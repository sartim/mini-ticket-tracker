from django.core.management.base import BaseCommand
from django.db import transaction

from tickets.models import Ticket


DEMO_TICKETS = (
    {
        "title": "Demo: Customer portal login is failing",
        "description": "Several customers are seeing an error after entering their password.",
        "status": Ticket.Status.OPEN,
        "priority": Ticket.Priority.HIGH,
    },
    {
        "title": "Demo: Password reset email is delayed",
        "description": "Reset messages are arriving several minutes after they are requested.",
        "status": Ticket.Status.OPEN,
        "priority": Ticket.Priority.MEDIUM,
    },
    {
        "title": "Demo: Update the billing contact",
        "description": "The account owner needs to replace the billing contact email.",
        "status": Ticket.Status.OPEN,
        "priority": Ticket.Priority.LOW,
    },
    {
        "title": "Demo: Inventory sync is running behind",
        "description": "The overnight inventory sync has not completed for two branches.",
        "status": Ticket.Status.IN_PROGRESS,
        "priority": Ticket.Priority.HIGH,
    },
    {
        "title": "Demo: Mobile app closes during startup",
        "description": "The Android app closes after the splash screen on older devices.",
        "status": Ticket.Status.IN_PROGRESS,
        "priority": Ticket.Priority.HIGH,
    },
    {
        "title": "Demo: Office printer queue is stuck",
        "description": "Documents remain queued after the printer reconnects to Wi-Fi.",
        "status": Ticket.Status.IN_PROGRESS,
        "priority": Ticket.Priority.MEDIUM,
    },
    {
        "title": "Demo: Invoice export includes duplicate rows",
        "description": "A fix was applied to remove repeated invoice lines from CSV exports.",
        "status": Ticket.Status.CLOSED,
        "priority": Ticket.Priority.MEDIUM,
    },
    {
        "title": "Demo: Email notifications are restored",
        "description": "The mail provider connection was renewed and delivery is healthy.",
        "status": Ticket.Status.CLOSED,
        "priority": Ticket.Priority.LOW,
    },
    {
        "title": "Demo: VPN disconnects during long calls",
        "description": "A gateway timeout setting was adjusted and verified with the team.",
        "status": Ticket.Status.CLOSED,
        "priority": Ticket.Priority.HIGH,
    },
)


class Command(BaseCommand):
    help = "Create example support tickets for exploring the board. Safe to run repeatedly."

    @transaction.atomic
    def handle(self, *args, **options):
        created = 0
        existing = 0
        for ticket_data in DEMO_TICKETS:
            _, was_created = Ticket.objects.get_or_create(
                title=ticket_data["title"], defaults=ticket_data
            )
            created += int(was_created)
            existing += int(not was_created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Demo tickets: {created} created, {existing} already existed."
            )
        )
