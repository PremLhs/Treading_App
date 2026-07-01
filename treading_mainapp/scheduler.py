import atexit
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from django.utils import timezone

from . import gapup as gapup_service

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(
    timezone=str(timezone.get_current_timezone()),
    job_defaults={
        "coalesce": True,
        "max_instances": 1,
        "misfire_grace_time": 1800,
    },
)

_scheduler_started = False


def run_auto_gap_scan():
    trade_date = timezone.localdate()
    logger.info("Starting AUTO_0930 gap scan for %s", trade_date)
    gapup_service.update_all_gapup_data(
        trade_date=trade_date,
        scan_type="AUTO_0930",
        trigger_source="apscheduler_auto",
        force=False,
    )


def run_final_gap_scan():
    trade_date = timezone.localdate()
    logger.info("Starting FINAL gap scan for %s", trade_date)
    gapup_service.update_all_gapup_data(
        trade_date=trade_date,
        scan_type="FINAL",
        trigger_source="apscheduler_final",
        force=True,
    )


def start():
    global _scheduler_started

    if _scheduler_started:
        return

    scheduler.add_job(
        run_auto_gap_scan,
        trigger=CronTrigger(day_of_week="mon-fri", hour=9, minute=30),
        id="gap_auto_0930_scan",
        replace_existing=True,
    )

    scheduler.add_job(
        run_final_gap_scan,
        trigger=CronTrigger(day_of_week="mon-fri", hour=15, minute=30),
        id="gap_final_1530_scan",
        replace_existing=True,
    )

    scheduler.start()
    _scheduler_started = True
    logger.info("Gap scan scheduler started.")
    atexit.register(lambda: scheduler.shutdown(wait=False))