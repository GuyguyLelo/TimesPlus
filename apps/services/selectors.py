"""Sélection des services visibles et du périmètre hiérarchique."""


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
