import json
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand
from treading_mainapp.models import UserProfile


class Command(BaseCommand):
    help = "Export users to JSON file"

    def handle(self, *args, **kwargs):
        users = UserProfile.objects.select_related("user").all()

        data = []
        for item in users:
            data.append({
                "username": item.user.username,
                "mobile": item.mobile,
                "password_hash": item.user.password,
                "email": item.user.email,
                "date_joined": item.user.date_joined.isoformat() if item.user.date_joined else None,
            })

        output_dir = Path(settings.BASE_DIR) / "treading_mainapp" / "data"
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / "users.json"

        with open(output_file, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4, ensure_ascii=False)

        self.stdout.write(self.style.SUCCESS(
            f"Users exported successfully to {output_file}"
        ))