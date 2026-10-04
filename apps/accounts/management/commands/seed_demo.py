"""Données de démonstration. Les coefficients et jours fériés sont des exemples modifiables."""

import os
from datetime import date, time, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.access import get_profile
from apps.accounts.roles import ensure_groups
from apps.agents.models import Agent, Fonction, Grade
from apps.agents.referentiel import ensure_referentiel
from apps.overtime.models import Holiday, OvertimeRequest, OvertimeRule, OvertimeType, WorkSchedule
from apps.overtime.services.declaration import enregistrer_declaration
from apps.services.models import Service
from apps.settings_app.models import SiteSettings
from apps.workflow.models import WorkflowDefinition, WorkflowStep
DEMO_PASSWORDS = {
    "admin": "Gestion-Heures-Admin-2026!",
    "rh": "Gestion-Heures-Rh-2026!",
    "chef": "Gestion-Heures-Chef-2026!",
    "agent": "Gestion-Heures-Agent-2026!",
}

HOLIDAYS = (
    (1, 1, "Nouvel An", Holiday.Type.NATIONAL),
    (1, 4, "Martyrs de l'indépendance", Holiday.Type.NATIONAL),
    (1, 16, "Journée du héros national Laurent-Désiré Kabila", Holiday.Type.OFFICIEL),
    (1, 17, "Journée du héros national Patrice-Émery Lumumba", Holiday.Type.OFFICIEL),
    (5, 1, "Fête du Travail", Holiday.Type.NATIONAL),
    (5, 17, "Journée de la libération", Holiday.Type.OFFICIEL),
    (6, 30, "Anniversaire de l'indépendance", Holiday.Type.NATIONAL),
    (8, 1, "Fête des parents", Holiday.Type.NATIONAL),
    (12, 25, "Noël", Holiday.Type.NATIONAL),
)


class Command(BaseCommand):
    help = "Crée des données de démonstration (services, agents, rôles, règles, demandes)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Autorise l'exécution même si DEBUG=False.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG and not options["force"]:
            raise CommandError(
                "seed_demo est prévu pour un environnement de démonstration. "
                "Relancez avec --force si vous assumez l'écriture de données d'exemple."
            )
        ensure_groups(force=True)
        self._settings()
        services = self._services()
        agents = self._agents(services)
        users = self._users(agents, services)
        self._schedules(services["dinfo"])
        self._holidays()
        self._rules()
        self._workflow()
        if not OvertimeRequest.objects.exists():
            self._requests(users)
        self.stdout.write(self.style.SUCCESS("Données de démonstration prêtes."))
        self.stdout.write("Comptes de démonstration (à changer avant toute mise en production) :")
        for username, password in DEMO_PASSWORDS.items():
            state = "créé" if username in self.created_users else "déjà présent, mot de passe inchangé"
            shown = password if username in self.created_users else "(inchangé)"
            self.stdout.write(f"  {username} / {shown} — {state}")

    def _settings(self):
        site = SiteSettings.load()
        if site.nom_administration in {
            "Administration publique",
            "Secrétariat général — environnement de démonstration",
        }:
            site.nom_administration = "Direction Générale du Trésor et de la Comptabilité Publique"
            site.sigle = "DGTCP"
            site.devise = "CDF"
            site.adresse = "Kinshasa, République démocratique du Congo"
            site.email_contact = "contact@heures.local"
            site.save()

    def _services(self):
        from apps.services.dgtcp import ensure_dgtcp

        ensure_dgtcp()
        codes = {
            "dgtcp": "DGTCP",
            "dmgp": "DMGP",
            "personnel": "DMGP-GP",
            "budget": "DMGP-FL-BUD",
            "dinfo": "DINFO",
            "etudes": "DINFO-ED",
            "developpements": "DINFO-ED-DEV",
        }
        return {key: Service.objects.get(code=code) for key, code in codes.items()}

    def _agents(self, services):
        ensure_referentiel()
        specs = [
            ("RH-001", "MUKENDI", "ILUNGA", "Jean", Agent.Sexe.MASCULIN, services["dmgp"], "DIR", "DIR"),
            ("DSI-001", "NGALULA", "MUKENGE", "Paul", Agent.Sexe.MASCULIN, services["etudes"], "CD-1", "CD"),
            ("DSI-014", "KASONGO", "MWAMBA", "Aline", Agent.Sexe.FEMININ, services["developpements"], "AA2-1", "AA2"),
            ("DAF-008", "LOMBE", "KALALA", "David", Agent.Sexe.MASCULIN, services["budget"], "CB-1", "CB"),
        ]
        created = {}
        for matricule, nom, postnom, prenom, sexe, service, grade_code, fonction_code in specs:
            grade = Grade.objects.get(code=grade_code)
            fonction = Fonction.objects.get(code=fonction_code)
            agent, created_agent = Agent.objects.get_or_create(
                matricule=matricule,
                defaults={
                    "nom": nom,
                    "postnom": postnom,
                    "prenom": prenom,
                    "sexe": sexe,
                    "service": service,
                    "grade": grade,
                    "fonction": fonction,
                    "email": f"{prenom}.{nom}@heures.local".lower(),
                    "taux_horaire": Decimal("5000.00"),
                    "statut": Agent.Statut.ACTIF,
                    "actif": True,
                    "date_engagement": timezone.localdate().replace(year=timezone.localdate().year - 5),
                },
            )
            if not created_agent:
                agent.service = service
                agent.grade = grade
                agent.fonction = fonction
                agent.save(update_fields=["service", "grade", "fonction", "updated_at"])
            created[matricule] = agent
        return created

    def _users(self, agents, services):
        self.created_users = set()
        common_password = os.environ.get("SEED_DEMO_PASSWORD", "").strip()
        specs = [
            ("admin", "Admin", "Système", True, True, "SUPER_ADMIN", None, None),
            ("rh", "Jean", "Mukendi", True, False, "ADMIN_RH", agents["RH-001"], services["dmgp"]),
            ("chef", "Paul", "Ngalula", False, False, "CHEF_SERVICE", agents["DSI-001"], services["etudes"]),
            ("agent", "Aline", "Kasongo", False, False, "AGENT", agents["DSI-014"], None),
        ]
        users = {}
        for username, first, last, staff, superuser, group_name, agent, service in specs:
            password = common_password or DEMO_PASSWORDS[username]
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "email": f"{username}@heures.local",
                    "is_staff": staff,
                    "is_superuser": superuser,
                    "is_active": True,
                },
            )
            if created:
                user.set_password(password)
                user.save()
                self.created_users.add(username)
            user.groups.add(Group.objects.get(name=group_name))
            profile = get_profile(user)
            if agent and profile.agent_id is None:
                profile.agent = agent
            if service:
                profile.service = service
            profile.save()
            users[username] = user
        return users

    def _schedules(self, service):
        for day in range(5):
            WorkSchedule.objects.get_or_create(
                nom="Horaire administratif",
                jour_semaine=day,
                service=None,
                defaults={
                    "heure_debut": time(8, 0),
                    "heure_fin": time(16, 0),
                    "pause_debut": time(12, 0),
                    "pause_fin": time(13, 0),
                    "actif": True,
                },
            )

    def _holidays(self):
        year = timezone.localdate().year
        for target_year in (year, year + 1):
            for month, day, label, kind in HOLIDAYS:
                Holiday.objects.get_or_create(
                    date=date(target_year, month, day),
                    defaults={"libelle": label, "type": kind, "actif": True},
                )

    def _rules(self):
        types = {
            "HEURE_NORMALE": ("Heure de semaine", Decimal("1.000")),
            "HEURE_NUIT": ("Heure de nuit", Decimal("1.000")),
            "HEURE_WEEKEND": ("Heure de week-end", Decimal("1.000")),
            "HEURE_FERIE": ("Heure de jour férié", Decimal("1.000")),
        }
        stored = {}
        for code, (label, coefficient) in types.items():
            item, _ = OvertimeType.objects.get_or_create(
                code=code,
                defaults={
                    "libelle": label,
                    "coefficient": coefficient,
                    "description": "Valeur d'exemple. L'administration doit saisir le coefficient applicable.",
                    "actif": True,
                },
            )
            stored[code] = item
        OvertimeRule.objects.get_or_create(
            nom="Jour férié",
            defaults={
                "type_heure": stored["HEURE_FERIE"],
                "priorite": 10,
                "applicable_ferie": True,
                "coefficient": Decimal("2.000"),
                "actif": True,
            },
        )
        OvertimeRule.objects.get_or_create(
            nom="Week-end",
            defaults={
                "type_heure": stored["HEURE_WEEKEND"],
                "priorite": 20,
                "applicable_weekend": True,
                "coefficient": Decimal("1.500"),
                "actif": True,
            },
        )
        OvertimeRule.objects.get_or_create(
            nom="Nuit en semaine",
            defaults={
                "type_heure": stored["HEURE_NUIT"],
                "priorite": 30,
                "heure_debut": time(18, 0),
                "heure_fin": time(6, 0),
                "coefficient": Decimal("1.600"),
                "actif": True,
            },
        )
        OvertimeRule.objects.get_or_create(
            nom="Semaine — journée",
            defaults={
                "type_heure": stored["HEURE_NORMALE"],
                "priorite": 100,
                "coefficient": Decimal("1.300"),
                "actif": True,
            },
        )

    def _workflow(self):
        workflow, _ = WorkflowDefinition.objects.get_or_create(
            code="VALIDATION_HS",
            defaults={
                "nom": "Validation des heures supplémentaires",
                "description": "Chef de service, puis ressources humaines.",
                "actif": True,
            },
        )
        chef, _ = WorkflowStep.objects.get_or_create(
            workflow=workflow,
            code="CHEF_SERVICE",
            defaults={"ordre": 1, "libelle": "Chef de service", "limiter_au_service": True},
        )
        rh, _ = WorkflowStep.objects.get_or_create(
            workflow=workflow,
            code="VALIDATION_RH",
            defaults={"ordre": 2, "libelle": "Validation RH", "limiter_au_service": False},
        )
        chef.groupes.set(Group.objects.filter(name__in=["CHEF_SERVICE", "VALIDATEUR"]))
        rh.groupes.set(Group.objects.filter(name__in=["ADMIN_RH"]))

    def _free_day(self, weekday, skip):
        day = timezone.localdate() - timedelta(days=30)
        found = 0
        while (timezone.localdate() - day).days < 500:
            if day.weekday() == weekday and not Holiday.objects.filter(date=day, actif=True).exists():
                if found == skip:
                    return day
                found += 1
            day -= timedelta(days=1)
        raise CommandError("Impossible de trouver une date de démonstration.")

    def _requests(self, users):
        agent = get_profile(users["agent"]).agent
        drafts = [
            (self._free_day(2, 0), time(17, 0), time(19, 0), "Astreinte réseau", "Supervision de la sauvegarde"),
        ]
        pending = [
            (self._free_day(2, 1), time(17, 0), time(20, 30), "Clôture applicative", "Mise en production corrective"),
        ]
        approved = [
            (self._free_day(2, 2), time(18, 0), time(21, 0), "Incident nocturne", "Rétablissement du service métier"),
        ]
        rejected = [
            (self._free_day(2, 3), time(17, 30), time(19, 0), "Réunion tardive", "Préparation d'un comité"),
        ]
        for day, start, end, motif, activite in drafts:
            enregistrer_declaration(
                agent=agent,
                date_travail=day,
                heure_debut=start,
                heure_fin=end,
                motif=motif,
                user=users["agent"],
            )
        for bucket in (pending, approved, rejected):
            for day, start, end, motif, activite in bucket:
                enregistrer_declaration(
                    agent=agent,
                    date_travail=day,
                    heure_debut=start,
                    heure_fin=end,
                    motif=motif,
                    user=users["agent"],
                )
