"""Circuit de validation configurable.

Parcours par défaut, créé par les données de démonstration :

brouillon → soumis → en validation (chef de service)
    → rejet, ou étape suivante (validation RH)
        → rejet, ou approuvé.
"""

from django.db import transaction
from django.utils import timezone

from apps.accounts.access import get_profile, is_own_agent
from apps.audit.utils import get_client_ip, journaliser
from apps.services.selectors import managed_service_ids


class WorkflowError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def workflow_actif():
    from apps.workflow.models import WorkflowDefinition

    return (
        WorkflowDefinition.objects.filter(actif=True)
        .prefetch_related("etapes__groupes")
        .order_by("id")
        .first()
    )


def _premiere_etape(workflow):
    if workflow is None:
        return None
    return workflow.etapes.order_by("ordre").first()


def _etape_suivante(etape):
    if etape is None:
        return None
    return (
        etape.workflow.etapes.filter(ordre__gt=etape.ordre)
        .order_by("ordre")
        .first()
    )


def peut_decider(user, demande, permission):
    """Un agent ne valide pas sa propre demande, et seulement dans son périmètre."""
    from apps.overtime.models import OvertimeRequest

    if not user.is_authenticated:
        return False
    if not user.is_superuser and not user.has_perm(permission):
        return False
    if is_own_agent(user, demande.agent_id):
        return False
    if demande.statut != OvertimeRequest.Statut.EN_VALIDATION or demande.current_step_id is None:
        return False
    etape = demande.current_step
    if user.is_superuser:
        return True
    if not etape.groupes.filter(pk__in=user.groups.values("pk")).exists():
        return False
    if etape.limiter_au_service and not user.has_perm("overtime.validate_all_overtime"):
        if demande.agent.service_id not in managed_service_ids(user):
            return False
    return True


def _evenement(demande, user, action, ancien, nouveau, commentaire, ip):
    from apps.workflow.models import RequestEvent

    RequestEvent.objects.create(
        demande=demande,
        utilisateur=user,
        action=action,
        commentaire=commentaire or "",
        ancien_statut=ancien,
        nouveau_statut=nouveau,
        ip_address=ip,
    )


def _journal(request, user, action, demande, ancien, nouveau, commentaire=""):
    journaliser(
        request=request,
        user=user,
        action=action,
        instance=demande,
        old_values={"statut": ancien},
        new_values={
            "statut": nouveau,
            "commentaire": commentaire,
            "etape": demande.current_step.libelle if demande.current_step_id else "",
        },
    )


@transaction.atomic
def soumettre(demande, user, request=None):
    from apps.overtime.models import OvertimeRequest
    from apps.overtime.services.calculation import CalculationError, calculer_declaration

    if not user.has_perm("overtime.submit_overtime") and not user.is_superuser:
        raise WorkflowError("⚠ Vous n'êtes pas autorisé à effectuer cette opération.")
    if demande.statut not in {OvertimeRequest.Statut.BROUILLON, OvertimeRequest.Statut.REJETE}:
        raise WorkflowError("Seule une demande en brouillon ou rejetée peut être soumise.")
    profile = get_profile(user)
    if not user.has_perm("overtime.view_all_overtime") and not user.is_superuser:
        if not profile.agent_id or profile.agent_id != demande.agent_id:
            raise WorkflowError("⚠ Vous n'êtes pas autorisé à effectuer cette opération.")

    try:
        result = calculer_declaration(
            demande.agent,
            demande.date_travail,
            demande.heure_debut,
            demande.heure_fin,
            exclude_id=demande.pk,
        )
    except CalculationError as exc:
        raise WorkflowError(exc.message) from exc

    demande.duree_minutes = result.duree_minutes
    demande.type_heure_id = result.type_id
    demande.regle_appliquee_id = result.regle_id
    demande.coefficient_applique = result.coefficient
    demande.montant_estime = result.montant_estime
    demande.ventilation = result.ventilation

    ancien = demande.statut
    ip = get_client_ip(request)
    workflow = workflow_actif()
    etape = _premiere_etape(workflow)
    demande.submitted_at = timezone.now()
    demande.approved_at = None
    if etape is None:
        demande.statut = OvertimeRequest.Statut.SOUMIS
        demande.current_step = None
    else:
        demande.statut = OvertimeRequest.Statut.EN_VALIDATION
        demande.current_step = etape
    demande.save()
    _evenement(demande, user, "SOUMISSION", ancien, demande.statut, "", ip)
    _journal(request, user, "SOUMISSION", demande, ancien, demande.statut)
    return demande


@transaction.atomic
def approuver(demande, user, request=None, commentaire=""):
    from apps.overtime.models import OvertimeRequest
    from apps.workflow.models import ValidationDecision

    if not peut_decider(user, demande, "overtime.approve_overtime"):
        raise WorkflowError("⚠ Vous n'êtes pas autorisé à effectuer cette opération.")

    etape = demande.current_step
    ip = get_client_ip(request)
    ValidationDecision.objects.create(
        demande=demande,
        etape=etape,
        utilisateur=user,
        decision=ValidationDecision.Decision.APPROBATION,
        commentaire=(commentaire or "").strip(),
        ip_address=ip,
    )
    ancien = demande.statut
    suivante = _etape_suivante(etape)
    if suivante is not None:
        demande.current_step = suivante
        demande.statut = OvertimeRequest.Statut.EN_VALIDATION
        action = "APPROBATION"
    else:
        demande.current_step = None
        demande.statut = OvertimeRequest.Statut.APPROUVE
        demande.approved_at = timezone.now()
        action = "APPROBATION"
    demande.save()
    _evenement(demande, user, action, ancien, demande.statut, commentaire, ip)
    _journal(request, user, "APPROBATION", demande, ancien, demande.statut, commentaire)
    if demande.statut != ancien:
        journaliser(
            request=request,
            user=user,
            action="CHANGEMENT_STATUT",
            instance=demande,
            old_values={"statut": ancien},
            new_values={"statut": demande.statut},
        )
    return demande


@transaction.atomic
def rejeter(demande, user, request=None, commentaire=""):
    from apps.overtime.models import OvertimeRequest
    from apps.workflow.models import ValidationDecision

    motif = (commentaire or "").strip()
    if not motif:
        raise WorkflowError("Le motif du rejet est obligatoire.")
    if not peut_decider(user, demande, "overtime.reject_overtime"):
        raise WorkflowError("⚠ Vous n'êtes pas autorisé à effectuer cette opération.")

    ip = get_client_ip(request)
    ValidationDecision.objects.create(
        demande=demande,
        etape=demande.current_step,
        utilisateur=user,
        decision=ValidationDecision.Decision.REJET,
        commentaire=motif,
        ip_address=ip,
    )
    ancien = demande.statut
    demande.statut = OvertimeRequest.Statut.REJETE
    demande.current_step = None
    demande.save()
    _evenement(demande, user, "REJET", ancien, demande.statut, motif, ip)
    _journal(request, user, "REJET", demande, ancien, demande.statut, motif)
    journaliser(
        request=request,
        user=user,
        action="CHANGEMENT_STATUT",
        instance=demande,
        old_values={"statut": ancien},
        new_values={"statut": demande.statut, "commentaire": motif},
    )
    return demande


@transaction.atomic
def annuler(demande, user, request=None, commentaire=""):
    from apps.overtime.models import OvertimeRequest

    if demande.statut != OvertimeRequest.Statut.BROUILLON:
        raise WorkflowError("Seule une demande en brouillon peut être annulée.")
    if not user.is_superuser and not is_own_agent(user, demande.agent_id):
        if not user.has_perm("overtime.change_overtime"):
            raise WorkflowError("⚠ Vous n'êtes pas autorisé à effectuer cette opération.")
    ancien = demande.statut
    demande.statut = OvertimeRequest.Statut.ANNULE
    demande.current_step = None
    demande.save()
    ip = get_client_ip(request)
    _evenement(demande, user, "ANNULATION", ancien, demande.statut, commentaire, ip)
    _journal(request, user, "CHANGEMENT_STATUT", demande, ancien, demande.statut, commentaire)
    return demande
