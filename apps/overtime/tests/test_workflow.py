from datetime import date, time

from django.test import TestCase

from apps.overtime.models import OvertimeRequest
from apps.overtime.services.declaration import enregistrer_declaration
from apps.overtime.tests.helpers import build_referential
from apps.workflow.services import WorkflowError, approuver, rejeter, soumettre


class WorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.world = build_referential()

    def _create(self):
        demande, _result = enregistrer_declaration(
            agent=self.world["agent"],
            date_travail=date(2026, 10, 7),
            heure_debut=time(17, 0),
            heure_fin=time(19, 0),
            motif="Intervention planifiée",
            user=self.world["agent_user"],
        )
        demande.statut = OvertimeRequest.Statut.BROUILLON
        demande.approved_at = None
        demande.save(update_fields=["statut", "approved_at"])
        return demande

    def test_submit_then_two_approvals(self):
        demande = self._create()
        soumettre(demande, self.world["agent_user"])
        demande.refresh_from_db()
        self.assertEqual(demande.statut, OvertimeRequest.Statut.EN_VALIDATION)
        self.assertEqual(demande.current_step.code, "CHEF_SERVICE")
        approuver(demande, self.world["chef_user"], commentaire="Vu.")
        demande.refresh_from_db()
        self.assertEqual(demande.statut, OvertimeRequest.Statut.EN_VALIDATION)
        self.assertEqual(demande.current_step.code, "VALIDATION_RH")
        approuver(demande, self.world["rh_user"], commentaire="Accord RH.")
        demande.refresh_from_db()
        self.assertEqual(demande.statut, OvertimeRequest.Statut.APPROUVE)
        self.assertIsNotNone(demande.approved_at)
        self.assertEqual(demande.decisions.count(), 2)

    def test_reject_requires_a_reason_and_sets_status(self):
        demande = self._create()
        soumettre(demande, self.world["agent_user"])
        demande.refresh_from_db()
        with self.assertRaises(WorkflowError):
            rejeter(demande, self.world["chef_user"], commentaire="  ")
        rejeter(demande, self.world["chef_user"], commentaire="Pièce manquante.")
        demande.refresh_from_db()
        self.assertEqual(demande.statut, OvertimeRequest.Statut.REJETE)
        self.assertIn("Pièce manquante.", demande.decisions.get().commentaire)

    def test_agent_cannot_approve_own_request(self):
        demande = self._create()
        soumettre(demande, self.world["agent_user"])
        demande.refresh_from_db()
        with self.assertRaises(WorkflowError):
            approuver(demande, self.world["agent_user"])

    def test_chef_cannot_approve_another_service(self):
        demande, _result = enregistrer_declaration(
            agent=self.world["other"],
            date_travail=date(2026, 10, 7),
            heure_debut=time(17, 0),
            heure_fin=time(19, 0),
            motif="Travail du service RH",
            user=self.world["rh_user"],
        )
        demande.statut = OvertimeRequest.Statut.BROUILLON
        demande.approved_at = None
        demande.save(update_fields=["statut", "approved_at"])
        soumettre(demande, self.world["rh_user"])
        demande.refresh_from_db()
        with self.assertRaises(WorkflowError):
            approuver(demande, self.world["chef_user"], commentaire="Hors périmètre.")
