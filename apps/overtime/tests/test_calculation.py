from datetime import time

from django.test import SimpleTestCase, TestCase

from apps.overtime.models import Holiday
from apps.overtime.services.calculation import (
    MSG_CHEVAUCHEMENT,
    MSG_FIN_AVANT_DEBUT,
    MSG_PLAFOND,
    CalculationError,
    calculer_declaration,
    compute_duration_minutes,
)
from apps.overtime.services.declaration import enregistrer_declaration
from apps.overtime.tests.helpers import PASSWORD, build_referential
from apps.settings_app.models import SiteSettings


class DurationTests(SimpleTestCase):
    def test_three_hours(self):
        self.assertEqual(compute_duration_minutes(time(17, 0), time(20, 0)), 180)

    def test_three_hours_thirty(self):
        self.assertEqual(compute_duration_minutes(time(17, 0), time(20, 30)), 210)

    def test_end_before_start(self):
        with self.assertRaises(CalculationError) as caught:
            compute_duration_minutes(time(20, 0), time(17, 0))
        self.assertEqual(caught.exception.message, MSG_FIN_AVANT_DEBUT)

    def test_zero_duration(self):
        with self.assertRaises(CalculationError):
            compute_duration_minutes(time(18, 0), time(18, 0))


class ClassificationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.world = build_referential()

    def test_mixed_evening_is_detected_from_rules(self):
        result = calculer_declaration(self.world["agent"], self._wednesday(), time(17, 0), time(20, 30))
        self.assertEqual(result.duree_minutes, 210)
        self.assertEqual(result.type_code, "HEURE_NUIT")
        self.assertEqual(sum(item["minutes"] for item in result.ventilation), 210)
        self.assertEqual(len(result.ventilation), 2)
        self.assertEqual(result.coefficient, 2)

    def test_weekend_uses_weekend_rule(self):
        result = calculer_declaration(self.world["agent"], self._saturday(), time(9, 0), time(12, 0))
        self.assertEqual(result.type_code, "HEURE_WEEKEND")
        self.assertEqual(result.duree_minutes, 180)

    def test_holiday_uses_holiday_rule(self):
        day = self._thursday()
        Holiday.objects.create(date=day, libelle="Fête de test", actif=True)
        result = calculer_declaration(self.world["agent"], day, time(9, 0), time(11, 0))
        self.assertEqual(result.type_code, "HEURE_FERIE")
        self.assertEqual(result.montant_estime, 20000)

    def test_overlap_is_rejected(self):
        day = self._wednesday()
        enregistrer_declaration(
            agent=self.world["agent"],
            date_travail=day,
            heure_debut=time(17, 0),
            heure_fin=time(19, 0),
            motif="Première déclaration",
            user=self.world["agent_user"],
        )
        with self.assertRaises(CalculationError) as caught:
            calculer_declaration(self.world["agent"], day, time(18, 0), time(20, 0))
        self.assertEqual(caught.exception.message, MSG_CHEVAUCHEMENT)

    def test_ceiling_is_configurable(self):
        settings_obj = SiteSettings.load()
        settings_obj.plafond_journalier_minutes = 60
        settings_obj.save()
        with self.assertRaises(CalculationError) as caught:
            calculer_declaration(self.world["agent"], self._wednesday(), time(17, 0), time(19, 0))
        self.assertEqual(caught.exception.message, MSG_PLAFOND)

    def _wednesday(self):
        from datetime import date

        return date(2026, 10, 7)

    def _thursday(self):
        from datetime import date

        return date(2026, 10, 8)

    def _saturday(self):
        from datetime import date

        return date(2026, 10, 3)
