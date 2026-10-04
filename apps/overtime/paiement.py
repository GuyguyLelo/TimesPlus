"""Clôture de la paie : un mois payé est archivé et n'est plus modifiable."""

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from apps.overtime.services.calculation import CalculationError


class PaieError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(message)


def _cache_key(annee, jour):
    return f"mois-payes:{annee}:{jour.isoformat()}"


def mois_payes_numeros(annee, jour=None):
    """Mois révolus et mois dont la paie a été clôturée."""
    from apps.overtime.models import PaiementMois

    jour = jour or timezone.localdate()
    key = _cache_key(annee, jour)
    cached = cache.get(key)
    if cached is not None:
        return cached
    if jour.year < annee:
        numeros = set()
    elif jour.year > annee:
        numeros = set(range(1, 13))
    else:
        numeros = set(range(1, jour.month))
    numeros.update(PaiementMois.objects.filter(annee=annee).values_list("mois", flat=True))
    resultat = sorted(numeros)
    cache.set(key, resultat, 60)
    return resultat


def mois_est_paye(annee, mois, jour=None):
    return mois in mois_payes_numeros(annee, jour)


def mois_ouverts(annee, jour=None):
    """Mois qui acceptent encore une saisie."""
    fermes = set(mois_payes_numeros(annee, jour))
    return [month for month in range(1, 13) if month not in fermes]


def invalider_mois_payes(annee, jour=None):
    jour = jour or timezone.localdate()
    cache.delete(_cache_key(annee, jour))


def verifier_saisie_ouverte(date_travail, existing=None):
    if existing is not None and mois_est_paye(existing.date_travail.year, existing.date_travail.month):
        raise CalculationError(
            "Les heures supplémentaires de ce mois sont payées et ne peuvent plus être modifiées."
        )
    if mois_est_paye(date_travail.year, date_travail.month):
        raise CalculationError(
            "Ce mois est clôturé. Les heures supplémentaires payées ne peuvent plus être saisies."
        )


def cloturer_paie(user, jour=None):
    """Archive le mois en cours. Les saisies de ce mois ne peuvent plus être modifiées."""
    from calendar import monthrange

    from apps.overtime.forms import ANNEE_MOIS
    from apps.overtime.models import OvertimeRequest, PaiementMois
    from apps.reports.services import report_totals

    aujourdhui = timezone.localdate()
    jour = jour or aujourdhui
    if jour.year != ANNEE_MOIS or (jour.year, jour.month) != (aujourdhui.year, aujourdhui.month):
        raise PaieError("La clôture porte sur le mois en cours.")
    if PaiementMois.objects.filter(annee=jour.year, mois=jour.month).exists():
        raise PaieError("La paie de ce mois est déjà clôturée.")
    debut = jour.replace(day=1)
    fin = jour.replace(day=monthrange(jour.year, jour.month)[1])
    queryset = OvertimeRequest.objects.filter(
        date_travail__gte=debut,
        date_travail__lte=fin,
        statut=OvertimeRequest.Statut.APPROUVE,
    )
    totals = report_totals(queryset)
    agents = queryset.order_by().values("agent_id").distinct().count()
    with transaction.atomic():
        paiement = PaiementMois.objects.create(
            annee=jour.year,
            mois=jour.month,
            agents=agents,
            nombre=totals["nombre"],
            minutes=totals["minutes"],
            montant=totals["montant"],
            cloture_par=user if getattr(user, "is_authenticated", False) else None,
        )
    invalider_mois_payes(jour.year, jour)
    return paiement
