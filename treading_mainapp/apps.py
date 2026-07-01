from django.apps import AppConfig


class TreadingMainappConfig(AppConfig):
    name = 'treading_mainapp'




import os
from django.apps import AppConfig


class TreadingMainappConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "treading_mainapp"

    def ready(self):
        if os.environ.get("RUN_MAIN") != "true" and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
            return

        if os.environ.get("DISABLE_GAP_SCHEDULER") == "1":
            return

        try:
            from .scheduler import start
            start()
        except Exception:
            pass