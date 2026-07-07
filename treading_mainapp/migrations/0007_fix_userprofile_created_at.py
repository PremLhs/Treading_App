from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("treading_mainapp", "0006_gapscanrun_alter_userprofile_options_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
    ]
