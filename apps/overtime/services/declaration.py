"""Enregistrement transactionnel d'une déclaration."""

from django.db import transaction
from django.utils import timezone

from apps.overtime.services.calculation import calculer_declaration, normalize_time


@transaction.atomic
def enregistrer_declaration(
    *,
    agent,
    date_travail,
    heure_debut,
    heure_fin,
    motif,
    user,
    existing=None,
    observation="",
):
    """Recalcule côté serveur puis enregistre. La durée du client est ignorée."""
    from apps.overtime.models import OvertimeRequest
    from apps.overtime.paiement import verifier_saisie_ouverte

    verifier_saisie_ouverte(date_travail, existing)

    list(
        OvertimeRequest.objects.select_for_update()
        .filter(agent=agent, date_travail=date_travail)
        .only("id")
    )
    result = calculer_declaration(
        agent,
        date_travail,
        heure_debut,
        heure_fin,
        exclude_id=existing.pk if existing else None,
    )
    if existing is None:
        demande = OvertimeRequest(created_by=user)
    else:
        demande = existing
    demande.agent = agent
    demande.date_travail = date_travail
    demande.heure_debut = normalize_time(heure_debut)
    demande.heure_fin = normalize_time(heure_fin)
    demande.duree_minutes = result.duree_minutes
    demande.type_heure_id = result.type_id
    demande.regle_appliquee_id = result.regle_id
    demande.coefficient_applique = result.coefficient
    demande.montant_estime = result.montant_estime
    demande.ventilation = result.ventilation
    demande.motif = motif
    demande.observation = (observation or "").strip()
    demande.statut = OvertimeRequest.Statut.APPROUVE
    demande.current_step = None
    demande.submitted_at = None
    demande.approved_at = timezone.now()
    from apps.overtime.listes import assurer_liste

    demande.save()
    assurer_liste(demande)
    return demande, result
