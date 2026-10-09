"""Cadre de la DGTCP selon le décret n° 22/12B du 31 mars 2022.

Direction générale, directions, divisions et bureaux. Les postes comptables
du trésor y sont rattachés comme réseau, sans inventaire de chaque implantation.
"""

from apps.services.models import Service

SOURCE = (
    "Décret n° 22/12B du 31 mars 2022 portant création, missions, organisation "
    "et fonctionnement de la Direction Générale du Trésor et de la Comptabilité Publique."
)

N = Service.Niveau


def _unit(code, nom, niveau, children=()):
    return {"code": code, "nom": nom, "niveau": niveau, "children": children}


STRUCTURE = _unit(
    "DGTCP",
    "Direction Générale du Trésor et de la Comptabilité Publique",
    N.DIRECTION_GENERALE,
    (
        _unit(
            "SEC-ADM",
            "Secrétariat administratif",
            N.SECRETARIAT,
            (
                _unit("SEC-ADM-COU", "Bureau courrier", N.BUREAU),
                _unit("SEC-ADM-PRO", "Bureau protocole", N.BUREAU),
                _unit("SEC-ADM-CRP", "Bureau communication et relations publiques", N.BUREAU),
            ),
        ),
        _unit("SEC-TECH", "Secrétariat technique", N.SECRETARIAT),
        _unit(
            "DIST",
            "Direction de l'inspection des services du trésor",
            N.DIRECTION,
            (
                _unit("DIST-SEC", "Secrétariat de direction", N.SECRETARIAT),
                _unit(
                    "DIST-VCS",
                    "Division des vérifications, contrôles et suivi",
                    N.DIVISION,
                    (
                        _unit("DIST-VCS-PC", "Bureau des vérifications et contrôles des postes comptables du Pouvoir central", N.BUREAU),
                        _unit("DIST-VCS-PV", "Bureau des vérifications et contrôles des postes comptables des provinces et des entités territoriales décentralisées", N.BUREAU),
                        _unit("DIST-VCS-SE", "Bureau du suivi et de l'évaluation", N.BUREAU),
                    ),
                ),
                _unit(
                    "DIST-AI",
                    "Division de l'audit interne",
                    N.DIVISION,
                    (
                        _unit("DIST-AI-MIS", "Bureau des missions d'audit interne", N.BUREAU),
                        _unit("DIST-AI-EC", "Bureau des études et conseils", N.BUREAU),
                    ),
                ),
            ),
        ),
        _unit(
            "DTMF",
            "Direction du trésor et des moyens de financement",
            N.DIRECTION,
            (
                _unit("DTMF-SEC", "Secrétariat de direction", N.SECRETARIAT),
                _unit(
                    "DTMF-TRES",
                    "Division du trésor",
                    N.DIVISION,
                    (
                        _unit("DTMF-TRES-EST", "Bureau des études et du suivi de la trésorerie", N.BUREAU),
                        _unit("DTMF-TRES-OPE", "Bureau des opérations financières de l'Etat", N.BUREAU),
                    ),
                ),
                _unit(
                    "DTMF-FIN",
                    "Division des moyens de financement",
                    N.DIVISION,
                    (
                        _unit("DTMF-FIN-TIT", "Bureau de financement par marchés des titres", N.BUREAU),
                        _unit("DTMF-FIN-HOR", "Bureau de financement hors marchés des titres", N.BUREAU),
                    ),
                ),
            ),
        ),
        _unit(
            "DRQC",
            "Direction de la réglementation et de la qualité comptables",
            N.DIRECTION,
            (
                _unit("DRQC-SEC", "Secrétariat de direction", N.SECRETARIAT),
                _unit(
                    "DRQC-REG",
                    "Division de la réglementation comptable",
                    N.DIVISION,
                    (
                        _unit("DRQC-REG-LEG", "Bureau de la législation comptable", N.BUREAU),
                        _unit("DRQC-REG-QUA", "Bureau du suivi et de la qualité comptables", N.BUREAU),
                    ),
                ),
                _unit(
                    "DRQC-DOC",
                    "Division de la documentation et des imprimés comptables",
                    N.DIVISION,
                    (
                        _unit("DRQC-DOC-GES", "Bureau de gestion de la documentation comptable", N.BUREAU),
                        _unit("DRQC-DOC-IMP", "Bureau des imprimés comptables", N.BUREAU),
                    ),
                ),
                _unit(
                    "DRQC-RA",
                    "Division des régies d'avances et des recettes",
                    N.DIVISION,
                    (
                        _unit("DRQC-RA-ACT", "Bureau des actes", N.BUREAU),
                        _unit("DRQC-RA-STA", "Bureau du suivi et des statistiques", N.BUREAU),
                    ),
                ),
            ),
        ),
        _unit(
            "DCF",
            "Direction des contentieux financiers",
            N.DIRECTION,
            (
                _unit("DCF-SEC", "Secrétariat de direction", N.SECRETARIAT),
                _unit(
                    "DCF-CON",
                    "Division conseil et assistance",
                    N.DIVISION,
                    (
                        _unit("DCF-CON-STA", "Bureau des statistiques et études des créances contentieuses", N.BUREAU),
                        _unit("DCF-CON-JUR", "Bureau d'études juridiques", N.BUREAU),
                        _unit("DCF-CON-INV", "Bureau des investigations", N.BUREAU),
                    ),
                ),
                _unit(
                    "DCF-SUI",
                    "Division de suivi des contentieux financiers",
                    N.DIVISION,
                    (
                        _unit("DCF-SUI-SUI", "Bureau de suivi des contentieux financiers", N.BUREAU),
                        _unit("DCF-SUI-REG", "Bureau du règlement des contentieux financiers", N.BUREAU),
                    ),
                ),
            ),
        ),
        _unit(
            "DMGP",
            "Direction des moyens généraux et du personnel",
            N.DIRECTION,
            (
                _unit("DMGP-SEC", "Secrétariat de direction", N.SECRETARIAT),
                _unit(
                    "DMGP-FL",
                    "Division finances et logistique",
                    N.DIVISION,
                    (
                        _unit("DMGP-FL-LOG", "Bureau intendance et logistique", N.BUREAU),
                        _unit("DMGP-FL-BUD", "Bureau gestion budgétaire", N.BUREAU),
                    ),
                ),
                _unit(
                    "DMGP-GP",
                    "Division gestion du personnel",
                    N.DIVISION,
                    (
                        _unit("DMGP-GP-CAR", "Bureau de suivi de la carrière du personnel", N.BUREAU),
                        _unit("DMGP-GP-SOC", "Bureau actions sociales", N.BUREAU),
                    ),
                ),
                _unit(
                    "DMGP-FC",
                    "Division formation et suivi des compétences",
                    N.DIVISION,
                    (
                        _unit("DMGP-FC-FOR", "Bureau formation", N.BUREAU),
                        _unit("DMGP-FC-EVA", "Bureau évaluation des compétences", N.BUREAU),
                    ),
                ),
            ),
        ),
        _unit(
            "DINFO",
            "Direction informatique",
            N.DIRECTION,
            (
                _unit("DINFO-SEC", "Secrétariat de direction", N.SECRETARIAT),
                _unit(
                    "DINFO-ED",
                    "Division des études et des développements informatiques",
                    N.DIVISION,
                    (
                        _unit("DINFO-ED-STR", "Bureau de la stratégie", N.BUREAU),
                        _unit("DINFO-ED-VEI", "Bureau de veille technologique", N.BUREAU),
                        _unit("DINFO-ED-DEV", "Bureau développements informatiques", N.BUREAU),
                    ),
                ),
                _unit(
                    "DINFO-ERS",
                    "Division de l'exploitation, des réseaux et de la sécurité informatique",
                    N.DIVISION,
                    (
                        _unit("DINFO-ERS-EXP", "Bureau d'exploitation des systèmes et des bases de données informatiques", N.BUREAU),
                        _unit("DINFO-ERS-SEC", "Bureau de la sécurité informatique", N.BUREAU),
                        _unit("DINFO-ERS-RES", "Bureau de gestion des réseaux et de l'infrastructure informatique", N.BUREAU),
                    ),
                ),
                _unit(
                    "DINFO-MNT",
                    "Division de la maintenance des applications bureautiques et de la gestion du matériel et des logiciels",
                    N.DIVISION,
                    (
                        _unit("DINFO-MNT-ASS", "Bureau de l'assistance et de la maintenance des applications bureautiques", N.BUREAU),
                        _unit("DINFO-MNT-WEB", "Bureau de la maintenance du site web, de la messagerie et de l'intranet", N.BUREAU),
                        _unit("DINFO-MNT-FOR", "Bureau de la formation informatique", N.BUREAU),
                    ),
                ),
            ),
        ),
        _unit("ACCT", "Agence comptable centrale du trésor", N.POSTE),
        _unit("TPE", "Trésorerie paierie pour l'étranger", N.POSTE),
        _unit("TPP", "Trésorerie paierie provinciale", N.POSTE),
        _unit("TPT", "Trésorerie paierie territoriale", N.POSTE),
        _unit("TPU", "Trésorerie paierie urbaine", N.POSTE),
        _unit("PCM", "Poste comptable des ministères", N.POSTE),
        _unit("PCBA", "Poste comptable des budgets annexes", N.POSTE),
        _unit("PCCS", "Poste comptable des comptes spéciaux", N.POSTE),
    ),
)

_REMPLACEMENTS = {
    "SG": "DGTCP",
    "DRH": "DMGP",
    "DSI": "DINFO",
    "DAF": "DMGP-FL",
}
# matricule, service, grade, fonction — le niveau suit le grade :
# directeur sur une direction, chef de division sur une division, chef de bureau et collaborateurs sur un bureau.
_AFFECTATIONS = (
    ("RH-001", "DMGP", "DIR", "DIR"),
    ("DSI-001", "DINFO-ED", "CD-1", "CD"),
    ("DSI-014", "DINFO-ED-DEV", "AA2-1", "AA2"),
    ("DAF-008", "DMGP-FL-BUD", "CB-1", "CB"),
)
# matricule, nom, postnom, prénom, sexe, service, grade, fonction.
# Un directeur, deux chefs de division, quatre chefs de bureau et trois attachés.
_AGENTS_DTMF = (
    ("DTMF-001", "KABANGE", "TSHIMANGA", "André", "M", "DTMF", "DIR", "DIR"),
    ("DTMF-002", "NGOY", "KABONGO", "Marie", "F", "DTMF-TRES", "CD-1", "CD"),
    ("DTMF-003", "ILUNGA", "MWAMBA", "Patrick", "M", "DTMF-FIN", "CD-1", "CD"),
    ("DTMF-004", "MUTOMBO", "KALALA", "Grâce", "F", "DTMF-TRES-EST", "CB-1", "CB"),
    ("DTMF-005", "KASONGO", "MUKENGE", "Eric", "M", "DTMF-TRES-EST", "AA2-1", "AA2"),
    ("DTMF-006", "LUKUSA", "NGOY", "Joseph", "M", "DTMF-TRES-OPE", "CB-1", "CB"),
    ("DTMF-007", "MBALA", "TSHIMANGA", "Clarisse", "F", "DTMF-TRES-OPE", "AA2-1", "AA2"),
    ("DTMF-008", "KALALA", "ILUNGA", "Nadine", "F", "DTMF-FIN-TIT", "CB-1", "CB"),
    ("DTMF-009", "MWAMBA", "KABANGE", "Serge", "M", "DTMF-FIN-TIT", "AA2-1", "AA2"),
    ("DTMF-010", "TSHIMANGA", "LUKUSA", "Didier", "M", "DTMF-FIN-HOR", "CB-1", "CB"),
)
_PROFILS = {
    "rh": "DMGP",
    "chef": "DINFO-ED",
}


def _enregistrer(unit, parent=None):
    service, created = Service.objects.get_or_create(
        code=unit["code"],
        defaults={
            "nom": unit["nom"],
            "niveau": unit["niveau"],
            "service_parent": parent,
            "actif": True,
        },
    )
    if not created:
        service.nom = unit["nom"]
        service.niveau = unit["niveau"]
        service.service_parent = parent
        service.save(update_fields=["nom", "niveau", "service_parent"])
    if unit["code"] == "DGTCP" and not service.description:
        service.description = SOURCE
        service.save(update_fields=["description"])
    for child in unit["children"]:
        _enregistrer(child, service)
    return service


def ensure_dgtcp(sender=None, **kwargs):
    _enregistrer(STRUCTURE)
    from apps.settings_app.models import SiteSettings

    site = SiteSettings.load()
    if site.nom_administration in {
        "Administration publique",
        "Secrétariat général — environnement de démonstration",
    }:
        site.nom_administration = "Direction Générale du Trésor et de la Comptabilité Publique"
        site.sigle = "DGTCP"
        if not site.adresse:
            site.adresse = "Kinshasa, République démocratique du Congo"
        site.save()


def assurer_agents_dtmf():
    """Crée les dix agents de la Direction du trésor et des moyens de financement."""
    from datetime import date
    from decimal import Decimal
    import unicodedata

    from apps.agents.models import Agent, Bareme, Fonction, Grade
    from apps.agents.referentiel import ensure_referentiel

    ensure_dgtcp()
    ensure_referentiel()
    for matricule, nom, postnom, prenom, sexe, code, grade_code, fonction_code in _AGENTS_DTMF:
        service = Service.objects.filter(code=code).first()
        grade = Grade.objects.filter(code=grade_code).first()
        fonction = Fonction.objects.filter(code=fonction_code).first()
        if service is None or grade is None or fonction is None:
            continue
        courriel = unicodedata.normalize("NFD", f"{prenom}.{nom}@heures.local".lower())
        courriel = "".join(car for car in courriel if unicodedata.category(car) != "Mn")
        agent, created = Agent.objects.get_or_create(
            matricule=matricule,
            defaults={
                "nom": nom,
                "postnom": postnom,
                "prenom": prenom,
                "sexe": sexe,
                "service": service,
                "grade": grade,
                "fonction": fonction,
                "email": courriel,
                "statut": Agent.Statut.ACTIF,
                "actif": True,
                "date_engagement": date(2021, 3, 1),
            },
        )
        if not created:
            agent.service = service
            agent.grade = grade
            agent.fonction = fonction
            agent.actif = True
            agent.save(update_fields=["service", "grade", "fonction", "actif", "updated_at"])
        Bareme.objects.get_or_create(
            grade=grade,
            fonction=fonction,
            defaults={"taux_horaire": Decimal("5000.00"), "actif": True},
        )


def reaffecter_agents():
    """Place chaque agent de démonstration sur l'unité DGTCP de son grade."""
    from django.contrib.auth.models import User

    from apps.accounts.models import UserProfile
    from apps.agents.models import Agent, Fonction, Grade
    from apps.agents.referentiel import ensure_referentiel

    ensure_dgtcp()
    ensure_referentiel()
    for matricule, code, grade_code, fonction_code in _AFFECTATIONS:
        agent = Agent.objects.filter(matricule=matricule).first()
        service = Service.objects.filter(code=code).first()
        if agent is None or service is None:
            continue
        agent.service = service
        grade = Grade.objects.filter(code=grade_code).first()
        fonction = Fonction.objects.filter(code=fonction_code).first()
        fields = ["service", "updated_at"]
        if grade is not None:
            agent.grade = grade
            fields.append("grade")
        if fonction is not None:
            agent.fonction = fonction
            fields.append("fonction")
        agent.save(update_fields=fields)
    assurer_agents_dtmf()
    for username, code in _PROFILS.items():
        cible = Service.objects.filter(code=code).first()
        user = User.objects.filter(username=username).first()
        if cible is not None and user is not None and hasattr(user, "profile"):
            UserProfile.objects.filter(user=user).update(service=cible)


def rattacher_anciens_services():
    """Déplace les données de démonstration vers la hiérarchie DGTCP."""
    from apps.accounts.models import UserProfile
    from apps.agents.models import Agent
    from apps.overtime.models import WorkSchedule

    reaffecter_agents()
    for ancien, nouveau in _REMPLACEMENTS.items():
        source = Service.objects.filter(code=ancien).first()
        cible = Service.objects.filter(code=nouveau).first()
        if source is None or cible is None or source.pk == cible.pk:
            continue
        Agent.objects.filter(service=source).update(service=cible)
        UserProfile.objects.filter(service=source).update(service=cible)
        WorkSchedule.objects.filter(service=source).update(service=cible)
    for code in ("DRH", "DAF", "DSI", "SG"):
        ancien = Service.objects.filter(code=code).first()
        if ancien is None:
            continue
        if ancien.sous_services.exists() or ancien.agents.exists() or ancien.responsables.exists():
            ancien.actif = False
            ancien.save(update_fields=["actif", "updated_at"])
            continue
        ancien.delete()
