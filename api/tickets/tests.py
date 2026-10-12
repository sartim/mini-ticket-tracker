from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APITestCase

from .models import Ticket


class TicketApiTests(APITestCase):
    api = "/api/v1"

    def setUp(self):
        user = get_user_model().objects.create_user(username="ticket-api-test")
        user.groups.add(Group.objects.get(name="Agent"))
        self.client.force_authenticate(user=user)

    def test_create_ticket_defaults_and_rejects_invalid_input(self):
        created = self.client.post(
            f"{self.api}/tickets", {"title": "Cannot sign in", "description": "Login times out"}, format="json"
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.data["status"], Ticket.Status.OPEN)
        self.assertEqual(created.data["priority"], Ticket.Priority.MEDIUM)

        invalid = self.client.post(f"{self.api}/tickets", {"title": ""}, format="json")
        self.assertEqual(invalid.status_code, 400)
        self.assertIn("error", invalid.data)

    def test_list_filters_and_paginates_tickets(self):
        Ticket.objects.create(title="Open item")
        Ticket.objects.create(title="Another open item")
        Ticket.objects.create(title="Closed item", status=Ticket.Status.CLOSED)

        response = self.client.get(f"{self.api}/tickets?status=open&page=1&limit=1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)
        self.assertIsNotNone(response.data["next"])
        self.assertIsNone(response.data["previous"])
        next_page = self.client.get(response.data["next"])
        self.assertEqual(next_page.status_code, 200)
        self.assertEqual(next_page.data["count"], 2)
        self.assertIsNotNone(next_page.data["previous"])

    def test_invalid_filter_and_pagination_are_rejected(self):
        self.assertEqual(self.client.get(f"{self.api}/tickets?status=waiting").status_code, 400)
        self.assertEqual(self.client.get(f"{self.api}/tickets?page=0").status_code, 404)

    def test_patch_updates_fields_and_stats_include_zero_statuses(self):
        ticket = Ticket.objects.create(title="Password reset")
        response = self.client.patch(
            f"{self.api}/tickets/{ticket.id}",
            {"status": Ticket.Status.IN_PROGRESS, "priority": Ticket.Priority.HIGH},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], Ticket.Status.IN_PROGRESS)
        self.assertEqual(response.data["priority"], Ticket.Priority.HIGH)
        self.assertEqual(
            self.client.get(f"{self.api}/tickets/stats").data,
            {"open": 0, "in_progress": 1, "closed": 0},
        )

    def test_unknown_ticket_returns_404(self):
        response = self.client.patch(
            f"{self.api}/tickets/999", {"status": "closed"}, format="json"
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("error", response.data)


class AuthenticationApiTests(APITestCase):
    api = "/api/v1"

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="auth-api-test", password="test-password"
        )
        self.user.groups.add(Group.objects.get(name="Agent"))

    def test_login_returns_access_and_user_with_role_and_permission_objects(self):
        response = self.client.post(
            f"{self.api}/auth/token",
            {"username": "auth-api-test", "password": "test-password"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertEqual(response.data["user"]["username"], "auth-api-test")
        self.assertEqual(response.data["user"]["roles"], [{"name": "Agent"}])
        self.assertTrue(
            any(permission["code"] == "tickets.view_ticket" for permission in response.data["user"]["permissions"])
        )
        self.assertNotIn("refresh", response.data)

    def test_login_error_uses_error_key(self):
        response = self.client.post(
            f"{self.api}/auth/token",
            {"username": "auth-api-test", "password": "incorrect"},
            format="json",
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("error", response.data)

    def test_refresh_returns_access_and_user(self):
        self.client.post(
            f"{self.api}/auth/token",
            {"username": "auth-api-test", "password": "test-password"},
            format="json",
        )
        response = self.client.post(f"{self.api}/auth/token/refresh")
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertEqual(response.data["user"]["id"], self.user.pk)


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
