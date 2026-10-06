"""Référentiel des grades et fonctions de l'administration publique de la RDC.

Grades : loi n° 16/013 du 15 juillet 2016, articles 17 et 18.
Les catégories B et C ont deux échelons ; le passage va de l'échelon 1 vers l'échelon 2.

Fonctions : emplois de commandement de l'administration centrale, structures
standards du décret n° 15/043 du 28 décembre 2015, et emplois de la loi n° 16/013.
"""

GRADES = [
    {"code": "SG", "abreviation": "SG", "libelle": "Secrétaire général", "categorie": "A", "echelon": None, "ordre": 10},
    {"code": "DG", "abreviation": "DG", "libelle": "Directeur général", "categorie": "A", "echelon": None, "ordre": 20},
    {"code": "DIR", "abreviation": "DIR", "libelle": "Directeur", "categorie": "A", "echelon": None, "ordre": 30},
    {"code": "CD-2", "abreviation": "CD", "libelle": "Chef de division", "categorie": "B", "echelon": 2, "ordre": 40},
    {"code": "CD-1", "abreviation": "CD", "libelle": "Chef de division", "categorie": "B", "echelon": 1, "ordre": 41},
    {"code": "CB-2", "abreviation": "CB", "libelle": "Chef de bureau", "categorie": "B", "echelon": 2, "ordre": 50},
    {"code": "CB-1", "abreviation": "CB", "libelle": "Chef de bureau", "categorie": "B", "echelon": 1, "ordre": 51},
    {"code": "AA1-2", "abreviation": "ATA1", "libelle": "Attaché d'administration de 1ère classe", "categorie": "C", "echelon": 2, "ordre": 60},
    {"code": "AA1-1", "abreviation": "ATA1", "libelle": "Attaché d'administration de 1ère classe", "categorie": "C", "echelon": 1, "ordre": 61},
    {"code": "AA2-2", "abreviation": "ATA2", "libelle": "Attaché d'administration de 2ème classe", "categorie": "C", "echelon": 2, "ordre": 70},
    {"code": "AA2-1", "abreviation": "ATA2", "libelle": "Attaché d'administration de 2ème classe", "categorie": "C", "echelon": 1, "ordre": 71},
    {"code": "AG1-2", "abreviation": "AGA1", "libelle": "Agent d'administration de 1ère classe", "categorie": "C", "echelon": 2, "ordre": 80},
    {"code": "AG1-1", "abreviation": "AGA1", "libelle": "Agent d'administration de 1ère classe", "categorie": "C", "echelon": 1, "ordre": 81},
    {"code": "AG2", "abreviation": "AGA2", "libelle": "Agent d'administration de 2ème classe", "categorie": "D", "echelon": None, "ordre": 90},
    {"code": "AUX1", "abreviation": "AUX1", "libelle": "Agent auxiliaire de 1ère classe", "categorie": "D", "echelon": None, "ordre": 100},
    {"code": "AUX2", "abreviation": "AUX2", "libelle": "Agent auxiliaire de 2ème classe", "categorie": "D", "echelon": None, "ordre": 110},
    {"code": "HUIS", "abreviation": "HUIS", "libelle": "Huissier", "categorie": "D", "echelon": None, "ordre": 120},
]

FONCTIONS = [
    {"code": "SG", "libelle": "Secrétaire général", "famille": "COMMANDEMENT", "ordre": 10},
    {"code": "DG", "libelle": "Directeur général", "famille": "COMMANDEMENT", "ordre": 20},
    {"code": "DIR", "libelle": "Directeur", "famille": "COMMANDEMENT", "ordre": 30},
    {"code": "CD", "libelle": "Chef de division", "famille": "COMMANDEMENT", "ordre": 40},
    {"code": "CB", "libelle": "Chef de bureau", "famille": "COMMANDEMENT", "ordre": 50},
    {"code": "DRH", "libelle": "Directeur des ressources humaines", "famille": "STRUCTURE", "ordre": 60},
    {"code": "DAF", "libelle": "Directeur administratif et financier", "famille": "STRUCTURE", "ordre": 70},
    {"code": "DEP", "libelle": "Directeur des études et de la planification", "famille": "STRUCTURE", "ordre": 80},
    {
        "code": "DANTIC",
        "libelle": "Directeur des archives et des nouvelles technologies de l'information et de la communication",
        "famille": "STRUCTURE",
        "ordre": 90,
    },
    {"code": "CELL-TECH", "libelle": "Chef de la cellule technique", "famille": "STRUCTURE", "ordre": 100},
    {"code": "CELL-MP", "libelle": "Chef de la cellule de gestion des marchés publics", "famille": "STRUCTURE", "ordre": 110},
    {"code": "AA1", "libelle": "Attaché d'administration de 1ère classe", "famille": "EMPLOI", "ordre": 120},
    {"code": "AA2", "libelle": "Attaché d'administration de 2ème classe", "famille": "EMPLOI", "ordre": 130},
    {"code": "AG1", "libelle": "Agent d'administration de 1ère classe", "famille": "EMPLOI", "ordre": 140},
    {"code": "AG2", "libelle": "Agent d'administration de 2ème classe", "famille": "EMPLOI", "ordre": 150},
    {"code": "AUX1", "libelle": "Agent auxiliaire de 1ère classe", "famille": "EMPLOI", "ordre": 160},
    {"code": "AUX2", "libelle": "Agent auxiliaire de 2ème classe", "famille": "EMPLOI", "ordre": 170},
    {"code": "HUIS", "libelle": "Huissier", "famille": "EMPLOI", "ordre": 180},
]


def ensure_referentiel(sender=None, **kwargs):
    from apps.agents.models import Fonction, Grade

    for row in GRADES:
        Grade.objects.update_or_create(
            code=row["code"],
            defaults={key: value for key, value in row.items() if key != "code"},
        )
    for row in FONCTIONS:
        Fonction.objects.update_or_create(
            code=row["code"],
            defaults={key: value for key, value in row.items() if key != "code"},
        )
