"""Requêtes d'heures supplémentaires limitées au périmètre de l'utilisateur."""

from django.db.models import Q

from apps.accounts.access import get_profile
from apps.services.selectors import managed_service_ids


def base_queryset():
    from apps.overtime.models import OvertimeRequest

    return OvertimeRequest.objects.select_related(
        "agent",
        "agent__service",
        "agent__grade",
        "agent__fonction",
        "type_heure",
        "regle_appliquee",
        "created_by",
        "current_step",
        "current_step__workflow",
    )


def can_view_all(user):
    return user.is_superuser or user.has_perm("overtime.view_all_overtime")


def overtime_for_user(user):
    queryset = base_queryset()
    if can_view_all(user):
        return queryset
    profile = get_profile(user)
    filters = Q()
    if profile.agent_id:
        filters |= Q(agent_id=profile.agent_id)
    if user.has_perm("overtime.approve_overtime") or user.has_perm("overtime.reject_overtime"):
        service_ids = managed_service_ids(user)
        if service_ids:
            filters |= Q(agent__service_id__in=service_ids)
    if filters:
        return queryset.filter(filters).distinct()
    return queryset.none()


def my_overtime(user):
    profile = get_profile(user)
    if not profile.agent_id:
        return base_queryset().none()
    return base_queryset().filter(agent_id=profile.agent_id)


def fiche_agent(agent):
    """Identité affichée lorsqu'un agent est choisi dans une saisie."""
    from django.urls import reverse

    return {
        "id": agent.pk,
        "matricule": agent.matricule,
        "nom": agent.nom_complet,
        "grade": str(agent.grade) if agent.grade_id else "",
        "fonction": str(agent.fonction) if agent.fonction_id else "",
        "service": agent.service.nom,
        "initiales": agent.initiales,
        "photo": reverse("agents:photo", args=[agent.pk]) if agent.photo else "",
    }


def agents_visible(user):
    from apps.agents.models import Agent

    queryset = Agent.objects.select_related("service")
    if user.is_superuser or can_view_all(user):
        return queryset
    profile = get_profile(user)
    filters = Q()
    if profile.agent_id:
        filters |= Q(pk=profile.agent_id)
    if user.has_perm("agents.view_agent"):
        service_ids = managed_service_ids(user)
        if service_ids:
            filters |= Q(service_id__in=service_ids)
    if filters:
        return queryset.filter(filters).distinct()
    return queryset.none()


def apply_overtime_filters(queryset, params):
    """Filtres et tri bornés à une liste blanche de colonnes."""
    from datetime import datetime

    from apps.overtime.models import OvertimeRequest

    q = (params.get("q") or "").strip()
    if q:
        queryset = queryset.filter(
            Q(motif__icontains=q)
            | Q(activite__icontains=q)
            | Q(agent__matricule__icontains=q)
            | Q(agent__nom__icontains=q)
            | Q(agent__postnom__icontains=q)
            | Q(agent__prenom__icontains=q)
        )
    statut = params.get("statut") or ""
    if statut in OvertimeRequest.Statut.values:
        queryset = queryset.filter(statut=statut)
    if str(params.get("type") or "").isdigit():
        queryset = queryset.filter(type_heure_id=int(params["type"]))
    if str(params.get("service") or "").isdigit():
        queryset = queryset.filter(agent__service_id=int(params["service"]))
    if str(params.get("agent") or "").isdigit():
        queryset = queryset.filter(agent_id=int(params["agent"]))
    for key, lookup in (("debut", "date_travail__gte"), ("fin", "date_travail__lte")):
        raw = params.get(key) or ""
        if not raw:
            continue
        try:
            parsed = datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            continue
        queryset = queryset.filter(**{lookup: parsed})
    sorts = {
        "date": "date_travail",
        "debut": "heure_debut",
        "duree": "duree_minutes",
        "statut": "statut",
        "agent": "agent__nom",
        "type": "type_heure__code",
    }
    column = sorts.get(params.get("tri") or "date", "date_travail")
    prefix = "" if params.get("ordre") == "asc" else "-"
    return queryset.order_by(f"{prefix}{column}", "-id")


def pending_for_user(user):
    from apps.overtime.models import OvertimeRequest

    queryset = overtime_for_user(user).filter(
        statut=OvertimeRequest.Statut.EN_VALIDATION,
        current_step__isnull=False,
    )
    if user.is_superuser:
        profile = get_profile(user)
        if profile.agent_id:
            queryset = queryset.exclude(agent_id=profile.agent_id)
        return queryset
    queryset = queryset.filter(current_step__groupes__in=user.groups.all())
    if not user.has_perm("overtime.validate_all_overtime"):
        service_ids = managed_service_ids(user)
        queryset = queryset.filter(agent__service_id__in=service_ids or [])
    profile = get_profile(user)
    if profile.agent_id:
        queryset = queryset.exclude(agent_id=profile.agent_id)
    return queryset.distinct()
