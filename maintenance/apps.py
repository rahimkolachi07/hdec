import os, sys, logging
from django.apps import AppConfig
logger = logging.getLogger(__name__)

class MaintenanceConfig(AppConfig):
    name = "maintenance"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        # Skip management commands that don't serve requests
        skip = {"migrate","makemigrations","shell","test","collectstatic",
                "createsuperuser","dbshell","inspectdb","check"}
        if len(sys.argv) > 1 and sys.argv[1] in skip:
            return
        # Avoid double-start in Django dev server reloader
        if os.environ.get("RUN_MAIN") == "false":
            return

        from django.conf import settings
        from maintenance import sheet_loader

        sheet_id   = getattr(settings, "GOOGLE_SHEET_ID", "")
        local_path = getattr(settings, "SHEET_LOCAL_PATH", "solar_plant_data.xlsx")
        interval   = getattr(settings, "SHEET_DOWNLOAD_INTERVAL_MINUTES", 5)

        if not sheet_id:
            logger.warning("[Sheet] GOOGLE_SHEET_ID not set")
            return

        # If local file already exists, parse it immediately (no download needed yet)
        if os.path.exists(local_path):
            try:
                data, summary = sheet_loader.parse_excel(local_path)
                sheet_loader._upd(data=data, data_summary=summary,
                                  last_parse=__import__('datetime').datetime.now().strftime("%d %b %Y %H:%M:%S"),
                                  parse_count=1, status="live (cached)",
                                  download_ok=True)
                logger.info("[Sheet] Loaded from cached file")
            except Exception as e:
                logger.warning(f"[Sheet] Could not parse cached file: {e}")

        sheet_loader.start_worker(sheet_id, local_path, interval)
        logger.info(f"[Sheet] Auto-sync started — every {interval} minutes")
