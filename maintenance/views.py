import json
from django.shortcuts import render
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from maintenance import sheet_loader


def _ctx(extra=None):
    """Base context — no login/user needed."""
    state = sheet_loader.get_state()
    data  = sheet_loader.get_data()
    ctx = {
        "state":       state,
        "pm_comp":     data.get("pm",{}).get(1,{}).get("compliance", 0),
        "cm_comp":     data.get("cm",{}).get(1,{}).get("compliance", 0),
        "tr_pend":     data.get("trackers",{}).get("pending", 0),
        "tr_rate":     data.get("trackers",{}).get("rate", 0),
        "parse_count": state.get("parse_count", 0),
        "last_parse":  state.get("last_parse", ""),
    }
    if extra:
        ctx.update(extra)
    return ctx


def overview(request):
    data = sheet_loader.get_data()
    pm=data.get("pm",{}); cm=data.get("cm",{})
    tr=data.get("trackers",{}); st=data.get("strings",{})
    scb=data.get("scb",{}); pveq=data.get("pv_equip",{})
    sseq=data.get("ss_equip",{}); ssob=data.get("ss_obs",{})
    pvob=data.get("pv_obs",{}); inv=data.get("inverters",{})
    w1pm=pm.get(1,{}); w2pm=pm.get(2,{}); w3pm=pm.get(3,{})
    w1cm=cm.get(1,{}); w2cm=cm.get(2,{}); w3cm=cm.get(3,{})
    ctx = _ctx({
        "w1pm": w1pm, "w2pm": w2pm, "w3pm": w3pm,
        "w1cm": w1cm, "w2cm": w2cm, "w3cm": w3cm,
        "inv": inv,
        "tr": tr, "st": st, "scb": scb,
        "pveq": pveq, "sseq": sseq, "ssob": ssob, "pvob": pvob,
        "active_issues":   sseq.get("active_records", []),
        "pv_by_type_json": json.dumps(pveq.get("by_type", {})),
        "alarm_json":      json.dumps(tr.get("alarm_counts", {})),
        "action_json":     json.dumps(st.get("action_counts", {})),
    })
    return render(request, "maintenance/overview.html", ctx)


def pm_page(request):
    data = sheet_loader.get_data()
    pm = data.get("pm", {})
    return render(request, "maintenance/pm.html", _ctx({"pm": pm, "weeks": sorted(pm.keys())}))


def cm_page(request):
    data = sheet_loader.get_data()
    cm = data.get("cm", {})
    return render(request, "maintenance/cm.html", _ctx({"cm": cm, "weeks": sorted(cm.keys())}))


def trackers_page(request):
    data = sheet_loader.get_data()
    return render(request, "maintenance/trackers.html", _ctx({"tr": data.get("trackers", {})}))


def strings_page(request):
    data = sheet_loader.get_data()
    return render(request, "maintenance/strings.html", _ctx({
        "st": data.get("strings", {}),
        "scb": data.get("scb", {}),
        "inv": data.get("inverters", {}),
    }))


def equipment_page(request):
    data = sheet_loader.get_data()
    return render(request, "maintenance/equipment.html", _ctx({
        "pveq": data.get("pv_equip", {}),
        "sseq": data.get("ss_equip", {}),
    }))


def observations_page(request):
    data = sheet_loader.get_data()
    return render(request, "maintenance/observations.html", _ctx({
        "pvob": data.get("pv_obs", {}),
        "ssob": data.get("ss_obs", {}),
    }))


def sync_page(request):
    from django.conf import settings
    state = sheet_loader.get_state()
    return render(request, "maintenance/sync.html", _ctx({
        "sheet_id":     getattr(settings, "GOOGLE_SHEET_ID", ""),
        "interval":     getattr(settings, "SHEET_DOWNLOAD_INTERVAL_MINUTES", 5),
        "local_path":   getattr(settings, "SHEET_LOCAL_PATH", ""),
        "data_summary": state.get("data_summary", {}),
        "steps": [
            (1, "Django server starts → background thread launches automatically"),
            (2, "Downloads sheet every 5 min via public URL (no API key needed)"),
            (3, "SHA-256 hash check — only re-parses if sheet actually changed"),
            (4, "All 10 tabs parsed into live dashboard data"),
            (5, "Refresh any page → see updated numbers and charts instantly"),
        ],
    }))


@require_POST
def sync_now(request):
    from django.conf import settings
    sheet_loader.force_sync_now(
        getattr(settings, "GOOGLE_SHEET_ID", ""),
        getattr(settings, "SHEET_LOCAL_PATH", "solar_plant_data.xlsx"),
    )
    return JsonResponse({"ok": True})


def sync_status(request):
    state = sheet_loader.get_state()
    return JsonResponse({
        "status":         state["status"],
        "download_ok":    state["download_ok"],
        "last_download":  state["last_download"],
        "last_parse":     state["last_parse"],
        "next_in_sec":    state["next_in_sec"],
        "download_count": state["download_count"],
        "parse_count":    state["parse_count"],
        "file_size_kb":   state["file_size_kb"],
        "error":          state["error"],
        "has_data":       bool(state["data"]),
    })


def api_kpis(request):
    data  = sheet_loader.get_data()
    state = sheet_loader.get_state()
    pm=data.get("pm",{}); cm=data.get("cm",{})
    tr=data.get("trackers",{}); st=data.get("strings",{})
    scb=data.get("scb",{}); pveq=data.get("pv_equip",{})
    sseq=data.get("ss_equip",{}); ssob=data.get("ss_obs",{})
    pvob=data.get("pv_obs",{})
    w1pm=pm.get(1,{}); w2pm=pm.get(2,{}); w3pm=pm.get(3,{})
    w1cm=cm.get(1,{}); w2cm=cm.get(2,{}); w3cm=cm.get(3,{})
    return JsonResponse({
        "parse_count":  state.get("parse_count", 0),
        "last_parse":   state.get("last_parse", ""),
        "pm_comp":      w1pm.get("compliance", 0),
        "pm_done":      w1pm.get("done", 0),
        "pm_sched":     w1pm.get("sched", 0),
        "pm_pending":   w1pm.get("pending", 0),
        "cm_comp":      w1cm.get("compliance", 0),
        "cm_done":      w1cm.get("done", 0),
        "cm_sched":     w1cm.get("sched", 0),
        "cm_pending":   w1cm.get("pending", 0),
        "cm2_comp":     w2cm.get("compliance", 0),
        "tr_total":     tr.get("total", 0),
        "tr_done":      tr.get("done", 0),
        "tr_pending":   tr.get("pending", 0),
        "tr_rate":      tr.get("rate", 0),
        "st_total":     st.get("total", 0),
        "st_done":      st.get("done", 0),
        "st_pending":   st.get("pending", 0),
        "st_rate":      st.get("rate", 0),
        "scb_total":    scb.get("total", 0),
        "scb_done":     scb.get("done", 0),
        "pveq_total":   pveq.get("total", 0),
        "pveq_done":    pveq.get("done", 0),
        "pveq_active":  pveq.get("active", 0),
        "pveq_rate":    pveq.get("rate", 0),
        "ss_active":    sseq.get("active_count", 0),
        "ssob_total":   ssob.get("total", 0),
        "ssob_done":    ssob.get("done", 0),
        "ssob_pending": ssob.get("pending", 0),
        "pvob_total":   pvob.get("total", 0),
        "pvob_open":    pvob.get("open", 0),
        "pvob_closed":  pvob.get("closed", 0),
    })
