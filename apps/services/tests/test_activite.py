from django.test import TestCase
from django.urls import reverse

from apps.agents.forms import AgentForm
from apps.overtime.tests.helpers import PASSWORD, build_referential
from apps.services.models import Service


def _codes_arbre(nodes):
    codes = []
    for node in nodes:
        codes.append(node["code"])
        codes.extend(_codes_arbre(node.get("children") or []))
    return codes


class DirectionActiviteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        build_referential()
        cls.dg = Service.objects.create(
            code="DG-ACT",
            nom="Direction générale de test",
            niveau=Service.Niveau.DIRECTION_GENERALE,
        )
        cls.direction = Service.objects.create(
            code="DIR-ACT",
            nom="Direction à désactiver",
            niveau=Service.Niveau.DIRECTION,
            service_parent=cls.dg,
        )
        cls.secretariat = Service.objects.create(
            code="SEC-ACT",
            nom="Secrétariat de la direction",
            niveau=Service.Niveau.SECRETARIAT,
            service_parent=cls.direction,
        )
        cls.division = Service.objects.create(
            code="DIV-ACT",
            nom="Division rattachée",
            niveau=Service.Niveau.DIVISION,
            service_parent=cls.direction,
        )
        cls.bureau = Service.objects.create(
            code="BUR-ACT",
            nom="Bureau rattaché",
            niveau=Service.Niveau.BUREAU,
            service_parent=cls.division,
        )
        cls.autre = Service.objects.create(
            code="DIR-AUTRE",
            nom="Autre direction",
            niveau=Service.Niveau.DIRECTION,
            service_parent=cls.dg,
        )

    def test_deactivating_a_direction_deactivates_its_units(self):
        self.client.login(username="rh", password=PASSWORD)
        page = self.client.get(reverse("services:list"))
        self.assertContains(page, "Rendre inactif")
        confirm = self.client.get(reverse("services:activite", args=[self.direction.pk]) + "?actif=0")
        self.assertContains(confirm, "Rendre la direction inactive")
        self.assertContains(confirm, "Secrétariat de la direction")
        self.assertContains(confirm, "Bureau rattaché")
        self.assertContains(confirm, "divisions, secrétariats et bureaux")
        response = self.client.post(reverse("services:activite", args=[self.direction.pk]) + "?actif=0")
        self.assertRedirects(response, reverse("services:list"))
        codes = {
            item.code: item.actif
            for item in Service.objects.filter(code__in=["DIR-ACT", "SEC-ACT", "DIV-ACT", "BUR-ACT", "DIR-AUTRE"])
        }
        self.assertEqual(
            codes,
            {"DIR-ACT": False, "SEC-ACT": False, "DIV-ACT": False, "BUR-ACT": False, "DIR-AUTRE": True},
        )

    def test_reactivating_a_direction_restores_its_units(self):
        self.client.login(username="rh", password=PASSWORD)
        self.client.post(reverse("services:activite", args=[self.direction.pk]) + "?actif=0")
        self.client.post(reverse("services:activite", args=[self.direction.pk]) + "?actif=1")
        actifs = set(
            Service.objects.filter(code__in=["DIR-ACT", "SEC-ACT", "DIV-ACT", "BUR-ACT"]).values_list(
                "actif", flat=True
            )
        )
        self.assertEqual(actifs, {True})

    def test_a_division_cannot_deactivate_its_parent_tree(self):
        self.client.login(username="rh", password=PASSWORD)
        response = self.client.post(reverse("services:activite", args=[self.division.pk]) + "?actif=0")
        self.assertRedirects(response, reverse("services:list"))
        self.assertTrue(Service.objects.get(code="DIV-ACT").actif)
        self.assertTrue(Service.objects.get(code="DIR-ACT").actif)

    def test_assignment_form_keeps_only_units_of_an_active_direction(self):
        self.dg.actif = False
        self.dg.save(update_fields=["actif"])
        poste = Service.objects.create(
            code="POSTE-ACT",
            nom="Poste sous une direction générale inactive",
            niveau=Service.Niveau.POSTE,
            service_parent=self.dg,
        )
        codes = set(AgentForm().fields["service"].queryset.values_list("code", flat=True))
        self.assertIn("DIR-ACT", codes)
        self.assertIn("DIV-ACT", codes)
        self.assertIn("BUR-ACT", codes)
        self.assertIn("SEC-ACT", codes)
        self.assertNotIn(poste.code, codes)
        self.assertNotIn(self.dg.code, codes)

    def test_personnel_filter_lists_only_units_of_an_active_direction(self):
        self.autre.actif = False
        self.autre.save(update_fields=["actif"])
        self.bureau.actif = False
        self.bureau.save(update_fields=["actif"])
        self.client.login(username="rh", password=PASSWORD)
        page = self.client.get(reverse("agents:list"))
        self.assertContains(page, "DIR-ACT")
        self.assertContains(page, "niveau-DIRECTION")
        self.assertContains(page, "DIV-ACT")
        self.assertContains(page, "niveau-DIVISION")
        self.assertNotContains(page, "DIR-AUTRE")
        self.assertNotContains(page, "BUR-ACT")

    def test_header_names_the_direction_under_the_logo(self):
        self.client.login(username="rh", password=PASSWORD)
        page = self.client.get(reverse("agents:list"))
        self.assertContains(page, 'class="topbar-direction"')
        self.assertContains(page, "DIRECTION DU TRESOR ET MOYENS DE FINANCEMENT")

    def test_opening_the_picker_reads_the_current_services(self):
        self.client.login(username="rh", password=PASSWORD)
        url = reverse("agents:affectation")
        self.client.post(reverse("services:activite", args=[self.direction.pk]) + "?actif=0")
        caches = self.client.get(url)
        self.assertEqual(caches.status_code, 200)
        self.assertNotIn("DIR-ACT", _codes_arbre(caches.json()))
        self.client.post(reverse("services:activite", args=[self.direction.pk]) + "?actif=1")
        frais = self.client.get(url)
        self.assertIn("DIR-ACT", _codes_arbre(frais.json()))
        self.assertIn("BUR-ACT", _codes_arbre(frais.json()))
