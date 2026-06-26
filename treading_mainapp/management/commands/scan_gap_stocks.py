from django.core.management.base import BaseCommand
from django.utils import timezone

from treading_mainapp import gapup as gapup_service


class Command(BaseCommand):
    help = "Scan Nifty 50 stocks for gap up / gap down using previous day and first 15m candle."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Limit number of symbols to scan.",
        )

    def handle(self, *args, **options):
        trade_date = timezone.localdate()
        limit = options.get("limit")

        self.stdout.write(self.style.NOTICE(f"Starting gap scan for {trade_date}"))

        result = gapup_service.update_all_gapup_data(
            trade_date=trade_date,
            limit_symbols=limit,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Completed. Success={result['success_count']} Failed={result['error_count']}"
            )
        )

        if result["errors"]:
            for err in result["errors"]:
                self.stdout.write(self.style.ERROR(f"{err['symbol']} -> {err['error']}"))