from pathlib import Path
import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand
from treading_mainapp.models import UserProfile


class Command(BaseCommand):
    help = "Export users to Excel file"

    def handle(self, *args, **kwargs):
        users = UserProfile.objects.select_related("user").all()

        data = []
        for item in users:
            data.append({
                "Username": item.user.username,
                "Mobile": item.mobile,
                "Password(Hash)": item.user.password,
                "Email": item.user.email,
                "Date Joined": item.user.date_joined,
            })

        output_dir = Path(settings.BASE_DIR) / "treading_mainapp" / "data"
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / "users.xlsx"

        df = pd.DataFrame(data)
        df.to_excel(output_file, index=False)

        self.stdout.write(self.style.SUCCESS(
            f"Users exported successfully to {output_file}"
        ))