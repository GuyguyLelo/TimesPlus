"""Référentiel minimal partagé par les tests."""

from datetime import time
from decimal import Decimal

from django.contrib.auth.models import Group, User

from apps.accounts.access import get_profile
from apps.accounts.roles import ensure_groups
from apps.agents.models import Agent, Bareme, Fonction, Grade
from apps.overtime.models import OvertimeRule, OvertimeType
from apps.services.models import Service
from apps.settings_app.models import SiteSettings
from apps.workflow.models import WorkflowDefinition, WorkflowStep

PASSWORD = "MotDePasse-Test-2026!"


def build_referential():
    ensure_groups(force=True)
    SiteSettings.load()
    direction = Service.objects.create(code="SG", nom="Secrétariat général")
    dsi = Service.objects.create(code="DSI", nom="Direction des systèmes d'information", service_parent=direction)
    drh = Service.objects.create(code="DRH", nom="Direction des ressources humaines", service_parent=direction)
    normale = OvertimeType.objects.create(code="HEURE_NORMALE", libelle="Heure normale", coefficient=Decimal("1"))
    nuit = OvertimeType.objects.create(code="HEURE_NUIT", libelle="Heure de nuit", coefficient=Decimal("1"))
    weekend = OvertimeType.objects.create(code="HEURE_WEEKEND", libelle="Heure de week-end", coefficient=Decimal("1"))
    ferie = OvertimeType.objects.create(code="HEURE_FERIE", libelle="Heure fériée", coefficient=Decimal("1"))
    OvertimeRule.objects.create(
        nom="Férié",
        type_heure=ferie,
        priorite=10,
        applicable_ferie=True,
        coefficient=Decimal("2"),
    )
    OvertimeRule.objects.create(
        nom="Week-end",
        type_heure=weekend,
        priorite=20,
        applicable_weekend=True,
        coefficient=Decimal("1.5"),
    )
    OvertimeRule.objects.create(
        nom="Nuit",
        type_heure=nuit,
        priorite=30,
        heure_debut=time(18, 0),
        heure_fin=time(6, 0),
        coefficient=Decimal("2"),
    )
    OvertimeRule.objects.create(
        nom="Semaine",
        type_heure=normale,
        priorite=100,
        coefficient=Decimal("1.5"),
    )
    workflow = WorkflowDefinition.objects.create(nom="Validation", code="VALIDATION_HS", actif=True)
    step_chef = WorkflowStep.objects.create(
        workflow=workflow, ordre=1, code="CHEF_SERVICE", libelle="Chef de service", limiter_au_service=True
    )
    step_rh = WorkflowStep.objects.create(
        workflow=workflow, ordre=2, code="VALIDATION_RH", libelle="Validation RH", limiter_au_service=False
    )
    step_chef.groupes.add(Group.objects.get(name="CHEF_SERVICE"))
    step_rh.groupes.add(Group.objects.get(name="ADMIN_RH"))
    agent = Agent.objects.create(
        matricule="DSI-014",
        nom="KASONGO",
        postnom="MWAMBA",
        prenom="Aline",
        sexe=Agent.Sexe.FEMININ,
        service=dsi,
        grade=Grade.objects.get(code="AA2-1"),
        fonction=Fonction.objects.get(code="AA2"),
    )
    chef_agent = Agent.objects.create(
        matricule="DSI-001",
        nom="NGALULA",
        prenom="Paul",
        sexe=Agent.Sexe.MASCULIN,
        service=dsi,
        grade=Grade.objects.get(code="CD-1"),
        fonction=Fonction.objects.get(code="CD"),
    )
    other = Agent.objects.create(
        matricule="DRH-002",
        nom="MUKENDI",
        prenom="Jean",
        sexe=Agent.Sexe.MASCULIN,
        service=drh,
        grade=Grade.objects.get(code="DIR"),
        fonction=Fonction.objects.get(code="DIR"),
    )
    Bareme.objects.get_or_create(
        grade=agent.grade, fonction=agent.fonction, defaults={"taux_horaire": Decimal("5000")}
    )
    Bareme.objects.get_or_create(
        grade=chef_agent.grade, fonction=chef_agent.fonction, defaults={"taux_horaire": Decimal("6000")}
    )
    Bareme.objects.get_or_create(
        grade=other.grade, fonction=other.fonction, defaults={"taux_horaire": Decimal("4000")}
    )
    agent_user = make_user("agent", "AGENT", agent=agent)
    chef_user = make_user("chef", "CHEF_SERVICE", agent=chef_agent, service=dsi)
    rh_user = make_user("rh", "ADMIN_RH", service=drh)
    return {
        "dsi": dsi,
        "drh": drh,
        "agent": agent,
        "chef_agent": chef_agent,
        "other": other,
        "agent_user": agent_user,
        "chef_user": chef_user,
        "rh_user": rh_user,
    }


def make_user(username, group_name, agent=None, service=None, superuser=False):
    user = User.objects.create_user(
        username=username,
        password=PASSWORD,
        is_staff=superuser or group_name in {"ADMIN_RH", "SUPER_ADMIN"},
        is_superuser=superuser,
    )
    if group_name:
        user.groups.add(Group.objects.get(name=group_name))
    profile = get_profile(user)
    profile.agent = agent
    profile.service = service
    profile.save()
    user._profile_cache = profile
    return user
