from django.contrib.auth.models import Group, Permission, User
from django.test import Client, TestCase
from django.urls import reverse

from apps.accounts.roles import ensure_groups
from apps.audit.models import AuditLog
from apps.overtime.tests.helpers import PASSWORD, build_referential, make_user


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

    def test_superuser_can_delete_another_user(self):
        admin = make_user("admin", "SUPER_ADMIN", superuser=True)
        self.client.login(username="admin", password=PASSWORD)
        cible = User.objects.get(username="agent")
        page = self.client.get(reverse("accounts:users"))
        self.assertContains(page, reverse("accounts:user_delete", args=[cible.pk]))
        self.assertNotContains(page, reverse("accounts:user_delete", args=[admin.pk]))
        confirm = self.client.get(reverse("accounts:user_delete", args=[cible.pk]))
        self.assertContains(confirm, "Confirmez la suppression du compte agent")
        done = self.client.post(reverse("accounts:user_delete", args=[cible.pk]))
        self.assertRedirects(done, reverse("accounts:users"))
        self.assertFalse(User.objects.filter(username="agent").exists())
        self.assertTrue(AuditLog.objects.filter(action="SUPPRESSION", model_name="User", object_id=str(cible.pk)).exists())
        soi = self.client.post(reverse("accounts:user_delete", args=[admin.pk]))
        self.assertRedirects(soi, reverse("accounts:users"))
        self.assertTrue(User.objects.filter(username="admin").exists())

    def test_superuser_manages_groups(self):
        make_user("admin", "SUPER_ADMIN", superuser=True)
        self.client.login(username="admin", password=PASSWORD)
        permission = Permission.objects.get(codename="view_agent", content_type__app_label="agents")
        membre = User.objects.get(username="agent")
        created = self.client.post(
            reverse("accounts:group_create"),
            {"name": "CELLULE", "permissions": [permission.pk], "membres": [membre.pk]},
        )
        groupe = Group.objects.get(name="CELLULE")
        self.assertRedirects(created, reverse("accounts:group_detail", args=[groupe.pk]))
        self.assertTrue(groupe.permissions.filter(pk=permission.pk).exists())
        self.assertTrue(membre.groups.filter(pk=groupe.pk).exists())
        listing = self.client.get(reverse("accounts:groups"))
        self.assertContains(listing, "Nouveau groupe")
        self.assertContains(listing, reverse("accounts:group_delete", args=[groupe.pk]))
        role = Group.objects.get(name="ADMIN_RH")
        self.assertNotContains(listing, reverse("accounts:group_delete", args=[role.pk]))
        renamed = self.client.post(
            reverse("accounts:group_update", args=[groupe.pk]),
            {"name": "CELLULE-2", "permissions": [permission.pk]},
        )
        self.assertRedirects(renamed, reverse("accounts:group_detail", args=[groupe.pk]))
        groupe.refresh_from_db()
        self.assertEqual(groupe.name, "CELLULE-2")
        self.assertFalse(membre.groups.filter(pk=groupe.pk).exists())
        deleted = self.client.post(reverse("accounts:group_delete", args=[groupe.pk]))
        self.assertRedirects(deleted, reverse("accounts:groups"))
        self.assertFalse(Group.objects.filter(pk=groupe.pk).exists())
        refused = self.client.post(reverse("accounts:group_delete", args=[role.pk]))
        self.assertRedirects(refused, reverse("accounts:group_detail", args=[role.pk]))
        self.assertTrue(Group.objects.filter(name="ADMIN_RH").exists())
        edition = self.client.get(reverse("accounts:group_update", args=[role.pk]))
        self.assertContains(edition, "disabled")
        self.assertContains(edition, "Permissions")
        self.assertContains(edition, "Membres")
        self.assertContains(edition, 'class="perm-fr"')
        self.assertContains(edition, "Peut consulter agent")
        self.assertContains(edition, "Peut ajouter utilisateur")

    def test_user_edit_form_is_grouped(self):
        make_user("admin", "SUPER_ADMIN", superuser=True)
        self.client.login(username="admin", password=PASSWORD)
        cible = User.objects.get(username="rh")
        page = self.client.get(reverse("accounts:user_update", args=[cible.pk]))
        self.assertContains(page, "Identité")
        self.assertContains(page, "Mot de passe")
        self.assertContains(page, "Rôles et accès")
        self.assertContains(page, "Rattachement")
        self.assertContains(page, "code-chip")
        self.assertContains(page, "role-picks")
        self.assertContains(page, "Laissez vide pour conserver le mot de passe actuel.")

    def test_rh_cannot_delete_a_user(self):
        self.client.login(username="rh", password=PASSWORD)
        cible = User.objects.get(username="agent")
        page = self.client.get(reverse("accounts:users"))
        self.assertRedirects(page, reverse("dashboard:home"))
        done = self.client.post(reverse("accounts:user_delete", args=[cible.pk]))
        self.assertRedirects(done, reverse("dashboard:home"))
        self.assertTrue(User.objects.filter(username="agent").exists())

    def test_roles_exist(self):
        ensure_groups(force=True)
        for name in ("SUPER_ADMIN", "ADMIN_RH", "CHEF_SERVICE", "VALIDATEUR", "AGENT", "AUDITEUR", "CONSULTATION"):
            self.assertTrue(Group.objects.filter(name=name).exists())
        agent_group = Group.objects.get(name="AGENT")
        self.assertTrue(agent_group.permissions.filter(codename="submit_overtime").exists())
        self.assertFalse(agent_group.permissions.filter(codename="approve_overtime").exists())
