from django.core.management.base import BaseCommand

from treading_mainapp.services.nifty50_loader import DATA_FILE
from treading_mainapp.services.nifty50_updater import refresh_nifty50_data


class Command(BaseCommand):
    help = "Refresh the local Nifty 50 master file from a configured source"

    def add_arguments(self, parser):
        parser.add_argument("--source-url", dest="source_url", default=None, help="Optional source URL to use for the refresh")

    def handle(self, *args, **options):
        try:
            result = refresh_nifty50_data(options.get("source_url"))
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f"Nifty 50 refresh skipped due to error: {exc}"))
            return

        self.stdout.write(self.style.SUCCESS(f"Updated {DATA_FILE} with {len(result.get('symbols', []))} symbols"))
