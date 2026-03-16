import os, sys, logging
from pathlib import Path
from django.apps import AppConfig
logger = logging.getLogger(__name__)

class MaintenanceConfig(AppConfig):
    name = "maintenance"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        skip = {"migrate","makemigrations","shell","test","collectstatic","createsuperuser","dbshell","inspectdb","check"}
        if len(sys.argv) > 1 and sys.argv[1] in skip: return
        if os.environ.get("RUN_MAIN") == "false": return

        from django.conf import settings
        from maintenance import sheet_loader
        import threading

        sheet_id    = getattr(settings, "GOOGLE_SHEET_ID", "")
        local_path  = getattr(settings, "SHEET_LOCAL_PATH", "solar_plant_data.xlsx")
        interval    = getattr(settings, "SHEET_DOWNLOAD_INTERVAL_MINUTES", 5)
        daily_id    = getattr(settings, "DAILY_SHEET_ID", "")
        daily_path  = getattr(settings, "DAILY_SHEET_LOCAL_PATH", "daily_activity.xlsx")

        # Load cached maintenance data immediately
        if os.path.exists(local_path):
            try:
                data, summary = sheet_loader.parse_excel(local_path)
                sheet_loader._upd(data=data, data_summary=summary,
                    last_parse=__import__('datetime').datetime.now().strftime("%d %b %Y %H:%M:%S"),
                    parse_count=1, status="live (cached)", download_ok=True)
                logger.info("[Sheet] Loaded from cache")
            except Exception as e:
                logger.warning(f"[Sheet] Cache error: {e}")

        # Load cached daily data immediately
        if os.path.exists(daily_path):
            try:
                import pandas as pd
                xl = pd.read_excel(daily_path, sheet_name=None)
                data = sheet_loader._parse_daily_sheet(xl)
                sheet_loader._upd_daily(data=data, download_ok=True)
                logger.info("[Daily] Loaded from cache")
            except Exception as e:
                logger.warning(f"[Daily] Cache error: {e}")

        # Start main sync worker
        if sheet_id:
            sheet_loader.start_worker(sheet_id, local_path, interval)

        # Start daily sheet sync in background thread
        if daily_id:
            def _daily_loop():
                import time
                while True:
                    sheet_loader.sync_daily(daily_id, daily_path)
                    time.sleep(interval * 60)
            t = threading.Thread(target=_daily_loop, name="DailySyncWorker", daemon=True)
            t.start()
            logger.info("[Daily] Auto-sync started")

        # Pre-load OpenAI API key from .env_hdec if present
        env_path = Path(settings.BASE_DIR) / '.env_hdec'
        if env_path.exists() and not getattr(settings, 'OPENAI_API_KEY', ''):
            try:
                for line in env_path.read_text().splitlines():
                    if line.startswith('OPENAI_API_KEY='):
                        key = line.split('=', 1)[1].strip()
                        if key:
                            os.environ['OPENAI_API_KEY'] = key
                            settings.OPENAI_API_KEY = key
                            logger.info("[HDEC Bot] OpenAI API key loaded from .env_hdec")
                            break
            except Exception as ke:
                logger.warning(f"[HDEC Bot] Could not load API key: {ke}")
