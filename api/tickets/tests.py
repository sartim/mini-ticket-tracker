from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
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

    def test_browsable_api_ui_renders_for_a_session_authenticated_browser(self):
        user = get_user_model().objects.create_user(
            username="browser-api-test", password="test-password"
        )
        user.groups.add(Group.objects.get(name="Agent"))
        ticket = Ticket.objects.create(title="Browsable API test ticket")
        self.client.force_authenticate(user=None)
        self.client.force_login(user)

        login_page = self.client.get("/api/v1/session-auth/login/")
        response = self.client.get(f"{self.api}/tickets", HTTP_ACCEPT="text/html")

        self.assertEqual(login_page.status_code, 200)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("text/html"))
        self.assertContains(response, ticket.title)

        stylesheet = self.client.get(
            "/api/static/rest_framework/css/bootstrap.min.css"
        )
        self.assertEqual(stylesheet.status_code, 200)
        self.assertTrue(stylesheet["Content-Type"].startswith("text/css"))

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

    def test_search_matches_displayed_ticket_codes_and_stats(self):
        open_ticket = Ticket.objects.create(title="Alpha request")
        Ticket.objects.create(title="Bravo request", status=Ticket.Status.CLOSED)
        large_id_ticket = Ticket.objects.create(id=10000, title="Gamma request")

        prefix = self.client.get(f"{self.api}/tickets?search=TK")
        self.assertEqual(prefix.status_code, 200)
        self.assertEqual(prefix.data["count"], 3)

        code = f"TKT-{open_ticket.id:04d}"
        exact_code = self.client.get(f"{self.api}/tickets?search={code.lower()}")
        self.assertEqual(exact_code.data["count"], 1)
        self.assertEqual(exact_code.data["results"][0]["id"], open_ticket.id)
        self.assertEqual(
            self.client.get(f"{self.api}/tickets/stats?search={code}").data,
            {"open": 1, "in_progress": 0, "closed": 0},
        )

        large_code = self.client.get(f"{self.api}/tickets?search=TKT-{large_id_ticket.id}")
        self.assertEqual(large_code.data["count"], 1)
        self.assertEqual(large_code.data["results"][0]["id"], large_id_ticket.id)

    def test_invalid_filter_and_pagination_are_rejected(self):
        self.assertEqual(self.client.get(f"{self.api}/tickets?status=waiting").status_code, 400)
        self.assertEqual(self.client.get(f"{self.api}/tickets?page=0").status_code, 404)

    def test_patch_updates_fields_and_stats_include_zero_statuses(self):
        ticket = Ticket.objects.create(title="Password reset")
        previous_update = timezone.now() - timedelta(days=1)
        Ticket.all_objects.filter(pk=ticket.pk).update(updated_at=previous_update)
        response = self.client.patch(
            f"{self.api}/tickets/{ticket.id}",
            {"status": Ticket.Status.IN_PROGRESS, "priority": Ticket.Priority.HIGH},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], Ticket.Status.IN_PROGRESS)
        self.assertEqual(response.data["priority"], Ticket.Priority.HIGH)
        self.assertGreater(response.data["updated_at"], previous_update.isoformat())
        self.assertIsNone(response.data["deleted_at"])
        self.assertIn("created_at", response.data)
        self.assertEqual(
            self.client.get(f"{self.api}/tickets/stats").data,
            {"open": 0, "in_progress": 1, "closed": 0},
        )

    def test_delete_soft_deletes_ticket_and_hides_it_from_active_queries(self):
        admin = get_user_model().objects.create_user(username="ticket-admin-test")
        admin.groups.add(Group.objects.get(name="Admin"))
        self.client.force_authenticate(user=admin)
        ticket = Ticket.objects.create(title="Request to remove")

        response = self.client.delete(f"{self.api}/tickets/{ticket.id}")

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.data["deleted_at"])
        self.assertFalse(Ticket.objects.filter(pk=ticket.pk).exists())
        stored = Ticket.all_objects.get(pk=ticket.pk)
        self.assertIsNotNone(stored.deleted_at)
        self.assertGreaterEqual(stored.updated_at, stored.deleted_at)
        self.assertEqual(self.client.get(f"{self.api}/tickets").data["count"], 0)
        self.assertEqual(self.client.get(f"{self.api}/tickets/stats").data["open"], 0)
        self.assertEqual(self.client.get(f"{self.api}/tickets/{ticket.id}").status_code, 404)

    def test_agent_cannot_soft_delete_tickets(self):
        ticket = Ticket.objects.create(title="Protected request")

        response = self.client.delete(f"{self.api}/tickets/{ticket.id}")

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Ticket.objects.filter(pk=ticket.pk).exists())

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

    def test_viewer_can_read_but_cannot_create_tickets(self):
        viewer = get_user_model().objects.create_user(username="viewer-api-test")
        viewer.groups.add(Group.objects.get(name="Viewer"))
        self.client.force_authenticate(user=viewer)

        self.assertEqual(self.client.get(f"{self.api}/tickets").status_code, 200)
        denied = self.client.post(
            f"{self.api}/tickets", {"title": "Not allowed"}, format="json"
        )
        self.assertEqual(denied.status_code, 403)
        self.assertIn("error", denied.data)

    def test_logout_clears_refresh_cookie_and_sign_in_session(self):
        login = self.client.post(
            f"{self.api}/auth/token",
            {"username": "auth-api-test", "password": "test-password"},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        response = self.client.post(f"{self.api}/auth/logout")

        self.assertEqual(response.status_code, 205)
        self.assertIn("ticket_desk_refresh", response.cookies)
        self.assertEqual(response.cookies["ticket_desk_refresh"]["max-age"], 0)


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

    def test_seed_demo_account_creates_limited_agent_and_is_repeatable(self):
        output = StringIO()

        call_command("seed_demo_account", stdout=output)
        call_command("seed_demo_account", stdout=output)

        user = get_user_model().objects.get(username="demo")
        self.assertTrue(user.check_password("ticketdesk-demo-2026"))
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_staff)
        self.assertEqual(list(user.groups.values_list("name", flat=True)), ["Agent"])
        self.assertIn("created with Agent access", output.getvalue())
        self.assertIn("reset with Agent access", output.getvalue())
