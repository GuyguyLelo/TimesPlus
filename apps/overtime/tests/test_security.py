from datetime import date, time

from django.test import TestCase
from django.urls import reverse

from apps.overtime.models import OvertimeRequest
from apps.overtime.services.declaration import enregistrer_declaration
from apps.overtime.tests.helpers import PASSWORD, build_referential


class SecurityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.world = build_referential()

    def setUp(self):
        self.client.login(username="agent", password=PASSWORD)

    def test_agent_cannot_open_another_service_request(self):
        other, _result = enregistrer_declaration(
            agent=self.world["other"],
            date_travail=date(2026, 10, 8),
            heure_debut=time(17, 0),
            heure_fin=time(18, 0),
            motif="Déclaration RH",
            user=self.world["rh_user"],
        )
        response = self.client.get(reverse("overtime:detail", args=[other.pk]))
        self.assertEqual(response.status_code, 404)

    def test_agent_cannot_approve(self):
        demande = self._own_request()
        self.assertEqual(demande.statut, OvertimeRequest.Statut.APPROUVE)
        response = self.client.post(reverse("workflow:approve", args=[demande.pk]), {"commentaire": "Moi-même"})
        demande.refresh_from_db()
        self.assertEqual(demande.statut, OvertimeRequest.Statut.APPROUVE)
        self.assertEqual(demande.decisions.count(), 0)
        self.assertIn(response.status_code, (302, 403))

    def test_saved_request_stays_editable(self):
        demande = self._own_request()
        response = self.client.get(reverse("overtime:update", args=[demande.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "ne peut plus être modifiée")

    def _own_request(self):
        demande, _result = enregistrer_declaration(
            agent=self.world["agent"],
            date_travail=date(2026, 10, 7),
            heure_debut=time(17, 0),
            heure_fin=time(19, 0),
            motif="Intervention de l'agent",
            user=self.world["agent_user"],
        )
        return demande
