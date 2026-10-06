from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.overtime.models import ListePresence, OvertimeRequest
from apps.overtime.tests.helpers import PASSWORD, build_referential

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"


def _pdf(name="liste-signee.pdf"):
    return SimpleUploadedFile(name, PDF, content_type="application/pdf")


class PresenceListTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        build_referential()

    def test_menu_shows_the_presence_list(self):
        self.client.login(username="rh", password=PASSWORD)
        response = self.client.get(reverse("dashboard:home"))
        self.assertContains(response, "Liste des présences")
        self.assertContains(response, reverse("overtime:presences"))

    def test_signed_list_is_attached_to_a_date(self):
        self.client.login(username="rh", password=PASSWORD)
        response = self.client.post(
            reverse("overtime:presence_create"),
            {"date": "2026-10-05", "effectifs": "12", "fichier": _pdf()},
        )
        self.assertRedirects(response, reverse("overtime:presences"))
        liste = ListePresence.objects.get(date=date(2026, 10, 5))
        self.assertEqual(liste.nom_original, "liste-signee.pdf")
        self.assertEqual(liste.effectifs, 12)
        page = self.client.get(reverse("overtime:presences"))
        self.assertContains(page, "05/10/2026")
        self.assertContains(page, "liste-signee.pdf")
        self.assertContains(page, ">12<")
        saisie = self.client.get(reverse("overtime:create") + "?date=2026-10-05")
        self.assertContains(saisie, 'name="effectifs"')
        self.assertContains(saisie, 'value="12"')
        self.assertContains(saisie, "readonly")
        lookup = self.client.get(reverse("overtime:presence_headcount") + "?date=2026-10-05")
        self.assertEqual(lookup.json()["effectifs"], 12)
        download = self.client.get(reverse("overtime:presence_download", args=[liste.pk]))
        self.assertEqual(download.status_code, 200)
        self.assertIn(b"%PDF", b"".join(download.streaming_content))

    def test_a_date_accepts_only_one_list(self):
        self.client.login(username="rh", password=PASSWORD)
        self.client.post(
            reverse("overtime:presence_create"),
            {"date": "2026-10-06", "effectifs": "8", "fichier": _pdf()},
        )
        again = self.client.post(
            reverse("overtime:presence_create"),
            {"date": "2026-10-06", "effectifs": "8", "fichier": _pdf("autre.pdf")},
        )
        self.assertEqual(again.status_code, 200)
        self.assertContains(again, "déjà une liste de présence")
        self.assertEqual(ListePresence.objects.filter(date=date(2026, 10, 6)).count(), 1)

    def test_rejected_extension_is_refused(self):
        self.client.login(username="rh", password=PASSWORD)
        fichier = SimpleUploadedFile("liste.exe", b"MZ", content_type="application/octet-stream")
        response = self.client.post(
            reverse("overtime:presence_create"),
            {"date": "2026-10-07", "effectifs": "4", "fichier": fichier},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ListePresence.objects.count(), 0)

    def test_agent_count_is_not_limited_by_the_list_headcount(self):
        from apps.agents.models import Agent

        self.client.login(username="rh", password=PASSWORD)
        created = self.client.post(
            reverse("overtime:presence_create"),
            {"date": "2026-10-08", "effectifs": "1", "fichier": _pdf()},
        )
        self.assertRedirects(created, reverse("overtime:presences"))
        agents = list(Agent.objects.order_by("pk")[:2])
        payload = {
            "date_travail": "2026-10-08",
            "heure_debut": "16:00",
            "heure_fin": "18:00",
            "motif": "PERMANENCE",
            "mois": "2026-10",
        }
        first = self.client.post(reverse("overtime:create"), {**payload, "agent": agents[0].pk})
        second = self.client.post(reverse("overtime:create"), {**payload, "agent": agents[1].pk})
        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        self.assertEqual(OvertimeRequest.objects.filter(date_travail=date(2026, 10, 8)).count(), 2)

    def test_saisie_does_not_require_the_joined_list(self):
        from apps.agents.models import Agent

        self.client.login(username="rh", password=PASSWORD)
        agent = Agent.objects.order_by("pk").first()
        response = self.client.post(
            reverse("overtime:create"),
            {
                "agent": agent.pk,
                "date_travail": "2026-10-09",
                "effectifs": "3",
                "heure_debut": "16:00",
                "heure_fin": "18:00",
                "motif": "PERMANENCE",
                "mois": "2026-10",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(OvertimeRequest.objects.filter(date_travail=date(2026, 10, 9)).count(), 1)

    def test_presence_list_is_edited_instead_of_deleted(self):
        self.client.login(username="rh", password=PASSWORD)
        created = self.client.post(
            reverse("overtime:presence_create"),
            {"date": "2026-10-04", "effectifs": "6", "fichier": _pdf()},
        )
        self.assertRedirects(created, reverse("overtime:presences"))
        liste = ListePresence.objects.get(date=date(2026, 10, 4))
        page = self.client.get(reverse("overtime:presences"))
        self.assertContains(page, "Modifier")
        self.assertNotContains(page, "Supprimer")
        form = self.client.get(reverse("overtime:presence_update", args=[liste.pk]))
        self.assertContains(form, "liste-signee.pdf")
        updated = self.client.post(
            reverse("overtime:presence_update", args=[liste.pk]),
            {"date": "2026-10-04", "effectifs": "9"},
        )
        self.assertRedirects(updated, reverse("overtime:presences"))
        liste.refresh_from_db()
        self.assertEqual(liste.effectifs, 9)
        self.assertEqual(liste.nom_original, "liste-signee.pdf")
