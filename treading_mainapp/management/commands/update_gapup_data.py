from django.core.management.base import BaseCommand
from django.utils import timezone

from treading_site.treading_mainapp.gapup import update_all_gapup_data


class Command(BaseCommand):
    help = "Update daily gap-up status for Nifty 50 stocks"

    def handle(self, *args, **options):
        trade_date = timezone.localdate()
        results = update_all_gapup_data(trade_date=trade_date)
        self.stdout.write(
            self.style.SUCCESS(
                f"Gap-up data updated successfully for {len(results)} symbols on {trade_date}"
            )
        )