import json, os
from pathlib import Path
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User, Group
from maintenance import sheet_loader

# ── Role helpers ───────────────────────────────────────────────────────────────
def is_admin(user):
    return user.is_staff or user.is_superuser or user.groups.filter(name='Admin').exists()

def login_view(request):
    error = ""
    if request.method == "POST":
        username = request.POST.get("username","").strip()
        password = request.POST.get("password","")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect(request.GET.get("next", "/"))
        error = "Invalid username or password"
    return render(request, "maintenance/login.html", {"error": error})

def logout_view(request):
    logout(request)
    return redirect("/login/")

def _data(): return sheet_loader.get_data()
def _state(): return sheet_loader.get_state()

def _base(extra=None):
    state = _state()
    data  = _data()
    ctx = {
        "state":      state,
        "sync_ok":    state.get("download_ok"),
        "last_parse": state.get("last_parse",""),
        "parse_count":state.get("parse_count",0),
        # Top bar KPIs
        "pm_comp":  data.get("pm",{}).get(1,{}).get("compliance",0),
        "cm_comp":  data.get("cm",{}).get(1,{}).get("compliance",0),
        "tr_pend":  data.get("trackers",{}).get("pending",0),
        "tr_rate":  data.get("trackers",{}).get("rate",0),
        # Company
        "company":  "POWER CHINA HDEC",
        "project":  "Al Henakiya 1100 MW Solar Power Plant",
    }
    if extra: ctx.update(extra)
    return ctx

@login_required
def home(request):
    data=_data(); pm=data.get("pm",{}); cm=data.get("cm",{})
    tr=data.get("trackers",{}); st=data.get("strings",{})
    scb=data.get("scb",{}); inv=data.get("inverters",{})
    pveq=data.get("pv_equip",{}); sseq=data.get("ss_equip",{})
    ssob=data.get("ss_obs",{}); pvob=data.get("pv_obs",{})
    w1pm=pm.get(1,{}); w1cm=cm.get(1,{})
    # Monthly totals across all weeks
    pm_mo_sched = sum(w.get("sched",0) for w in pm.values())
    pm_mo_done  = sum(w.get("done",0) for w in pm.values())
    pm_mo_pct   = round(pm_mo_done/pm_mo_sched*100,1) if pm_mo_sched else 0
    cm_mo_sched = sum(w.get("sched",0) for w in cm.values())
    cm_mo_done  = sum(w.get("done",0) for w in cm.values())
    cm_mo_pct   = round(cm_mo_done/cm_mo_sched*100,1) if cm_mo_sched else 0
    # Per-week arrays for charts
    pm_weeks = sorted(pm.keys())
    pm_labels = [f"W{w}" for w in pm_weeks]
    pm_sched_arr = [pm[w].get("sched",0) for w in pm_weeks]
    pm_done_arr  = [pm[w].get("done",0) for w in pm_weeks]
    pm_pct_arr   = [pm[w].get("compliance",0) for w in pm_weeks]
    cm_weeks = sorted(cm.keys())
    cm_labels = [f"W{w}" for w in cm_weeks]
    cm_sched_arr = [cm[w].get("sched",0) for w in cm_weeks]
    cm_done_arr  = [cm[w].get("done",0) for w in cm_weeks]
    cm_pct_arr   = [cm[w].get("compliance",0) for w in cm_weeks]
    modules=[
        {"id":"daily-report","name":"Daily Report",    "icon":"DR","color":"#f5c518","color_bg":"rgba(245,197,24,.12)","value":f"{w1pm.get('compliance',0)}%","label":"Today PM","sub":f"{w1pm.get('done',0)}/{w1pm.get('sched',0)} done","status":"ok" if w1pm.get('compliance',0)>=90 else "warn"},
        {"id":"pm",          "name":"PM Tracing",      "icon":"PM","color":"#00e676","color_bg":"rgba(0,230,118,.12)","value":f"{w1pm.get('compliance',0)}%","label":"Compliance","sub":f"W1: {w1pm.get('done',0)}/{w1pm.get('sched',0)}","status":"ok" if w1pm.get('compliance',0)>=90 else "warn"},
        {"id":"cm",          "name":"Corrective CM",   "icon":"CM","color":"#ffab00","color_bg":"rgba(255,171,0,.12)","value":f"{w1cm.get('compliance',0)}%","label":"CM Rate","sub":f"W1: {w1cm.get('done',0)}/{w1cm.get('sched',0)}","status":"ok" if w1cm.get('compliance',0)>=85 else "warn"},
        {"id":"trackers",    "name":"Trackers",        "icon":"TR","color":"#40c4ff","color_bg":"rgba(64,196,255,.12)","value":str(tr.get('pending',0)),"label":"Pending","sub":f"{tr.get('total',0)} total logged","status":"crit" if tr.get('pending',0)>5 else "ok"},
        {"id":"strings",     "name":"Strings",         "icon":"ST","color":"#1de9b6","color_bg":"rgba(29,233,182,.12)","value":f"{st.get('rate',0)}%","label":"Rectified","sub":f"{st.get('total',0)} faults","status":"ok"},
        {"id":"mvps",        "name":"MVPS / Inverter", "icon":"MV","color":"#e040fb","color_bg":"rgba(224,64,251,.12)","value":f"{inv.get('rate',0)}%","label":"Resolved","sub":f"{inv.get('total',0)} total","status":"ok"},
        {"id":"equipment",   "name":"Equipment",       "icon":"EQ","color":"#ff6e40","color_bg":"rgba(255,110,64,.12)","value":str(sseq.get('active_count',0)),"label":"SS Active","sub":f"{pveq.get('total',0)} PV total","status":"crit" if sseq.get('active_count',0)>0 else "ok"},
        {"id":"observations","name":"Observations",    "icon":"OB","color":"#ce93d8","color_bg":"rgba(206,147,216,.12)","value":str(pvob.get('open',0)),"label":"PV Open","sub":f"{ssob.get('pending',0)} SS pending","status":"warn"},
        {"id":"staff",       "name":"Staff",           "icon":"SF","color":"#82b1ff","color_bg":"rgba(130,177,255,.12)","value":"11/14","label":"On Site","sub":"2 leave · 1 training","status":"ok"},
        {"id":"documents",   "name":"Documents",       "icon":"DC","color":"#f5c518","color_bg":"rgba(245,197,24,.12)","value":"55","label":"Checklists","sub":"All revisions tracked","status":"ok"},
        {"id":"material",    "name":"Material",        "icon":"MT","color":"#ff8a65","color_bg":"rgba(255,138,101,.12)","value":"10","label":"Spare Items","sub":"Parts register","status":"ok"},
        {"id":"sync",        "name":"Live Sync",       "icon":"SY","color":"#00e676","color_bg":"rgba(0,230,118,.12)","value":f"{_state().get('parse_count',0)}x","label":"Auto Synced","sub":"Every 5 min","status":"ok"},
    ]
    alerts=[]
    for r in sseq.get("active_records",[]): alerts.append({"type":"crit","msg":f"SS CRITICAL: {r['equip']} — {r['issue']}"})
    if tr.get("pending",0)>0: alerts.append({"type":"warn","msg":f"{tr['pending']} tracker faults still open"})
    if ssob.get("pending",0)>0: alerts.append({"type":"warn","msg":f"{ssob['pending']} SS observations pending closure"})
    day_staff=[
        {"name":"Ahmad Israr","role":"Maint. Engineer"},
        {"name":"Khalid Rahman","role":"Sr. Technician"},
        {"name":"Faisal Al-Mutairi","role":"Electrician"},
        {"name":"Omar Saleh","role":"Mech. Tech"},
        {"name":"Waleed Nasser","role":"Safety Officer"},
    ]
    # Extra context for chatbot detailed answers
    st_pending   = [r for r in st.get("records",[]) if str(r.get("status","")).lower()!="done"][:20]
    inv_pending  = [r for r in inv.get("records",[]) if str(r.get("status","")).lower()!="done"][:15]
    pveq_active  = [r for r in pveq.get("records",[]) if str(r.get("status","")).lower()!="done"][:15]
    ssob_pending = [r for r in ssob.get("records",[]) if str(r.get("status","")).lower()!="done"][:20]
    pvob_sample  = [r for r in pvob.get("records",[]) if r.get("status","")=="Open"][:10]

    return render(request,"maintenance/home.html",_base({
        "modules":modules,"alerts":alerts,
        "w1pm":w1pm,"w1cm":w1cm,
        "w2pm":pm.get(2,{}),"w3pm":pm.get(3,{}),"w2cm":cm.get(2,{}),"w3cm":cm.get(3,{}),
        # Monthly totals
        "pm_mo_sched":pm_mo_sched,"pm_mo_done":pm_mo_done,"pm_mo_pct":pm_mo_pct,
        "cm_mo_sched":cm_mo_sched,"cm_mo_done":cm_mo_done,"cm_mo_pct":cm_mo_pct,
        # Weekly chart data
        "pm_labels_json":json.dumps(pm_labels),
        "pm_sched_json":json.dumps(pm_sched_arr),
        "pm_done_json":json.dumps(pm_done_arr),
        "pm_pct_json":json.dumps(pm_pct_arr),
        "cm_labels_json":json.dumps(cm_labels),
        "cm_sched_json":json.dumps(cm_sched_arr),
        "cm_done_json":json.dumps(cm_done_arr),
        "cm_pct_json":json.dumps(cm_pct_arr),
        # All aggregated data
        "tr":tr,"st":st,"scb":scb,"inv":inv,"pveq":pveq,"sseq":sseq,"ssob":ssob,"pvob":pvob,
        "active_issues":sseq.get("active_records",[]),
        "pv_by_type_json":json.dumps(pveq.get("by_type",{})),
        "alarm_json":json.dumps(tr.get("alarm_counts",{})),
        "action_json":json.dumps(st.get("action_counts",{})),
        # Detailed records for chatbot
        "st_pending":st_pending,
        "inv_pending":inv_pending,
        "pveq_active":pveq_active,
        "ssob_pending":ssob_pending,
        "pvob_sample":pvob_sample,
        "day_staff":day_staff,
    }))

@login_required
def daily_report(request):
    data=_data(); pm=data.get("pm",{}); cm=data.get("cm",{})
    tr=data.get("trackers",{}); st=data.get("strings",{})
    scb=data.get("scb",{}); inv=data.get("inverters",{})
    pveq=data.get("pv_equip",{}); sseq=data.get("ss_equip",{})
    ssob=data.get("ss_obs",{}); pvob=data.get("pv_obs",{})
    # Daily activity sheet
    daily_data = sheet_loader.get_daily_data()
    daily_sheets = list(daily_data.keys()) if daily_data else []
    daily_sheet_names = daily_sheets
    # Get first sheet data for display
    first_daily = daily_data.get(daily_sheets[0], {}) if daily_sheets else {}
    return render(request,"maintenance/daily_report.html",_base({
        "w1pm":pm.get(1,{}),"w1cm":cm.get(1,{}),"w2pm":pm.get(2,{}),"w2cm":cm.get(2,{}),"w3pm":pm.get(3,{}),"w3cm":cm.get(3,{}),
        "tr":tr,"st":st,"scb":scb,"inv":inv,
        "pveq":pveq,"sseq":sseq,"ssob":ssob,"pvob":pvob,
        "active_issues":sseq.get("active_records",[]),
        "alarm_json":json.dumps(tr.get("alarm_counts",{})),
        "daily_data":daily_data,"daily_sheets":daily_sheets,
        "first_daily":first_daily,
        "daily_sheet_id":"1HbzHNFdtXWBiqXk7HSmq2RI6u8AwOh2vvO3WYR3YgC8",
    }))

@login_required
def pm_page(request):
    data=_data(); pm=data.get("pm",{})
    return render(request,"maintenance/pm.html",_base({"pm":pm,"weeks":sorted(pm.keys())}))

@login_required
def cm_page(request):
    data=_data(); cm=data.get("cm",{})
    return render(request,"maintenance/cm.html",_base({"cm":cm,"weeks":sorted(cm.keys())}))

@login_required
def trackers_page(request):
    data=_data(); tr=data.get("trackers",{})
    return render(request,"maintenance/trackers.html",_base({"tr":tr,"alarm_json":json.dumps(tr.get("alarm_counts",{}))}))

@login_required
def strings_page(request):
    data=_data(); st=data.get("strings",{}); scb=data.get("scb",{})
    return render(request,"maintenance/strings.html",_base({"st":st,"scb":scb,"action_json":json.dumps(st.get("action_counts",{}))}))

@login_required
def mvps_page(request):
    data=_data(); inv=data.get("inverters",{})
    return render(request,"maintenance/mvps.html",_base({"inv":inv}))

@login_required
def equipment_page(request):
    data=_data()
    return render(request,"maintenance/equipment.html",_base({"pveq":data.get("pv_equip",{}),"sseq":data.get("ss_equip",{})}))

@login_required
def observations_page(request):
    data=_data()
    return render(request,"maintenance/observations.html",_base({"pvob":data.get("pv_obs",{}),"ssob":data.get("ss_obs",{})}))

@login_required
def staff_page(request):
    staff=[
        {"name":"Ahmad Israr","role":"Maintenance Engineer","status":"active","shift":"Day"},
        {"name":"Khalid Rahman","role":"Sr. Technician","status":"active","shift":"Day"},
        {"name":"Faisal Al-Mutairi","role":"Electrician","status":"active","shift":"Day"},
        {"name":"Omar Saleh","role":"Mech Technician","status":"active","shift":"Day"},
        {"name":"Yusuf Mohammed","role":"Technician","status":"active","shift":"Day"},
        {"name":"Sami Al-Harbi","role":"Technician","status":"active","shift":"Day"},
        {"name":"Waleed Nasser","role":"Safety Officer","status":"active","shift":"Day"},
        {"name":"Ibrahim Khalid","role":"Technician","status":"active","shift":"Night"},
        {"name":"Tariq Fahad","role":"Electrician","status":"active","shift":"Night"},
        {"name":"Hassan Al-Qahtani","role":"Sr. Technician","status":"active","shift":"Night"},
        {"name":"Nasser Bin Said","role":"Sr. Technician","status":"active","shift":"Night"},
        {"name":"Majed Al-Dosari","role":"Technician","status":"leave","shift":"—"},
        {"name":"Riyadh Turki","role":"Technician","status":"leave","shift":"—"},
        {"name":"Ziad Al-Anazi","role":"Technician","status":"training","shift":"—"},
    ]
    day_shift=[s for s in staff if s["shift"]=="Day" and s["status"]=="active"]
    night_shift=[s for s in staff if s["shift"]=="Night" and s["status"]=="active"]
    return render(request,"maintenance/staff.html",_base({
        "staff":staff,"on_site":sum(1 for s in staff if s["status"]=="active"),
        "on_leave":sum(1 for s in staff if s["status"]=="leave"),
        "training":sum(1 for s in staff if s["status"]=="training"),"total":len(staff),
        "day_shift":day_shift,"night_shift":night_shift,
    }))

@login_required
def documents_page(request):
    docs=[
        {"no":1,"name":"Weather Monitoring System Checklist","rev1":"C4","rev2":"C2","owner":"Ahmad Israr"},
        {"no":2,"name":"Power Station Checklist","rev1":"C4","rev2":"C1","owner":"Ahmad Israr"},
        {"no":3,"name":"Tracker Checklist","rev1":"C4","rev2":"UR","owner":"Ahmad Israr"},
        {"no":4,"name":"Robot Checklist","rev1":"C3","rev2":"UR","owner":"Farooq Ghumro"},
        {"no":5,"name":"SCB Checklist","rev1":"C3","rev2":"C1","owner":"Ahmad Israr"},
        {"no":6,"name":"Inverter Checklist","rev1":"C4","rev2":"C2","owner":"Ahmad Israr"},
        {"no":7,"name":"HV Switching Procedure","rev1":"C2","rev2":"C1","owner":"Ahmad Israr"},
        {"no":8,"name":"LOTO Procedure","rev1":"C3","rev2":"C2","owner":"Ahmad Israr"},
        {"no":9,"name":"Emergency Response Plan","rev1":"C2","rev2":"C1","owner":"Waleed Nasser"},
        {"no":10,"name":"Substation Daily Checklist","rev1":"C4","rev2":"C3","owner":"Ahmad Israr"},
    ]
    return render(request,"maintenance/documents.html",_base({"docs":docs}))

@login_required
def material_page(request):
    spares=[
        {"item":"Fuse Bucket","part_no":"FB-001","qty":12,"unit":"pcs","category":"Electrical","status":"In Stock"},
        {"item":"MC4 Connector","part_no":"MC4-01","qty":250,"unit":"pcs","category":"PV","status":"In Stock"},
        {"item":"String Cable 6mm","part_no":"SC-006","qty":500,"unit":"m","category":"PV","status":"In Stock"},
        {"item":"Surge Arrestor SPD","part_no":"SPD-01","qty":5,"unit":"pcs","category":"Electrical","status":"Low Stock"},
        {"item":"A26 Module SVG","part_no":"A26-SVG","qty":2,"unit":"pcs","category":"Substation","status":"In Stock"},
        {"item":"Winding Temp Board","part_no":"WTB-01","qty":1,"unit":"pcs","category":"Substation","status":"Low Stock"},
        {"item":"UPS Connector","part_no":"UPS-CN","qty":8,"unit":"pcs","category":"Electrical","status":"In Stock"},
        {"item":"Communication Mod","part_no":"COM-01","qty":3,"unit":"pcs","category":"Substation","status":"In Stock"},
        {"item":"Cable Joint Kit","part_no":"CJK-01","qty":10,"unit":"pcs","category":"PV","status":"In Stock"},
        {"item":"Silica Gel","part_no":"SG-001","qty":20,"unit":"kg","category":"Maintenance","status":"In Stock"},
    ]
    return render(request,"maintenance/material.html",_base({"spares":spares}))

@login_required
def sync_page(request):
    from django.conf import settings
    state=_state()
    return render(request,"maintenance/sync.html",_base({
        "sheet_id":getattr(settings,"GOOGLE_SHEET_ID",""),
        "interval":getattr(settings,"SHEET_DOWNLOAD_INTERVAL_MINUTES",5),
        "data_summary":state.get("data_summary",{}),
        "steps":[(1,"Server starts → thread launches"),(2,"Downloads sheet every 5 min"),(3,"Hash check — only re-parses if changed"),(4,"All 10 tabs parsed"),(5,"Refresh page to see updates")],
    }))

@require_POST
def sync_now(request):
    from django.conf import settings
    sheet_loader.force_sync_now(getattr(settings,"GOOGLE_SHEET_ID",""),getattr(settings,"SHEET_LOCAL_PATH","solar_plant_data.xlsx"))
    return JsonResponse({"ok":True})

def sync_status(request):
    state=_state()
    return JsonResponse({"status":state["status"],"download_ok":state["download_ok"],"last_download":state["last_download"],"last_parse":state["last_parse"],"next_in_sec":state["next_in_sec"],"download_count":state["download_count"],"parse_count":state["parse_count"],"file_size_kb":state["file_size_kb"],"error":state["error"],"has_data":bool(state["data"])})

def api_kpis(request):
    data=_data(); state=_state()
    pm=data.get("pm",{}); cm=data.get("cm",{}); tr=data.get("trackers",{})
    st=data.get("strings",{}); inv=data.get("inverters",{}); pveq=data.get("pv_equip",{})
    sseq=data.get("ss_equip",{}); w1pm=pm.get(1,{}); w1cm=cm.get(1,{})
    return JsonResponse({"parse_count":state.get("parse_count",0),"last_parse":state.get("last_parse",""),"pm_comp":w1pm.get("compliance",0),"cm_comp":w1cm.get("compliance",0),"tr_pending":tr.get("pending",0),"tr_rate":tr.get("rate",0),"st_rate":st.get("rate",0),"inv_rate":inv.get("rate",0),"pveq_rate":pveq.get("rate",0),"ss_active":sseq.get("active_count",0)})

def search_api(request):
    q=request.GET.get("q","").lower().strip()
    if not q: return JsonResponse({"results":[]})
    data=_data(); results=[]
    for r in data.get("trackers",{}).get("records",[]):
        if q in str(r.get("alarm","")).lower() or q in str(r.get("block","")).lower():
            results.append({"type":"Tracker","title":f"Block {r['block']} · {r['alarm']}","sub":r.get("status",""),"url":"/trackers/"})
            if len(results)>=4: break
    for r in data.get("pv_obs",{}).get("records",[]):
        if q in r.get("obs","").lower() or q in str(r.get("block","")).lower():
            results.append({"type":"Observation","title":f"Blk {r['block']} · {r['obs'][:35]}","sub":r.get("status",""),"url":"/observations/"})
            if len(results)>=7: break
    for r in data.get("pv_equip",{}).get("records",[]):
        if q in r.get("issue","").lower() or q in r.get("equip","").lower():
            results.append({"type":"Equipment","title":f"Blk {r['block']} · {r['equip']}","sub":r.get("status",""),"url":"/equipment/"})
            if len(results)>=9: break
    return JsonResponse({"results":results[:8]})


# ── SETTINGS PAGE ──────────────────────────────────────────────────────────────
@login_required
def settings_page(request):
    from maintenance.rag_engine import rag_stats
    try:
        stats = rag_stats()
    except Exception:
        stats = {"document_count": 0, "chunk_count": 0, "documents": []}
    api_key = getattr(settings, 'OPENAI_API_KEY', '')
    # Mask the key for display
    masked = (api_key[:8] + '...' + api_key[-4:]) if len(api_key) > 12 else ('Set' if api_key else 'Not set')
    return render(request, 'maintenance/settings.html', _base({
        'stats': stats,
        'api_key_masked': masked,
        'api_key_set': bool(api_key),
        'docs': stats.get('documents', []),
    }))



# ── SETTINGS PAGE ──────────────────────────────────────────────────────────────
@login_required
def settings_page(request):
    from maintenance.rag_engine import rag_stats
    import os
    try:
        stats = rag_stats()
    except Exception:
        stats = {"document_count": 0, "chunk_count": 0, "documents": []}
    api_key = getattr(settings, 'OPENAI_API_KEY', '') or os.environ.get('OPENAI_API_KEY', '')
    if not api_key:
        env_path = Path(settings.BASE_DIR) / '.env_hdec'
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith('OPENAI_API_KEY='):
                    api_key = line.split('=', 1)[1].strip()
    masked = (api_key[:8] + '...' + api_key[-4:]) if len(api_key) > 12 else ('Set' if api_key else 'Not configured')
    return render(request, 'maintenance/settings.html', _base({
        'stats': stats,
        'api_key_masked': masked,
        'api_key_set': bool(api_key),
        'docs': stats.get('documents', []),
    }))


@require_POST
def save_settings(request):
    import os
    key = request.POST.get('openai_key', '').strip()
    if not key:
        return JsonResponse({'ok': False, 'msg': 'No key provided'}, status=400)
    env_path = Path(settings.BASE_DIR) / '.env_hdec'
    lines = []
    if env_path.exists():
        lines = [l for l in env_path.read_text().splitlines() if not l.startswith('OPENAI_API_KEY')]
    lines.append('OPENAI_API_KEY=' + key)
    env_path.write_text(os.linesep.join(lines) + os.linesep)
    os.environ['OPENAI_API_KEY'] = key
    settings.OPENAI_API_KEY = key
    return JsonResponse({'ok': True, 'msg': 'API key saved successfully'})


@require_POST
def doc_upload(request):
    from maintenance.rag_engine import index_document
    import os
    api_key = getattr(settings, 'OPENAI_API_KEY', '') or os.environ.get('OPENAI_API_KEY', '')
    if not api_key:
        env_path = Path(settings.BASE_DIR) / '.env_hdec'
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith('OPENAI_API_KEY='):
                    api_key = line.split('=', 1)[1].strip()
    if not api_key:
        return JsonResponse({'ok': False, 'msg': 'OpenAI API key not configured. Go to Settings first.'}, status=400)
    uploaded = request.FILES.get('document')
    if not uploaded:
        return JsonResponse({'ok': False, 'msg': 'No file uploaded'}, status=400)
    allowed_ext = {'.pdf', '.docx', '.doc', '.txt', '.md', '.xlsx', '.xls', '.csv'}
    ext = Path(uploaded.name).suffix.lower()
    if ext not in allowed_ext:
        return JsonResponse({'ok': False, 'msg': 'File type not supported. Use PDF, DOCX, TXT, XLSX, CSV.'}, status=400)
    if uploaded.size > 20 * 1024 * 1024:
        return JsonResponse({'ok': False, 'msg': 'File too large (max 20MB)'}, status=400)
    docs_dir = Path(settings.HDEC_DOCS_DIR)
    docs_dir.mkdir(parents=True, exist_ok=True)
    safe_name = uploaded.name.replace(' ', '_').replace('/', '_')
    dest = docs_dir / safe_name
    with open(dest, 'wb') as f:
        for chunk in uploaded.chunks():
            f.write(chunk)
    try:
        result = index_document(str(dest), safe_name, api_key)
        if result.get('error'):
            return JsonResponse({'ok': False, 'msg': result['error']}, status=400)
        return JsonResponse({'ok': True, 'filename': safe_name, 'chunks': result.get('chunks', 0),
                             'msg': 'Indexed ' + str(result.get('chunks', 0)) + ' chunks from ' + safe_name})
    except Exception as e:
        return JsonResponse({'ok': False, 'msg': str(e)}, status=500)


@require_POST
def doc_delete(request, doc_id):
    from maintenance.rag_engine import remove_document
    ok = remove_document(doc_id)
    return JsonResponse({'ok': ok})


@login_required
def rag_stats_api(request):
    from maintenance.rag_engine import rag_stats
    try:
        return JsonResponse(rag_stats())
    except Exception as e:
        return JsonResponse({'document_count': 0, 'chunk_count': 0, 'documents': [], 'error': str(e)})


@csrf_exempt
@require_POST
def chat_api(request):
    import os, traceback as _tb

    # ── Load API key ──────────────────────────────────────────────────────────
    def _load_key():
        k = getattr(settings, 'OPENAI_API_KEY', '') or os.environ.get('OPENAI_API_KEY', '')
        if k:
            return k
        env_path = Path(settings.BASE_DIR) / '.env_hdec'
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith('OPENAI_API_KEY='):
                    k = line.split('=', 1)[1].strip()
                    if k:
                        os.environ['OPENAI_API_KEY'] = k
                        settings.OPENAI_API_KEY = k
                        return k
        return ''

    api_key = _load_key()
    if not api_key:
        return JsonResponse({'ok': False,
            'reply': 'HDEC Bot is not configured yet. Please go to ⚙ Settings in the sidebar and enter your OpenAI API key.'})

    # ── Parse request body ────────────────────────────────────────────────────
    try:
        body = json.loads(request.body)
    except Exception:
        return JsonResponse({'ok': False, 'reply': 'Invalid request format.'}, status=400)

    messages = body.get('messages', [])
    plant_context = body.get('plant_context', '')
    if not messages:
        return JsonResponse({'ok': False, 'reply': 'No messages provided.'}, status=400)

    # ── Try RAG chat ──────────────────────────────────────────────────────────
    try:
        from maintenance.rag_engine import rag_chat
        reply = rag_chat(messages, plant_context, api_key)
        return JsonResponse({'ok': True, 'reply': reply})
    except ImportError as e:
        # openai package not installed — try direct HTTP fallback
        return _openai_http_fallback(messages, plant_context, api_key, str(e))
    except Exception as e:
        err_detail = _tb.format_exc()[-800:]
        return JsonResponse({'ok': False, 'reply': 'Error: ' + str(e) + chr(10) + err_detail}, status=500)


def _openai_http_fallback(messages, plant_context, api_key, import_err):
    """Direct HTTP call to OpenAI — used when openai package is not installed."""
    import urllib.request, urllib.error
    data_body = {
        'model': 'gpt-4o-mini',
        'max_tokens': 800,
        'temperature': 0.2,
        'messages': [
            {'role': 'system', 'content': 'You are HDEC Bot, the maintenance assistant for Al Henakiya 1100 MW Solar Power Plant, Power China HDEC, Saudi Arabia. Answer using the plant data provided.\n\n' + plant_context},
        ] + messages[-10:]
    }
    try:
        req = urllib.request.Request(
            'https://api.openai.com/v1/chat/completions',
            data=json.dumps(data_body).encode('utf-8'),
            headers={
                'Authorization': 'Bearer ' + api_key,
                'Content-Type': 'application/json',
            },
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode('utf-8'))
        reply = result['choices'][0]['message']['content']
        return JsonResponse({'ok': True, 'reply': reply})
    except urllib.error.HTTPError as e:
        body_err = e.read().decode('utf-8', errors='replace')[:400]
        return JsonResponse({'ok': False, 'reply': 'OpenAI API error ' + str(e.code) + ': ' + body_err})
    except Exception as e2:
        return JsonResponse({'ok': False, 'reply': 'Fallback error: ' + str(e2) + '. Import error was: ' + import_err})
