from datetime import date, time
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.agents.models import Bareme, Fonction, Grade
from apps.overtime.services.calculation import MSG_SANS_BAREME, CalculationError, calculer_declaration
from apps.overtime.tests.helpers import PASSWORD, build_referential


class BaremeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.world = build_referential()

    def test_agent_form_has_no_hourly_rate(self):
        self.client.login(username="rh", password=PASSWORD)
        response = self.client.get(reverse("agents:create"))
        self.assertNotContains(response, "id_taux_horaire")
        self.assertContains(response, "barème")

    def test_scale_page_lists_the_rate(self):
        self.client.login(username="rh", password=PASSWORD)
        response = self.client.get(reverse("agents:bareme"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "5 000,00")
        self.assertContains(response, "échelon 1")

    def test_menu_links_the_scale_under_parameters(self):
        self.client.login(username="rh", password=PASSWORD)
        response = self.client.get(reverse("dashboard:home"))
        self.assertContains(response, reverse("agents:bareme"))

    def test_agent_cannot_open_the_scale(self):
        self.client.login(username="agent", password=PASSWORD)
        response = self.client.get(reverse("agents:bareme"))
        self.assertEqual(response.status_code, 302)

    def test_duplicate_grade_and_function_is_rejected(self):
        self.client.login(username="rh", password=PASSWORD)
        grade = Grade.objects.get(code="AA2-1")
        fonction = Fonction.objects.get(code="AA2")
        response = self.client.post(
            reverse("agents:bareme_create"),
            {"grade": grade.pk, "fonction": fonction.pk, "taux_horaire": "9000", "actif": "on"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "existe déjà")
        self.assertEqual(Bareme.objects.filter(grade=grade, fonction=fonction).count(), 1)

    def test_missing_scale_blocks_the_calculation(self):
        agent = self.world["agent"]
        Bareme.objects.filter(grade=agent.grade, fonction=agent.fonction).delete()
        with self.assertRaises(CalculationError) as caught:
            calculer_declaration(agent, date(2026, 10, 7), time(17, 0), time(19, 0))
        self.assertEqual(caught.exception.message, MSG_SANS_BAREME)

    def test_new_rate_is_used(self):
        agent = self.world["agent"]
        row = Bareme.objects.get(grade=agent.grade, fonction=agent.fonction)
        row.taux_horaire = Decimal("8000")
        row.save(update_fields=["taux_horaire"])
        result = calculer_declaration(agent, date(2026, 10, 8), time(9, 0), time(11, 0))
        self.assertEqual(result.montant_estime, Decimal("24000.00"))
