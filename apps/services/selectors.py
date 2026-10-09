"""Sélection des services visibles et du périmètre hiérarchique."""


def appliquer_activite(service, actif):
    """Active ou désactive un service et toutes les unités qui en dépendent."""
    from django.utils import timezone

    from apps.services.models import Service

    identifiants = descendant_ids(service.pk)
    return Service.objects.filter(pk__in=identifiants).update(
        actif=actif,
        updated_at=timezone.now(),
    )


def descendant_ids(service_id):
    """Identifiants du service et de tous ses sous-services."""
    from apps.services.models import Service

    if not service_id:
        return set()
    collected = {service_id}
    frontier = [service_id]
    while frontier:
        children = list(
            Service.objects.filter(service_parent_id__in=frontier).values_list("id", flat=True)
        )
        frontier = [child for child in children if child not in collected]
        collected.update(frontier)
    return collected


def managed_service_ids(user):
    from apps.accounts.access import get_profile

    profile = get_profile(user)
    if not profile.service_id:
        return set()
    return descendant_ids(profile.service_id)


def services_pour_affectation(conserver_id=None):
    """Services proposés pour l'affectation d'un agent.

    Une unité n'est proposée que si elle est active et qu'elle appartient à une
    direction active. Les secrétariats et postes rattachés seulement à une
    direction générale inactive restent hors de la liste.
    """
    from apps.services.models import Service

    lignes = {
        pk: (actif, niveau, parent_id)
        for pk, actif, niveau, parent_id in Service.objects.values_list(
            "pk", "actif", "niveau", "service_parent_id"
        )
    }

    def direction_active(pk):
        vus = set()
        courant = pk
        while courant and courant not in vus:
            vus.add(courant)
            actif, niveau, parent_id = lignes[courant]
            if niveau == Service.Niveau.DIRECTION:
                return actif
            courant = parent_id
        return None

    choisis = []
    for pk, (actif, niveau, _parent_id) in lignes.items():
        if not actif:
            continue
        if niveau == Service.Niveau.DIRECTION or direction_active(pk) is True:
            choisis.append(pk)
    if conserver_id and conserver_id not in choisis:
        choisis.append(conserver_id)
    return Service.objects.filter(pk__in=choisis)


def services_for_user(user):
    from apps.overtime.selectors import can_view_all
    from apps.services.models import Service

    queryset = Service.objects.select_related("service_parent").order_by("code")
    if user.is_superuser or can_view_all(user) or user.has_perm("services.add_service"):
        return queryset
    identifiers = managed_service_ids(user)
    if identifiers:
        return queryset.filter(pk__in=identifiers)
    return queryset.none()
