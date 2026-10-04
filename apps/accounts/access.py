"""Accès au profil et au périmètre d'un utilisateur."""


def get_profile(user):
    """Retourne le profil, et le crée s'il n'existe pas encore."""
    from apps.accounts.models import UserProfile

    cached = getattr(user, "_profile_cache", None)
    if cached is not None:
        return cached
    profile, _created = UserProfile.objects.select_related("agent", "agent__service", "service").get_or_create(
        user=user
    )
    user._profile_cache = profile
    return profile


def is_own_agent(user, agent_id):
    if not agent_id:
        return False
    profile = get_profile(user)
    return profile.agent_id == agent_id
