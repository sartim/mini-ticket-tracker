from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Assign one ticket tracker role to a user. Run migrate first."

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("--role", choices=("Admin", "Agent", "Viewer"), required=True)

    def handle(self, *args, **options):
        username = options["username"]
        role = options["role"]
        User = get_user_model()
        try:
            user = User.objects.get(**{User.USERNAME_FIELD: username})
        except User.DoesNotExist as exc:
            raise CommandError(
                f"No user found for {User.USERNAME_FIELD} '{username}'."
            ) from exc

        try:
            group = Group.objects.get(name=role)
        except Group.DoesNotExist as exc:
            raise CommandError(
                "Ticket roles are not initialized. Run `python manage.py migrate` first."
            ) from exc

        user.groups.set([group])
        self.stdout.write(self.style.SUCCESS(f"Assigned {role} role to {username}."))
