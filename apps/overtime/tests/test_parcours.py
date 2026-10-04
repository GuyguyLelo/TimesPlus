from datetime import date, time

from django.test import TestCase
from django.urls import reverse

from apps.overtime.models import OvertimeRequest
from apps.overtime.tests.helpers import PASSWORD, build_referential
from apps.reports.models import GeneratedReport


class ParcoursTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.world = build_referential()

    def test_full_path_from_declaration_to_exports(self):
        self.client.login(username="agent", password=PASSWORD)
        response = self.client.post(
            reverse("overtime:create"),
            {
                "agent": self.world["agent"].pk,
                "date_travail": "2026-10-07",
                "heure_debut": "17:00",
                "heure_fin": "20:30",
                "motif": "PERMANENCE",
            },
            follow=True,
        )
        self.assertContains(response, "Saisie enregistrée sur la liste")
        demande = OvertimeRequest.objects.get(agent=self.world["agent"])
        self.assertEqual(demande.heure_debut, time(16, 0))
        self.assertEqual(demande.duree_minutes, 270)
        self.assertEqual(demande.type_heure.code, "HEURE_NUIT")
        self.assertEqual(demande.statut, OvertimeRequest.Statut.APPROUVE)
        self.assertIsNotNone(demande.approved_at)

        preview = self.client.get(
            reverse("overtime:preview"),
            {
                "date": "2026-10-07",
                "heure_debut": "17:00",
                "heure_fin": "20:30",
                "agent": self.world["agent"].pk,
                "exclude": demande.pk,
            },
        )
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.json()["minutes"], 210)

        self.client.logout()
        self.client.login(username="rh", password=PASSWORD)
        query = "?debut=2026-10-01&fin=2026-10-31&kind=ADMINISTRATIF"
        pdf = self.client.get(reverse("reports:pdf") + query)
        excel = self.client.get(reverse("reports:excel") + "?debut=2026-10-01&fin=2026-10-31")
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.content.startswith(b"%PDF"))
        self.assertEqual(excel.status_code, 200)
        self.assertGreater(GeneratedReport.objects.count(), 0)
        self.assertEqual(date(2026, 10, 7).weekday(), 2)
        self.assertEqual(demande.heure_debut, time(16, 0))
