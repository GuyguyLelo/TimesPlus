"""Sélection des déclarations entrant dans un rapport."""

from datetime import datetime

from django.db.models import Count, Prefetch, Sum

from apps.overtime.models import OvertimeRequest
from apps.overtime.selectors import overtime_for_user
from apps.workflow.models import ValidationDecision


def parse_report_params(data):
    def parse_date(value):
        if not value:
            return None
        if hasattr(value, "year"):
            return value
        try:
            return datetime.strptime(str(value), "%Y-%m-%d").date()
        except ValueError:
            return None

    statut = data.get("statut") or OvertimeRequest.Statut.APPROUVE
    return {
        "debut": parse_date(data.get("debut")),
        "fin": parse_date(data.get("fin")),
        "service": data.get("service") or "",
        "agent": data.get("agent") or "",
        "statut": statut,
        "type_heure": data.get("type_heure") or "",
    }


def report_queryset(user, params):
    queryset = overtime_for_user(user)
    if params.get("debut"):
        queryset = queryset.filter(date_travail__gte=params["debut"])
    if params.get("fin"):
        queryset = queryset.filter(date_travail__lte=params["fin"])
    if str(params.get("service") or "").isdigit():
        queryset = queryset.filter(agent__service_id=int(params["service"]))
    if str(params.get("agent") or "").isdigit():
        queryset = queryset.filter(agent_id=int(params["agent"]))
    statut = params.get("statut") or OvertimeRequest.Statut.APPROUVE
    if statut != "TOUS":
        queryset = queryset.filter(statut=statut)
    if str(params.get("type_heure") or "").isdigit():
        queryset = queryset.filter(type_heure_id=int(params["type_heure"]))
    approvals = ValidationDecision.objects.filter(
        decision=ValidationDecision.Decision.APPROBATION
    ).select_related("utilisateur").order_by("-created_at")
    return queryset.prefetch_related(
        Prefetch("decisions", queryset=approvals, to_attr="approbations")
    ).order_by("agent__service__code", "agent__nom", "agent__prenom", "date_travail", "heure_debut")


def report_totals(queryset):
    aggregated = queryset.aggregate(
        minutes=Sum("duree_minutes"),
        montant=Sum("montant_estime"),
        nombre=Count("id"),
    )
    return {
        "minutes": aggregated["minutes"] or 0,
        "montant": aggregated["montant"] or 0,
        "nombre": aggregated["nombre"] or 0,
    }


def by_service(queryset):
    return list(
        queryset.values("agent__service__code", "agent__service__nom")
        .annotate(minutes=Sum("duree_minutes"), montant=Sum("montant_estime"), nombre=Count("id"))
        .order_by("agent__service__code")
    )


def by_type(queryset):
    return list(
        queryset.values("type_heure__code", "type_heure__libelle")
        .annotate(minutes=Sum("duree_minutes"), montant=Sum("montant_estime"), nombre=Count("id"))
        .order_by("type_heure__code")
    )


def agent_unique(queryset):
    """Retourne l'agent lorsque le rapport ne concerne qu'une seule personne."""
    identifiants = list(queryset.order_by().values_list("agent_id", flat=True).distinct()[:2])
    if len(identifiants) != 1:
        return None
    from apps.agents.models import Agent

    return (
        Agent.objects.select_related("grade", "fonction", "service")
        .filter(pk=identifiants[0])
        .first()
    )


def mois_anterieurs_payes(annee, jour=None):
    """Mois déjà payés : mois révolus et mois clôturés par la paie."""
    from apps.overtime.paiement import mois_payes_numeros

    return mois_payes_numeros(annee, jour)


def bornes_mois_payes(annee, jour=None):
    from apps.overtime.forms import _bornes_mois

    mois = mois_anterieurs_payes(annee, jour)
    if not mois:
        return None
    debut, _fin = _bornes_mois(f"{annee}-{mois[0]:02d}")
    _debut, fin = _bornes_mois(f"{annee}-{mois[-1]:02d}")
    return debut, fin


def historique_par_mois(queryset, annee, mois=None):
    """Totaux des mois antérieurs déjà payés, y compris ceux sans saisie."""
    from apps.overtime.forms import _NOMS_MOIS, _bornes_mois

    if mois is None:
        mois = mois_anterieurs_payes(annee)
    rows = []
    for month in mois:
        debut, fin = _bornes_mois(f"{annee}-{month:02d}")
        subset = queryset.filter(date_travail__gte=debut, date_travail__lte=fin)
        totals = report_totals(subset)
        rows.append(
            {
                "mois": f"{annee}-{month:02d}",
                "label": f"{_NOMS_MOIS[month - 1]} {annee}",
                "agents": subset.order_by().values("agent_id").distinct().count(),
                **totals,
            }
        )
    return rows


def by_agent(queryset):
    rows = list(
        queryset.values(
            "agent__matricule",
            "agent__nom",
            "agent__postnom",
            "agent__prenom",
            "agent__service__code",
            "agent__service__nom",
        )
        .annotate(minutes=Sum("duree_minutes"), montant=Sum("montant_estime"), nombre=Count("id"))
        .order_by("agent__service__code", "agent__nom", "agent__postnom", "agent__prenom")
    )
    for row in rows:
        row["nom"] = " ".join(
            part for part in (row["agent__nom"], row["agent__postnom"], row["agent__prenom"]) if part
        )
    return rows
