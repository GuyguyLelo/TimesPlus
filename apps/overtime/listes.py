"""Liste journalière des heures supplémentaires et signatures."""

from apps.accounts.access import get_profile
from apps.overtime.models import ListeJournaliere, SignatureListe
from apps.overtime.selectors import can_view_all, overtime_for_user
from apps.services.selectors import managed_service_ids

_CADRE_FONCTIONS = {"SG", "DG", "DIR", "CD", "CB", "DRH", "DAF", "DEP", "DANTIC"}
_CADRE_GRADES = {"SG", "DG", "DIR", "CD-2", "CD-1", "CB-2", "CB-1"}


def est_cadre(agent):
    if agent is None:
        return False
    fonction = agent.fonction.code if agent.fonction_id else ""
    grade = agent.grade.code if agent.grade_id else ""
    return fonction in _CADRE_FONCTIONS or grade in _CADRE_GRADES


def assurer_liste(demande):
    if demande.liste_id:
        return demande.liste
    liste, _created = ListeJournaliere.objects.get_or_create(
        date=demande.date_travail,
        service_id=demande.agent.service_id,
    )
    demande.liste = liste
    demande.save(update_fields=["liste", "updated_at"])
    return liste


def _couvre(user, agent, service_id):
    if can_view_all(user) or user.is_superuser:
        return True
    if agent.service_id == service_id:
        return True
    return service_id in managed_service_ids(user)


def listes_du_jour(user, jour):
    lignes = (
        overtime_for_user(user)
        .filter(date_travail=jour)
        .select_related("agent", "agent__service", "agent__fonction", "agent__grade", "liste")
        .order_by("agent__service__code", "agent__nom", "heure_fin")
    )
    groupes = {}
    for ligne in lignes:
        liste = assurer_liste(ligne)
        bucket = groupes.setdefault(liste.pk, {"liste": liste, "lignes": []})
        bucket["lignes"].append(ligne)
    profil = get_profile(user).agent
    if profil is not None:
        profil = type(profil).objects.select_related("fonction", "grade", "service").get(pk=profil.pk)
    result = []
    for groupe in groupes.values():
        liste = groupe["liste"]
        signatures = list(liste.signatures.select_related("agent"))
        agents_signes = {item.agent_id for item in signatures if item.qualite == SignatureListe.Qualite.AGENT}
        cadres_signes = {item.agent_id for item in signatures if item.qualite == SignatureListe.Qualite.CADRE}
        groupe["signatures_agents"] = [item for item in signatures if item.qualite == SignatureListe.Qualite.AGENT]
        groupe["signatures_cadres"] = [item for item in signatures if item.qualite == SignatureListe.Qualite.CADRE]
        sur_la_liste = profil is not None and any(ligne.agent_id == profil.id for ligne in groupe["lignes"])
        groupe["peut_signer_agent"] = sur_la_liste and profil.id not in agents_signes
        groupe["peut_signer_cadre"] = (
            profil is not None
            and est_cadre(profil)
            and _couvre(user, profil, liste.service_id)
            and profil.id not in cadres_signes
        )
        result.append(groupe)
    return result


def signer(user, liste, qualite):
    agent = get_profile(user).agent
    if agent is None:
        return False, "Aucun agent n'est lié à ce compte."
    agent = type(agent).objects.select_related("fonction", "grade", "service").get(pk=agent.pk)
    if qualite == SignatureListe.Qualite.AGENT:
        if not liste.lignes.filter(agent=agent).exists():
            return False, "Seuls les agents inscrits sur la liste peuvent la signer."
    elif qualite == SignatureListe.Qualite.CADRE:
        if not est_cadre(agent) or not _couvre(user, agent, liste.service_id):
            return False, "Seul un cadre du service peut signer cette liste."
    else:
        return False, "Qualité de signature inconnue."
    SignatureListe.objects.get_or_create(liste=liste, agent=agent, qualite=qualite)
    return True, ""
