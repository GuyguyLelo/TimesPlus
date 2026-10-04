from datetime import date, time

from django.test import TestCase
from django.urls import reverse

from apps.overtime.models import OvertimeRequest, PaiementMois
from apps.overtime.services.calculation import CalculationError
from apps.overtime.services.declaration import enregistrer_declaration
from apps.overtime.tests.helpers import PASSWORD, build_referential


class PaiementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.world = build_referential()

    def test_closing_current_month_archives_and_locks(self):
        self.client.login(username="rh", password=PASSWORD)
        enregistrer_declaration(
            agent=self.world["agent"],
            date_travail=date(2026, 10, 7),
            heure_debut=time(17, 0),
            heure_fin=time(20, 0),
            motif="PERMANENCE",
            user=self.world["rh_user"],
        )
        response = self.client.post(reverse("overtime:payroll_close"), follow=True)
        self.assertContains(response, "octobre 2026 clôturée")
        self.assertContains(response, "Payé")
        demande = OvertimeRequest.objects.get()
        self.assertFalse(demande.editable)
        self.assertFalse(demande.supprimable)
        self.assertTrue(PaiementMois.objects.filter(annee=2026, mois=10).exists())
        blocked = self.client.get(reverse("overtime:update", args=[demande.pk]), follow=True)
        self.assertContains(blocked, "ne peuvent plus être modifiée")
        page = self.client.get(reverse("overtime:create"))
        self.assertNotContains(page, 'value="2026-09"')
        self.assertNotContains(page, 'value="2026-10"')
        self.assertContains(page, 'value="2026-11"')
        refused = self.client.post(
            reverse("overtime:create"),
            {
                "agent": self.world["agent"].pk,
                "mois": "2026-10",
                "date_travail": "2026-10-08",
                "heure_debut": "16:00",
                "heure_fin": "18:00",
                "motif": "PERMANENCE",
            },
        )
        self.assertContains(refused, "clôturé")
        self.assertEqual(OvertimeRequest.objects.count(), 1)
        with self.assertRaises(CalculationError):
            enregistrer_declaration(
                agent=self.world["agent"],
                date_travail=date(2026, 10, 8),
                heure_debut=time(17, 0),
                heure_fin=time(19, 0),
                motif="PERMANENCE",
                user=self.world["rh_user"],
            )
        historique = self.client.get(reverse("reports:historical"))
        self.assertContains(historique, "Octobre 2026")

    def test_agent_cannot_close_payroll(self):
        self.client.login(username="agent", password=PASSWORD)
        response = self.client.post(reverse("overtime:payroll_close"), follow=True)
        self.assertFalse(PaiementMois.objects.exists())
        self.assertContains(response, "pas autorisé")
