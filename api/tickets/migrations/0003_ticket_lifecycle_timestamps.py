import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("tickets", "0002_seed_ticket_roles")]

    operations = [
        migrations.AddField(
            model_name="ticket",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="ticket",
            name="deleted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
