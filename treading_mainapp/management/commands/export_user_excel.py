import pandas as pd
from django.core.management.base import BaseCommand
from treading_mainapp.models import UserProfile

class Command(BaseCommand):
    help = "Export users to Excel file"

    def handle(self, *args, **kwargs):
        users = UserProfile.objects.select_related("user").all()

        data = [
            {
                "username": item.user.username,
                "mobile": item.mobile,
            }
            for item in users
        ]

        df = pd.DataFrame(data)
        df.to_excel("users.xlsx", index=False)

        self.stdout.write(self.style.SUCCESS("Users exported to users.xlsx"))