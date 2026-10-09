from django.test import TestCase
from django.urls import reverse

from apps.agents.models import Fonction, Grade
from apps.agents.referentiel import FONCTIONS, GRADES
from apps.overtime.tests.helpers import PASSWORD, build_referential


class ReferentielTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.world = build_referential()

    def test_official_grades_and_functions_are_loaded(self):
        self.assertEqual(Grade.objects.count(), len(GRADES))
        self.assertEqual(Fonction.objects.count(), len(FONCTIONS))
        self.assertTrue(Grade.objects.filter(code="SG", libelle="Secrétaire général", echelon__isnull=True).exists())
        self.assertEqual(Grade.objects.filter(libelle="Chef de division").count(), 2)
        self.assertTrue(Fonction.objects.filter(code="DRH", famille="STRUCTURE").exists())
        self.assertTrue(Fonction.objects.filter(code="CELL-MP").exists())

    def test_agent_form_offers_the_referential(self):
        self.client.login(username="rh", password=PASSWORD)
        response = self.client.get(reverse("agents:create"))
        self.assertContains(response, "Grade statutaire")
        self.assertContains(response, "Cadre organique")
        self.assertContains(response, "Secrétaire général")
        self.assertContains(response, "Chef de division, échelon 2")
        self.assertContains(response, "Directeur des ressources humaines")
        self.assertContains(response, "Huissier")

    def test_referential_page_is_visible_to_rh(self):
        self.client.login(username="rh", password=PASSWORD)
        response = self.client.get(reverse("agents:referentiel"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Loi n° 16/013")
        self.assertContains(response, "décret n° 15/043")
        self.assertContains(response, "ATA1")
        self.assertContains(response, "AGA2")
        self.assertContains(response, ">DIR<")
