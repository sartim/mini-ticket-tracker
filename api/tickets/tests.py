from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APITestCase

from .models import Ticket


class TicketApiTests(APITestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username="ticket-api-test")
        user.groups.add(Group.objects.get(name="Agent"))
        self.client.force_authenticate(user=user)

    def test_create_ticket_defaults_and_rejects_invalid_input(self):
        created = self.client.post(
            "/tickets", {"title": "Cannot sign in", "description": "Login times out"}, format="json"
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.data["status"], Ticket.Status.OPEN)
        self.assertEqual(created.data["priority"], Ticket.Priority.MEDIUM)

        invalid = self.client.post("/tickets", {"title": ""}, format="json")
        self.assertEqual(invalid.status_code, 400)

    def test_list_filters_and_paginates_tickets(self):
        Ticket.objects.create(title="Open item")
        Ticket.objects.create(title="Closed item", status=Ticket.Status.CLOSED)

        response = self.client.get("/tickets?status=open&page=1&limit=1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total"], 1)
        self.assertEqual(response.data["tickets"][0]["title"], "Open item")

    def test_invalid_filter_and_pagination_are_rejected(self):
        self.assertEqual(self.client.get("/tickets?status=waiting").status_code, 400)
        self.assertEqual(self.client.get("/tickets?page=0").status_code, 404)

    def test_patch_updates_fields_and_stats_include_zero_statuses(self):
        ticket = Ticket.objects.create(title="Password reset")
        response = self.client.patch(
            f"/tickets/{ticket.id}",
            {"status": Ticket.Status.IN_PROGRESS, "priority": Ticket.Priority.HIGH},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], Ticket.Status.IN_PROGRESS)
        self.assertEqual(response.data["priority"], Ticket.Priority.HIGH)
        self.assertEqual(
            self.client.get("/tickets/stats").data,
            {"open": 0, "in_progress": 1, "closed": 0},
        )

    def test_unknown_ticket_returns_404(self):
        response = self.client.patch(
            "/tickets/999", {"status": "closed"}, format="json"
        )
        self.assertEqual(response.status_code, 404)


class SeedDemoDataCommandTests(TestCase):
    def test_command_creates_demo_tickets_across_statuses_and_priorities(self):
        output = StringIO()

        call_command("seed_demo_data", stdout=output)

        self.assertEqual(Ticket.objects.filter(title__startswith="Demo:").count(), 9)
        demo_tickets = Ticket.objects.filter(title__startswith="Demo:")
        self.assertEqual(
            set(demo_tickets.values_list("status", flat=True)),
            {Ticket.Status.OPEN, Ticket.Status.IN_PROGRESS, Ticket.Status.CLOSED},
        )
        self.assertEqual(
            set(demo_tickets.values_list("priority", flat=True)),
            {Ticket.Priority.LOW, Ticket.Priority.MEDIUM, Ticket.Priority.HIGH},
        )
        self.assertIn("9 created, 0 already existed", output.getvalue())

    def test_command_is_idempotent_and_does_not_overwrite_existing_demo_ticket(self):
        existing = Ticket.objects.create(
            title="Demo: Customer portal login is failing",
            description="Keep this description",
            status=Ticket.Status.CLOSED,
            priority=Ticket.Priority.LOW,
        )
        output = StringIO()

        call_command("seed_demo_data", stdout=output)
        call_command("seed_demo_data", stdout=output)

        self.assertEqual(Ticket.objects.filter(title__startswith="Demo:").count(), 9)
        existing.refresh_from_db()
        self.assertEqual(existing.description, "Keep this description")
        self.assertEqual(existing.status, Ticket.Status.CLOSED)
        self.assertEqual(existing.priority, Ticket.Priority.LOW)
        self.assertIn("8 created, 1 already existed", output.getvalue())
        self.assertIn("0 created, 9 already existed", output.getvalue())
