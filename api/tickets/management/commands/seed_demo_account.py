from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.db import transaction


DEMO_USERNAME = "demo"
DEMO_PASSWORD = "ticketdesk-demo-2026"


class Command(BaseCommand):
    help = "Create or reset the shared, limited Agent account used by the public demo."

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        user, created = User.objects.get_or_create(username=DEMO_USERNAME)
        user.is_active = True
        user.is_staff = False
        user.is_superuser = False
        user.set_password(DEMO_PASSWORD)
        user.save()
        user.groups.set([Group.objects.get(name="Agent")])

        action = "created" if created else "reset"
        self.stdout.write(self.style.SUCCESS(f"Demo account {DEMO_USERNAME} {action} with Agent access."))
