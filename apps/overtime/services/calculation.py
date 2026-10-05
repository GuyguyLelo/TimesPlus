"""Moteur de calcul des heures supplémentaires.

Aucune règle juridique ou financière n'est codée ici. Le moteur :
1. mesure la durée ;
2. classe chaque minute selon les règles actives, les jours fériés et les
   paramètres de week-end ;
3. retient la règle applicable ;
4. applique son coefficient au taux horaire du barème (grade et fonction) ;
5. produit un montant estimé et conserve la ventilation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Q, Sum
from django.utils import timezone


MSG_FIN_AVANT_DEBUT = "L'heure de fin doit être postérieure à l'heure de début."
MSG_DUREE_NULLE = "La durée doit être strictement positive."
MSG_CHEVAUCHEMENT = "⚠ Cette période chevauche une déclaration existante."
MSG_PLAFOND = "⚠ Vous avez dépassé le plafond autorisé."
MSG_SANS_REGLE = (
    "Aucune règle active ne couvre l'ensemble de la période déclarée. "
    "Contactez l'administrateur pour paramétrer les règles de calcul."
)
MSG_SANS_BAREME = (
    "Aucun barème actif ne correspond au grade et à la fonction de cet agent."
)
MSG_DATE_FUTURE = "La date de travail ne peut pas être dans le futur."
MSG_AGENT_INACTIF = "Cet agent n'est pas actif."


class CalculationError(Exception):
    """Erreur métier destinée à l'utilisateur."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


@dataclass
class Segment:
    heure_debut: time
    heure_fin: time
    minutes: int
    type_code: str
    type_id: int
    type_libelle: str
    regle_id: int
    regle_nom: str
    priorite: int
    coefficient: Decimal
    montant: Decimal


@dataclass
class CalculationResult:
    duree_minutes: int
    type_id: int
    type_code: str
    type_libelle: str
    regle_id: int
    regle_nom: str
    coefficient: Decimal
    montant_estime: Decimal
    ventilation: list[dict] = field(default_factory=list)
    regle_ids: list[int] = field(default_factory=list)


def normalize_time(value: time) -> time:
    return time(value.hour, value.minute)


def _minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def _from_minutes(value: int) -> time:
    bounded = max(0, min(value, 23 * 60 + 59))
    return time(bounded // 60, bounded % 60)


def compute_duration_minutes(heure_debut: time, heure_fin: time) -> int:
    """Durée en minutes. Le serveur ignore toute durée envoyée par le navigateur."""
    heure_debut = normalize_time(heure_debut)
    heure_fin = normalize_time(heure_fin)
    if heure_fin <= heure_debut:
        raise CalculationError(MSG_FIN_AVANT_DEBUT)
    start = datetime.combine(date.min, heure_debut)
    end = datetime.combine(date.min, heure_fin)
    minutes = int((end - start).total_seconds() // 60)
    if minutes <= 0:
        raise CalculationError(MSG_DUREE_NULLE)
    return minutes


def _rule_window(rule):
    if rule.heure_debut is None or rule.heure_fin is None:
        return None
    return _minutes(rule.heure_debut), _minutes(rule.heure_fin)


def _minute_in_window(minute: int, start: int, end: int) -> bool:
    if start == end:
        return False
    if start < end:
        return start <= minute < end
    return minute >= start or minute < end


def _rule_applies_to_day(rule, *, is_holiday: bool, is_weekend: bool) -> bool:
    if is_holiday:
        return rule.applicable_ferie
    if is_weekend:
        return rule.applicable_weekend
    return not rule.applicable_ferie and not rule.applicable_weekend


def _active_rules(jour: date):
    from apps.overtime.models import OvertimeRule

    return list(
        OvertimeRule.objects.filter(actif=True, type_heure__actif=True)
        .filter(Q(date_debut_validite__isnull=True) | Q(date_debut_validite__lte=jour))
        .filter(Q(date_fin_validite__isnull=True) | Q(date_fin_validite__gte=jour))
        .select_related("type_heure")
        .order_by("priorite", "id")
    )


def _winning_rule(rules, minute, *, is_holiday, is_weekend):
    for rule in rules:
        if not _rule_applies_to_day(rule, is_holiday=is_holiday, is_weekend=is_weekend):
            continue
        window = _rule_window(rule)
        if window is None or _minute_in_window(minute, window[0], window[1]):
            return rule
    return None


def _money(hours: Decimal, taux: Decimal, coefficient: Decimal) -> Decimal:
    return (hours * taux * coefficient).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def classify_period(jour: date, heure_debut: time, heure_fin: time, agent) -> CalculationResult:
    """Classe la période et calcule le montant à partir des règles en base."""
    from apps.agents.models import taux_horaire_bareme
    from apps.overtime.models import Holiday
    from apps.settings_app.models import SiteSettings

    heure_debut = normalize_time(heure_debut)
    heure_fin = normalize_time(heure_fin)
    duration = compute_duration_minutes(heure_debut, heure_fin)
    settings_obj = SiteSettings.load()
    is_holiday = Holiday.objects.filter(date=jour, actif=True).exists()
    is_weekend = jour.weekday() in settings_obj.jours_weekend_set()
    rules = _active_rules(jour)
    if not rules:
        raise CalculationError(MSG_SANS_REGLE)

    start_m = _minutes(heure_debut)
    end_m = _minutes(heure_fin)
    raw_segments = []
    current = None
    seg_start = start_m
    for minute in range(start_m, end_m):
        rule = _winning_rule(rules, minute, is_holiday=is_holiday, is_weekend=is_weekend)
        if rule is None:
            raise CalculationError(MSG_SANS_REGLE)
        if current is None:
            current = rule
            seg_start = minute
        elif rule.id != current.id:
            raw_segments.append((seg_start, minute, current))
            current = rule
            seg_start = minute
    raw_segments.append((seg_start, end_m, current))

    if not getattr(agent, "grade_id", None) or not getattr(agent, "fonction_id", None):
        raise CalculationError(MSG_SANS_BAREME)
    taux = taux_horaire_bareme(agent)
    if taux is None:
        raise CalculationError(MSG_SANS_BAREME)
    segments: list[Segment] = []
    total = Decimal("0.00")
    for seg_start, seg_end, rule in raw_segments:
        minutes = seg_end - seg_start
        coefficient = rule.coefficient
        montant = _money(Decimal(minutes) / Decimal(60), taux, coefficient)
        total += montant
        segments.append(
            Segment(
                heure_debut=_from_minutes(seg_start),
                heure_fin=_from_minutes(seg_end),
                minutes=minutes,
                type_code=rule.type_heure.code,
                type_id=rule.type_heure_id,
                type_libelle=rule.type_heure.libelle,
                regle_id=rule.id,
                regle_nom=rule.nom,
                priorite=rule.priorite,
                coefficient=coefficient,
                montant=montant,
            )
        )

    primary = max(segments, key=lambda item: (item.minutes, -item.priorite))
    ventilation = [
        {
            "debut": segment.heure_debut.strftime("%H:%M"),
            "fin": segment.heure_fin.strftime("%H:%M"),
            "minutes": segment.minutes,
            "type_code": segment.type_code,
            "type_libelle": segment.type_libelle,
            "regle_id": segment.regle_id,
            "regle_nom": segment.regle_nom,
            "coefficient": str(segment.coefficient),
            "montant": str(segment.montant),
        }
        for segment in segments
    ]
    return CalculationResult(
        duree_minutes=duration,
        type_id=primary.type_id,
        type_code=primary.type_code,
        type_libelle=primary.type_libelle,
        regle_id=primary.regle_id,
        regle_nom=primary.regle_nom,
        coefficient=primary.coefficient,
        montant_estime=total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        ventilation=ventilation,
        regle_ids=sorted({segment.regle_id for segment in segments}),
    )


def _blocking_statuses():
    from apps.overtime.models import OvertimeRequest

    return [
        OvertimeRequest.Statut.BROUILLON,
        OvertimeRequest.Statut.SOUMIS,
        OvertimeRequest.Statut.EN_VALIDATION,
        OvertimeRequest.Statut.APPROUVE,
    ]


def find_overlap(agent, jour, heure_debut, heure_fin, exclude_id=None):
    from apps.overtime.models import OvertimeRequest

    heure_debut = normalize_time(heure_debut)
    heure_fin = normalize_time(heure_fin)
    queryset = OvertimeRequest.objects.filter(
        agent=agent,
        date_travail=jour,
        statut__in=_blocking_statuses(),
    )
    if exclude_id:
        queryset = queryset.exclude(pk=exclude_id)
    start = _minutes(heure_debut)
    end = _minutes(heure_fin)
    for other in queryset.only("id", "heure_debut", "heure_fin", "date_travail"):
        other_start = _minutes(other.heure_debut)
        other_end = _minutes(other.heure_fin)
        if start < other_end and other_start < end:
            return other
    return None


def assert_within_ceilings(agent, jour, minutes, regle_ids, exclude_id=None):
    from apps.overtime.models import OvertimeRequest, OvertimeRule
    from apps.settings_app.models import SiteSettings

    settings_obj = SiteSettings.load()
    rules = list(OvertimeRule.objects.filter(pk__in=regle_ids))
    daily_caps = [rule.plafond_journalier for rule in rules if rule.plafond_journalier is not None]
    monthly_caps = [rule.plafond_mensuel for rule in rules if rule.plafond_mensuel is not None]
    if settings_obj.plafond_journalier_minutes is not None:
        daily_caps.append(settings_obj.plafond_journalier_minutes)
    if settings_obj.plafond_mensuel_minutes is not None:
        monthly_caps.append(settings_obj.plafond_mensuel_minutes)

    queryset = OvertimeRequest.objects.filter(agent=agent, statut__in=_blocking_statuses())
    if exclude_id:
        queryset = queryset.exclude(pk=exclude_id)

    if daily_caps:
        used = queryset.filter(date_travail=jour).aggregate(total=Sum("duree_minutes"))["total"] or 0
        if used + minutes > min(daily_caps):
            raise CalculationError(MSG_PLAFOND)
    if monthly_caps:
        used = queryset.filter(
            date_travail__year=jour.year,
            date_travail__month=jour.month,
        ).aggregate(total=Sum("duree_minutes"))["total"] or 0
        if used + minutes > min(monthly_caps):
            raise CalculationError(MSG_PLAFOND)


def calculer_declaration(agent, jour, heure_debut, heure_fin, exclude_id=None) -> CalculationResult:
    """Point d'entrée : durée, classification, chevauchement et plafonds."""
    from apps.agents.models import Agent
    from apps.settings_app.models import SiteSettings

    settings_obj = SiteSettings.load()
    if not settings_obj.autoriser_agent_inactif:
        if not agent.actif or agent.statut != Agent.Statut.ACTIF:
            raise CalculationError(MSG_AGENT_INACTIF)
    if not settings_obj.autoriser_date_future and jour > timezone.localdate():
        raise CalculationError(MSG_DATE_FUTURE)

    result = classify_period(jour, heure_debut, heure_fin, agent)
    if find_overlap(agent, jour, heure_debut, heure_fin, exclude_id=exclude_id):
        raise CalculationError(MSG_CHEVAUCHEMENT)
    assert_within_ceilings(
        agent,
        jour,
        result.duree_minutes,
        result.regle_ids,
        exclude_id=exclude_id,
    )
    return result
