import re

from django.test import TestCase
from django.urls import reverse

from apps.agents.annuaire import echelon, regrouper, repartition
from apps.agents.models import Agent, Fonction, Grade
from apps.overtime.tests.helpers import PASSWORD, build_referential
from apps.services.models import Service


def _ouvrir_pdf(client, apercu):
    match = re.search(br'class="pdf-frame" src="([^"]+)"', apercu.content)
    if match is None:
        raise AssertionError(apercu.content[:500])
    src = match.group(1).decode()
    fichier = client.get(src)
    telechargement = client.get(f"{src}?telecharger=1")
    return fichier, telechargement


class AnnuaireTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        build_referential()
        dg = Service.objects.create(
            code="DG-PDF",
            nom="Direction générale du test",
            niveau=Service.Niveau.DIRECTION_GENERALE,
        )
        direction_b = Service.objects.create(
            code="DIR-B",
            nom="Direction du budget",
            niveau=Service.Niveau.DIRECTION,
            service_parent=dg,
        )
        direction_a = Service.objects.create(
            code="DIR-A",
            nom="Direction des achats",
            niveau=Service.Niveau.DIRECTION,
            service_parent=dg,
        )
        division = Service.objects.create(
            code="DIV-A",
            nom="Division de la paie",
            niveau=Service.Niveau.DIVISION,
            service_parent=direction_a,
        )
        bureau = Service.objects.create(
            code="BUR-A",
            nom="Bureau des états",
            niveau=Service.Niveau.BUREAU,
            service_parent=division,
        )
        Agent.objects.create(
            matricule="PDF-Z",
            nom="ZOLA",
            prenom="Zoe",
            sexe=Agent.Sexe.FEMININ,
            service=bureau,
        )
        Agent.objects.create(
            matricule="PDF-A",
            nom="AMANI",
            prenom="Aline",
            sexe=Agent.Sexe.FEMININ,
            service=bureau,
        )
        Agent.objects.create(
            matricule="PDF-B",
            nom="BAKA",
            prenom="Paul",
            sexe=Agent.Sexe.MASCULIN,
            service=direction_b,
        )
        cls.bureau = bureau
        cls.direction_a = direction_a
        cls.direction_b = direction_b

    def test_agents_are_grouped_and_sorted_by_name(self):
        agents = Agent.objects.filter(matricule__startswith="PDF-").select_related(
            "service",
            "service__service_parent",
            "service__service_parent__service_parent",
            "service__service_parent__service_parent__service_parent",
        )
        arbre = regrouper(agents)
        self.assertEqual([item["unite"].nom for item in arbre], ["Direction des achats", "Direction du budget"])
        bureau = arbre[0]["milieux"][0]["bureaux"][0]
        self.assertEqual(bureau["unite"].nom, "Bureau des états")
        self.assertEqual([agent.nom for agent in bureau["agents"]], ["AMANI", "ZOLA"])
        direction, milieu, unite = echelon(self.bureau)
        self.assertEqual(direction.nom, "Direction des achats")
        self.assertEqual(milieu.nom, "Division de la paie")
        self.assertEqual(unite.nom, "Bureau des états")

    def test_headcount_separates_cadres_and_agents(self):
        directeur = Agent.objects.get(matricule="PDF-A")
        directeur.grade = Grade.objects.get(code="DIR")
        directeur.fonction = Fonction.objects.get(code="DIR")
        directeur.save()
        agents = Agent.objects.filter(matricule__startswith="PDF-").select_related("grade", "fonction")
        cadres, autres = repartition(agents)
        self.assertEqual((cadres, autres), (1, 2))

    def test_print_button_returns_a_pdf(self):
        self.client.login(username="rh", password=PASSWORD)
        page = self.client.get(reverse("agents:list"))
        self.assertContains(page, "Imprimer")
        apercu = self.client.get(reverse("agents:print"))
        self.assertEqual(apercu.status_code, 200)
        self.assertContains(apercu, "Télécharger")
        self.assertContains(apercu, "Liste déclarative par emboîtement")
        fichier, telechargement = _ouvrir_pdf(self.client, apercu)
        self.assertEqual(fichier["Content-Type"], "application/pdf")
        self.assertIn("inline", fichier["Content-Disposition"])
        self.assertTrue(fichier.content.startswith(b"%PDF"))
        self.assertIn("attachment", telechargement["Content-Disposition"])
        self.assertIn("liste-du-personnel.pdf", telechargement["Content-Disposition"])
        self.assertEqual(telechargement.content, fichier.content)
