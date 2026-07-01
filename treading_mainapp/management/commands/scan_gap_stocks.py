from django.core.management.base import BaseCommand
from django.utils import timezone

from treading_mainapp import gapup as gapup_service


class Command(BaseCommand):
    help = "Scan Nifty 50 stocks for gap up / gap down using previous day and first 15m candle."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=None, help="Limit number of symbols to scan.")
        parser.add_argument("--force", action="store_true", help="Force fresh scan even if today's data exists.")
        parser.add_argument("--scan-type", type=str, default="MANUAL", help="AUTO_0930 / MANUAL / FORCE / FINAL")

    def handle(self, *args, **options):
        trade_date = timezone.localdate()
        limit = options.get("limit")
        force = options.get("force", False)
        scan_type = options.get("scan_type") or "MANUAL"

        self.stdout.write(self.style.NOTICE(f"Starting gap scan for {trade_date}"))

        result = gapup_service.update_all_gapup_data(
            trade_date=trade_date,
            limit_symbols=limit,
            scan_type=scan_type,
            trigger_source="management_command",
            force=force,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"{result['message']}"
            )
        )

        if result["errors"]:
            for err in result["errors"]:
                self.stdout.write(self.style.ERROR(f"{err['symbol']} -> {err['error']}"))