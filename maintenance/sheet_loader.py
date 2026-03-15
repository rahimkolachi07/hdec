"""
maintenance/sheet_loader.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━
Downloads the public Google Sheet every INTERVAL minutes and parses all tabs.
NO API KEY — uses public /export?format=xlsx URL.
"""
import os, hashlib, threading, time, logging
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

logger = logging.getLogger(__name__)

_state = {
    "status": "starting",
    "last_download": None, "last_parse": None,
    "download_ok": None, "error": "",
    "next_in_sec": None,
    "download_count": 0, "parse_count": 0,
    "last_hash": None, "file_size_kb": 0,
    "data": {}, "data_summary": {},
}
_lock = threading.Lock()
_stop = threading.Event()

def get_state():
    with _lock: return dict(_state)

def get_data():
    with _lock: return _state["data"]

def _upd(**kw):
    with _lock: _state.update(kw)

# ─── helpers ──────────────────────────────────────────────────────────────────
def _si(v, d=0):
    try: return int(float(str(v).strip()))
    except: return d

def _sf(v, d=0.0):
    try: return float(str(v).strip())
    except: return d

def _ss(v, d=""):
    if v is None: return d
    try:
        import math
        if isinstance(v, float) and math.isnan(v): return d
    except: pass
    s = str(v).strip()
    return d if s.lower() in ("nan","nat","none","") else s

def _sd(v):
    if v is None: return None
    try:
        import math
        if isinstance(v, float) and math.isnan(v): return None
    except: pass
    try:
        if isinstance(v, (pd.Timestamp, datetime)):
            return v.strftime("%d %b %Y")
        s = str(v).strip()
        if len(s) >= 10 and s[4] == '-':
            return datetime.strptime(s[:10], "%Y-%m-%d").strftime("%d %b %Y")
        return s[:10] if s else None
    except: return str(v)[:10]

# ─── PM parser ────────────────────────────────────────────────────────────────
def _parse_pm(df):
    """
    The sheet has MULTIPLE week sections.
    Week 1 column header = 'Week 1 (1 March To 4 March)'
    Subsequent weeks start at rows labelled 'Week 2 ...' in col[1].
    Structure per section:
      col0=AREA  col1=EQUIPMENT  col2=Schedule PM  col3=PM done
    """
    weeks = {}

    # ── Week 1: data starts at row 1 (row 0 is sub-header)
    # columns: AREA | Week1 label | Unnamed:2 | Unnamed:3
    #          (row 0 values): nan | EQUIPMENT | Schedule PM | PM done
    # actual data rows: 1..until next blank AREA block

    col_area = 0
    col_task = 1
    col_sched = 2
    col_done  = 3

    current_week = 1
    weeks[1] = {"label": "Week 1 (1 March To 4 March)", "tasks": [], "sched": 0, "done": 0}

    for i, row in df.iterrows():
        r = [_ss(c) for c in row]

        # Detect new week header row (col1 starts with "Week N")
        task_val = r[col_task].lower()
        if task_val.startswith("week ") and "march" in task_val:
            # Extract week number
            for n in range(2, 8):
                if f"week {n}" in task_val:
                    current_week = n
                    if current_week not in weeks:
                        weeks[current_week] = {"label": r[col_task], "tasks": [], "sched": 0, "done": 0}
                    break
            continue

        area = r[col_area]
        task = r[col_task]
        sched_r = r[col_sched]
        done_r  = r[col_done]

        # Skip header/total/blank rows
        if not task or task.upper() in ("EQUIPMENT","TOTAL","COMPLIANCE SCORE","PENDING","AREA",""):
            continue
        if area.upper() in ("NAN","") and task.upper() in ("TOTAL","COMPLIANCE SCORE","PENDING",""):
            continue
        if area.upper() == "NAN":
            area = ""
        if not area and not task:
            continue

        all_done = sched_r.lower() == "all"
        sched = _si(sched_r) if not all_done else 0
        done  = _si(done_r)  if not all_done else 0

        if sched < 0 or (not all_done and sched == 0 and done == 0 and not task):
            continue

        status = "Done" if (all_done or (sched > 0 and done >= sched)) else (
                 "Pending" if done == 0 else "In Progress")

        weeks[current_week]["tasks"].append({
            "area": area or "PV", "task": task,
            "sched": sched, "done": done,
            "all_done": all_done, "status": status,
        })
        if not all_done:
            weeks[current_week]["sched"] += sched
            weeks[current_week]["done"]  += done

    for w in weeks.values():
        s, d = w["sched"], w["done"]
        w["compliance"] = round(d / s * 100, 1) if s else 0
        w["pending"]    = max(0, s - d)

    return weeks

# ─── CM parser ────────────────────────────────────────────────────────────────
def _parse_cm(df):
    """
    col0=EQUIPMENT col1=Schedule CM col2=CM Done
    Week sections start with a row where col0 = 'Week N (...)'
    Week 1 data starts at row 1.
    """
    weeks = {}
    current_week = 1
    weeks[1] = {"tasks": [], "sched": 0, "done": 0}

    for i, row in df.iterrows():
        r = [_ss(c) for c in row]
        equip   = r[0]
        sched_r = r[1]
        done_r  = r[2]

        equip_l = equip.lower()
        if equip_l.startswith("week "):
            for n in range(2, 8):
                if f"week {n}" in equip_l:
                    current_week = n
                    if current_week not in weeks:
                        weeks[current_week] = {"tasks": [], "sched": 0, "done": 0}
                    break
            continue

        if not equip or equip.upper() in ("EQUIPMENT","TOTAL","COMPLIANCE SCORE","PENDING",""):
            continue

        sched = _si(sched_r)
        done  = _si(done_r)
        status = "Done" if sched and done >= sched else ("Pending" if done == 0 else "In Progress")

        weeks[current_week]["tasks"].append({
            "equip": equip, "sched": sched, "done": done,
            "status": status, "pending": max(0, sched - done),
        })
        weeks[current_week]["sched"] += sched
        weeks[current_week]["done"]  += done

    for w in weeks.values():
        s, d = w["sched"], w["done"]
        w["compliance"] = round(d / s * 100, 1) if s else 0
        w["pending"]    = max(0, s - d)

    return weeks

# ─── Trackers ─────────────────────────────────────────────────────────────────
def _parse_trackers(df):
    records = []
    for _, row in df.iloc[3:].iterrows():
        r = [_ss(c) for c in row]
        if not r[0].isdigit(): continue
        records.append({
            "sno": _si(r[0]), "date": _sd(row.iloc[1]),
            "block": _si(r[2]), "tracker": _si(r[3]),
            "alarm": r[4], "action": r[5],
            "rect_date": _sd(row.iloc[6]),
            "status": r[7], "remarks": r[8],
        })
    done = sum(1 for r in records if r["status"].lower() in ("done","d0ne"))
    pend = [r for r in records if r["status"].lower() not in ("done","d0ne")]
    alarms = {}
    for r in pend:
        alarms[r["alarm"]] = alarms.get(r["alarm"], 0) + 1
    total = len(records)
    return {
        "total": total, "done": done, "pending": len(pend),
        "rate": round(done / total * 100, 1) if total else 0,
        "records": records, "pending_records": pend,
        "alarm_counts": alarms,
    }

# ─── SCB ──────────────────────────────────────────────────────────────────────
def _parse_scb(df):
    records = []
    for _, row in df.iloc[3:].iterrows():
        r = [_ss(c) for c in row]
        if not r[0].isdigit(): continue
        records.append({
            "sno": _si(r[0]), "date": _sd(row.iloc[1]),
            "block": _si(r[2]), "scb": _si(r[3]),
            "alarm": r[4], "action": r[5],
            "rect_date": _sd(row.iloc[6]), "status": r[7],
        })
    done = sum(1 for r in records if r["status"].lower() == "done")
    return {"total": len(records), "done": done, "pending": len(records) - done, "records": records}

# ─── Strings ──────────────────────────────────────────────────────────────────
def _parse_strings(df):
    records = []
    for _, row in df.iloc[3:].iterrows():
        r = [_ss(c) for c in row]
        if not r[0].isdigit(): continue
        records.append({
            "sno": _si(r[0]), "date": _sd(row.iloc[1]),
            "block": _si(r[2]), "scb": _si(r[3]), "string": _si(r[4]),
            "action": r[5], "rect_date": _sd(row.iloc[6]),
            "status": r[7], "remarks": r[8],
        })
    done = sum(1 for r in records if r["status"].lower() == "done")
    acts = {}
    for r in records:
        acts[r["action"]] = acts.get(r["action"], 0) + 1
    total = len(records)
    return {
        "total": total, "done": done, "pending": total - done,
        "rate": round(done / total * 100, 1) if total else 0,
        "records": records[:60], "action_counts": acts,
    }

# ─── Inverters ────────────────────────────────────────────────────────────────
def _parse_inverters(df):
    records = []
    for _, row in df.iloc[4:].iterrows():
        r = [_ss(c) for c in row]
        if not r[0].isdigit(): continue
        records.append({
            "sno": _si(r[0]), "date": _sd(row.iloc[1]),
            "block": _ss(row.iloc[2]), "module": _ss(row.iloc[3]),
            "inverter": _ss(row.iloc[4]), "issue": r[5],
            "action": r[6], "rect_date": _sd(row.iloc[7]), "status": r[8],
        })
    done = sum(1 for r in records if r["status"].lower() == "done")
    total = len(records)
    return {
        "total": total, "done": done, "pending": total - done,
        "rate": round(done / total * 100, 1) if total else 0,
        "records": records,
    }

# ─── PV Equipment ─────────────────────────────────────────────────────────────
def _parse_pv_equip(df):
    records = []
    for _, row in df.iloc[1:].iterrows():
        r = [_ss(c) for c in row]
        if not r[0].isdigit(): continue
        records.append({
            "sno": _si(r[0]), "date": _sd(row.iloc[1]),
            "block": r[2], "equip": r[3], "gen_aff": r[4],
            "issue": r[5], "action": r[6], "done_by": r[7],
            "rect_date": _sd(row.iloc[8]), "status": r[9], "spare": r[10],
        })
    done = sum(1 for r in records if r["status"].lower() == "done")
    by_type = {}
    for r in records:
        by_type[r["equip"]] = by_type.get(r["equip"], 0) + 1
    total = len(records)
    return {
        "total": total, "done": done, "active": total - done,
        "rate": round(done / total * 100, 1) if total else 0,
        "records": records, "by_type": by_type,
    }

# ─── SS Equipment ─────────────────────────────────────────────────────────────
def _parse_ss_equip(df):
    records = []
    for _, row in df.iloc[1:].iterrows():
        r = [_ss(c) for c in row]
        if not r[0].isdigit(): continue
        records.append({
            "sno": _si(r[0]), "date": _sd(row.iloc[1]),
            "area": r[2], "equip": r[3], "gen_aff": r[4],
            "issue": r[5], "action": r[6], "done_by": r[7],
            "rect_date": _sd(row.iloc[8]), "status": r[9], "spare": r[10],
        })
    done   = sum(1 for r in records if r["status"].lower() == "done")
    active = [r for r in records if r["status"].lower() not in ("done", "")]
    return {
        "total": len(records), "done": done,
        "active_count": len(active),
        "records": records, "active_records": active,
    }

# ─── SS Observations ──────────────────────────────────────────────────────────
def _parse_ss_obs(df):
    records = []
    for _, row in df.iterrows():
        r = [_ss(c) for c in row]
        if not r[0].isdigit(): continue
        records.append({
            "sno": _si(r[0]), "area": r[1], "equip": r[2],
            "issue": r[3], "action": r[4],
            "rect_date": _sd(row.iloc[5]), "status": r[6],
        })
    done    = sum(1 for r in records if r["status"].upper() == "DONE")
    pending = len(records) - done
    area_counts = {}
    for r in records:
        area_counts[r["area"]] = area_counts.get(r["area"], 0) + 1
    return {
        "total": len(records), "done": done, "pending": pending,
        "records": records, "area_counts": area_counts,
    }

# ─── PV Observations ──────────────────────────────────────────────────────────
def _parse_pv_obs(df):
    records = []
    for _, row in df.iloc[3:].iterrows():
        r = [_ss(c) for c in row]
        if not r[0].isdigit(): continue
        status = _ss(row.iloc[8]) if len(row) > 8 else "Open"
        records.append({
            "sno": _si(r[0]), "date": _sd(row.iloc[1]),
            "block": r[2], "obs": r[3], "equip": r[4], "desc": r[5],
            "action": _ss(row.iloc[7]) if len(row) > 7 else "",
            "status": status,
        })
    closed = sum(1 for r in records if r["status"].lower() == "closed")
    opened = len(records) - closed
    by_type = {}
    for r in records:
        by_type[r["obs"]] = by_type.get(r["obs"], 0) + 1
    return {
        "total": len(records), "open": opened, "closed": closed,
        "records": records[:30], "by_type": by_type,
    }

# ─── Main parse ───────────────────────────────────────────────────────────────
PARSERS = {
    "Statistics PM":         ("pm",        _parse_pm),
    "Statistics CM":         ("cm",        _parse_cm),
    "Trackers":              ("trackers",  _parse_trackers),
    "SCB":                   ("scb",       _parse_scb),
    "Strings & PV Modules":  ("strings",   _parse_strings),
    "Inverter and MVPS":     ("inverters", _parse_inverters),
    "PV Equipments Failure": ("pv_equip",  _parse_pv_equip),
    "SS Equipments failure": ("ss_equip",  _parse_ss_equip),
    "SS Observations":       ("ss_obs",    _parse_ss_obs),
    "PV Observations":       ("pv_obs",    _parse_pv_obs),
}

def parse_excel(path):
    _upd(status="parsing")
    xl = pd.read_excel(path, sheet_name=None)
    data, summary = {}, {}
    for sheet_name, (key, parser) in PARSERS.items():
        if sheet_name in xl:
            try:
                parsed = parser(xl[sheet_name])
                data[key] = parsed
                total = parsed.get("total", parsed.get("sched", 0))
                summary[sheet_name] = total
                logger.info(f"  ✓ {sheet_name} ({total} rows)")
            except Exception as e:
                import traceback
                logger.error(f"  ✗ {sheet_name}: {e}\n{traceback.format_exc()}")
                data[key] = {}
        else:
            data[key] = {}
    data["parsed_at"] = datetime.now().strftime("%d %b %Y %H:%M:%S")
    return data, summary

# ─── Download ─────────────────────────────────────────────────────────────────
def download_sheet(sheet_id, local_path):
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
    _upd(status="downloading")
    try:
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            content = r.content
            new_hash = hashlib.sha256(content).hexdigest()
            with _lock: old_hash = _state["last_hash"]
            changed = (new_hash != old_hash)
            Path(local_path).parent.mkdir(parents=True, exist_ok=True)
            with open(local_path, "wb") as f:
                f.write(content)
            _upd(
                download_ok=True, error="",
                last_download=datetime.now().strftime("%d %b %Y %H:%M:%S"),
                file_size_kb=round(len(content)/1024, 1),
                last_hash=new_hash,
                download_count=_state["download_count"] + 1,
            )
            logger.info(f"[Sheet] Downloaded {len(content):,}B ({'CHANGED' if changed else 'unchanged'})")
            return True, changed
        else:
            _upd(download_ok=False, error=f"HTTP {r.status_code}", status="error")
            return False, False
    except Exception as e:
        _upd(download_ok=False, error=str(e), status="error")
        logger.error(f"[Sheet] Download error: {e}")
        return False, False

def do_sync(sheet_id, local_path, force=False):
    ok, changed = download_sheet(sheet_id, local_path)
    if ok and (changed or force):
        try:
            data, summary = parse_excel(local_path)
            _upd(data=data, data_summary=summary,
                 last_parse=datetime.now().strftime("%d %b %Y %H:%M:%S"),
                 parse_count=_state["parse_count"] + 1,
                 status="live", error="")
        except Exception as e:
            _upd(error=str(e), status="error")
            logger.error(f"[Sheet] Parse error: {e}")
    elif ok:
        _upd(status="live")
    # Fall back to cached file
    if not ok and os.path.exists(local_path) and not _state["data"]:
        try:
            data, summary = parse_excel(local_path)
            _upd(data=data, data_summary=summary,
                 last_parse=datetime.now().strftime("%d %b %Y %H:%M:%S"),
                 status="live (cached)", error="Using cached file")
        except: pass

def _worker(sheet_id, local_path, interval_sec):
    logger.info(f"[Sheet] Worker started (interval={interval_sec}s)")
    do_sync(sheet_id, local_path, force=True)
    while not _stop.is_set():
        end_time = time.time() + interval_sec
        while time.time() < end_time:
            if _stop.is_set(): break
            _upd(next_in_sec=max(0, int(end_time - time.time())))
            time.sleep(1)
        if not _stop.is_set():
            do_sync(sheet_id, local_path)

_thread = None

def start_worker(sheet_id, local_path, interval_minutes=5):
    global _thread, _stop
    if _thread and _thread.is_alive(): return
    _stop = threading.Event()
    _thread = threading.Thread(
        target=_worker,
        args=(sheet_id, local_path, interval_minutes * 60),
        name="SheetSyncWorker", daemon=True
    )
    _thread.start()

def force_sync_now(sheet_id, local_path):
    def _bg(): do_sync(sheet_id, local_path, force=True)
    threading.Thread(target=_bg, daemon=True).start()
