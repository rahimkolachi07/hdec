# SolarCMMS Pro — Django Dashboard
## No login required · Auto-syncs from Google Sheets every 5 minutes

---

## QUICK START (3 commands)

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Open: http://127.0.0.1:8000

**No login screen. Dashboard opens directly.**

---

## HOW AUTO-SYNC WORKS

When you run `python manage.py runserver`:

1. The app **immediately loads** `solar_plant_data.xlsx` from the project folder
2. A background thread starts and **downloads your Google Sheet every 5 minutes**
3. If the sheet changed → re-parses all 10 tabs → dashboard updates
4. If no change → skips parsing (efficient)
5. The **green dot** in the top-right shows sync status live

To update the dashboard: **edit your Google Sheet → wait 5 minutes → refresh page**

Or click the sync dot (top-right) → "Download Now" for instant update.

---

## CHANGE SYNC INTERVAL

Edit `solar_cmms/settings.py`:
```python
SHEET_DOWNLOAD_INTERVAL_MINUTES = 5   # default
SHEET_DOWNLOAD_INTERVAL_MINUTES = 1   # every 1 minute
SHEET_DOWNLOAD_INTERVAL_MINUTES = 60  # every 1 hour
```

---

## PAGES

| URL | Page |
|---|---|
| / | Overview + KPIs + 9 charts |
| /pm/ | PM Tracing (all weeks) |
| /cm/ | Corrective Maintenance |
| /trackers/ | Tracker faults |
| /strings/ | Strings, SCB, Inverters |
| /equipment/ | Equipment failures |
| /observations/ | PV & SS observations |
| /sync/ | Sync status & manual trigger |
| /admin/ | Django admin panel |

---

## GOOGLE SHEET REQUIREMENT

Your sheet must be **public** (Share → Anyone with link → Viewer).

Sheet tabs used:
- Statistics PM, Statistics CM
- Trackers, SCB, Strings & PV Modules
- Inverter and MVPS, PV Equipments Failure
- SS Equipments failure, SS Observations, PV Observations
