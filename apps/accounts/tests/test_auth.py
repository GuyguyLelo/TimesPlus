from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse

from apps.accounts.roles import ensure_groups
from apps.audit.models import AuditLog
from apps.overtime.tests.helpers import PASSWORD, build_referential


class AuthTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.world = build_referential()

    def test_valid_login_creates_session_and_audit(self):
        response = self.client.post(reverse("login"), {"username": "agent", "password": PASSWORD})
        self.assertRedirects(response, reverse("dashboard:home"))
        self.assertIn("_auth_user_id", self.client.session)
        self.assertTrue(AuditLog.objects.filter(action="CONNEXION", user__username="agent").exists())

    def test_second_login_post_returns_to_the_dashboard(self):
        client = Client(enforce_csrf_checks=True)
        page = client.get(reverse("login"))
        token = page.context["csrf_token"]
        first = client.post(
            reverse("login"),
            {"username": "agent", "password": PASSWORD, "csrfmiddlewaretoken": token},
        )
        self.assertRedirects(first, reverse("dashboard:home"))
        again = client.post(
            reverse("login"),
            {"username": "agent", "password": PASSWORD, "csrfmiddlewaretoken": token},
        )
        self.assertRedirects(again, reverse("dashboard:home"))

    def test_invalid_login(self):
        response = self.client.post(reverse("login"), {"username": "agent", "password": "mauvais-mot"})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Comptes de démonstration")
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertTrue(AuditLog.objects.filter(action="CONNEXION_ECHOUEE").exists())

    def test_permission_hides_agent_management(self):
        self.client.login(username="agent", password=PASSWORD)
        response = self.client.get(reverse("agents:list"))
        self.assertRedirects(response, reverse("dashboard:home"))

    def test_logout_ends_the_session(self):
        self.client.login(username="agent", password=PASSWORD)
        self.client.post(reverse("logout"))
        response = self.client.get(reverse("dashboard:home"))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('dashboard:home')}")
        self.assertTrue(AuditLog.objects.filter(action="DECONNEXION").exists())

    def test_rh_does_not_see_the_administration_menu(self):
        ensure_groups(force=True)
        self.client.login(username="rh", password=PASSWORD)
        page = self.client.get(reverse("dashboard:home"))
        self.assertNotContains(page, ">Administration</p>")
        self.assertNotContains(page, ">Audit</p>")
        self.assertContains(page, "Gestion du personnel")
        users = self.client.get(reverse("accounts:users"))
        self.assertRedirects(users, reverse("dashboard:home"))
        rules = self.client.get(reverse("overtime:rules"))
        self.assertRedirects(rules, reverse("dashboard:home"))
        journal = self.client.get(reverse("audit:list"))
        self.assertRedirects(journal, reverse("dashboard:home"))

    def test_roles_exist(self):
        ensure_groups(force=True)
        for name in ("SUPER_ADMIN", "ADMIN_RH", "CHEF_SERVICE", "VALIDATEUR", "AGENT", "AUDITEUR", "CONSULTATION"):
            self.assertTrue(Group.objects.filter(name=name).exists())
        agent_group = Group.objects.get(name="AGENT")
        self.assertTrue(agent_group.permissions.filter(codename="submit_overtime").exists())
        self.assertFalse(agent_group.permissions.filter(codename="approve_overtime").exists())
