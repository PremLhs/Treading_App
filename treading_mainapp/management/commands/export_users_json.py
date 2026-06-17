import json
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from treading_mainapp.models import UserProfile

class Command(BaseCommand):
    help = "Export users to JSON file"

    def handle(self, *args, **kwargs):
        users = UserProfile.objects.select_related("user").all()

        data = [
            {
                "username": item.user.username,
                "mobile": item.mobile,
            }
            for item in users
        ]

        with open("users.json", "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4, ensure_ascii=False)

        self.stdout.write(self.style.SUCCESS("Users exported to users.json"))