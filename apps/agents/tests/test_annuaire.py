import re

from django.test import TestCase
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from django.urls import reverse

from apps.agents.annuaire import (
    _bloc_effectif,
    _colonnes_tableau,
    _rubrique,
    build_annuaire_pdf,
    echelon,
    lignes_par_grade,
    _nom_signataire,
    lignes_synthese,
    signataire_de,
    regrouper,
    repartition,
)
from apps.settings_app.models import SiteSettings
from apps.agents.models import Agent, Fonction, Grade
from apps.overtime.tests.helpers import PASSWORD, build_referential
from reportlab.lib.enums import TA_RIGHT

from apps.reports.services.pdf import _data_table, _styled
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

    def test_declared_order_overrides_the_alphabetical_sort(self):
        Agent.objects.filter(matricule="PDF-Z").update(ordre=1)
        Agent.objects.filter(matricule="PDF-A").update(ordre=2)
        Agent.objects.filter(matricule="PDF-B").update(ordre=0)
        agents = Agent.objects.filter(matricule__startswith="PDF-").select_related(
            "service",
            "service__service_parent",
            "service__service_parent__service_parent",
            "service__service_parent__service_parent__service_parent",
        )
        arbre = regrouper(agents)
        self.assertEqual([item["unite"].nom for item in arbre], ["Direction du budget", "Direction des achats"])
        bureau = arbre[1]["milieux"][0]["bureaux"][0]
        self.assertEqual([agent.nom for agent in bureau["agents"]], ["ZOLA", "AMANI"])
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

    def test_division_and_bureau_titles_follow_the_name_column(self):
        fiche = _styled()
        largeur = A4[0] - 28 * mm
        colonnes = _colonnes_tableau(largeur)
        self.assertEqual(colonnes[0], 80 * mm)
        self.assertEqual(colonnes[1], 48 * mm)
        direction = _rubrique(fiche, largeur, "Direction — Budget", 0, "1 cadre, 4 agents")
        division = _rubrique(fiche, largeur, "Division — Paie", 1, "1 cadre, 2 agents")
        bureau = _rubrique(fiche, largeur, "Bureau — États", 2, "0 cadre, 2 agents")
        self.assertEqual(list(direction._colWidths), colonnes)
        self.assertEqual(list(division._colWidths), colonnes)
        self.assertEqual(list(bureau._colWidths), colonnes)
        self.assertEqual(direction._cellvalues[0][0].style.fontSize, 9)
        self.assertEqual(division._cellvalues[0][0].style.fontSize, 8.5)
        self.assertEqual(bureau._cellvalues[0][0].style.fontSize, 8)
        self.assertEqual(len({direction.fond, division.fond, bureau.fond}), 3)
        effectif = _bloc_effectif(fiche, largeur, [])
        self.assertEqual(list(effectif._colWidths), colonnes)
        tableau = _data_table(fiche, ["Nom", "Matricule", "Grade"], [["NOM", "1.515.048", "AA"]], colonnes, right_columns=(1,))
        self.assertEqual(tableau._cellvalues[0][1].style.alignment, TA_RIGHT)
        self.assertEqual(tableau._cellvalues[1][1].style.alignment, TA_RIGHT)

    def test_print_button_returns_a_pdf(self):
        self.client.login(username="rh", password=PASSWORD)
        page = self.client.get(reverse("agents:list"))
        self.assertContains(page, "Imprimer la liste")
        self.assertContains(page, "Tableau synthèse")
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

    def test_synthesis_counts_cadres_and_agents(self):
        agent = Agent.objects.get(matricule="PDF-A")
        agent.grade = Grade.objects.get(code="DIR")
        agent.fonction = Fonction.objects.get(code="DIR")
        agent.save()
        agents = list(
            Agent.objects.filter(matricule__in=["PDF-A", "PDF-Z", "PDF-B"]).select_related(
                "grade", "fonction", "service", "service__service_parent"
            )
        )
        lignes = lignes_synthese(agents)
        achats = next(item for item in lignes if item[1] == "Direction des achats")
        paie = next(item for item in lignes if item[1] == "Division de la paie")
        self.assertEqual(achats, (0, "Direction des achats", 1, 1))
        self.assertEqual(paie[0], 1)
        self.assertEqual((paie[2], paie[3]), (1, 1))
        grades = lignes_par_grade(agents)
        self.assertFalse(any("Catégorie" in item[1] for item in grades))
        directeur = next(item for item in grades if item[0] == "DIR")
        self.assertEqual(directeur[1], "Directeur")
        self.assertEqual((directeur[2], directeur[3]), (1, 0))
        sans = next(item for item in grades if item[1] == "Sans grade")
        self.assertEqual((sans[2], sans[3]), (0, 2))
        premier = Agent.objects.get(matricule="PDF-Z")
        second = Agent.objects.get(matricule="PDF-B")
        premier.grade = Grade.objects.get(code="AA2-1")
        second.grade = Grade.objects.get(code="AA2-2")
        fusion = lignes_par_grade([premier, second])
        self.assertEqual(len(fusion), 1)
        self.assertEqual(fusion[0][1], "Attaché d'administration de 2ème classe")
        self.assertNotIn("échelon", fusion[0][1])
        self.assertEqual((fusion[0][2], fusion[0][3]), (0, 2))
        self.client.login(username="rh", password=PASSWORD)
        apercu = self.client.get(reverse("agents:synthese"))
        self.assertEqual(apercu.status_code, 200)
        self.assertContains(apercu, "Tableau synthèse")
        fichier, telechargement = _ouvrir_pdf(self.client, apercu)
        self.assertTrue(fichier.content.startswith(b"%PDF"))
        self.assertIn("tableau-synthese.pdf", telechargement["Content-Disposition"])

    def test_the_director_of_the_direction_signs_the_statement(self):
        directeur = Agent.objects.get(matricule="PDF-B")
        directeur.fonction = Fonction.objects.get(code="DIR")
        directeur.nom = "Mafutala"
        directeur.postnom = "Bekonda"
        directeur.prenom = "Jean Paul"
        directeur.save()
        agents = list(
            Agent.objects.filter(matricule="PDF-B").select_related(
                "service", "service__service_parent", "fonction"
            )
        )
        trouve = signataire_de(agents)
        self.assertEqual(trouve.pk, directeur.pk)
        self.assertEqual(_nom_signataire(trouve), "MAFUTALA BEKONDA Jean Paul")
        site = SiteSettings.load()
        build_annuaire_pdf(agents, site=site, genere_le="09/10/2026 11:19")

    def test_group_titles_stay_with_the_table(self):
        direction = self.direction_b
        for index in range(34):
            Agent.objects.create(
                matricule=f"PDF-N-{index:02d}",
                nom=f"NOM{index:02d}",
                prenom="Test",
                sexe=Agent.Sexe.MASCULIN,
                service=direction,
            )
        site = SiteSettings.load()
        choisis_base = list(
            Agent.objects.filter(matricule__in=["PDF-A", "PDF-Z", "PDF-B"]).select_related(
                "grade", "fonction", "service", "service__service_parent"
            )
        )
        remplissage = list(
            Agent.objects.filter(matricule__startswith="PDF-N-").order_by("matricule").select_related(
                "grade", "fonction", "service", "service__service_parent"
            )
        )
        for count in (0, 8, 15, 22, 28, 34):
            trace = []
            build_annuaire_pdf(
                choisis_base + remplissage[:count],
                site=site,
                genere_le="08/10/2026 19:30",
                trace=trace,
            )
            pages = {}
            for page, est_titre in trace:
                pages.setdefault(page, []).append(est_titre)
            for page, flags in pages.items():
                if True not in flags:
                    continue
                dernier = max(index for index, flag in enumerate(flags) if flag)
                self.assertIn(
                    False,
                    flags[dernier + 1 :],
                    f"Titre de regroupement seul en bas de la page {page} pour {count} agents.",
                )
