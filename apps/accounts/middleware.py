"""Middleware : garantit un profil pour chaque utilisateur authentifié."""


class EnsureProfileMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            from apps.accounts.access import get_profile

            get_profile(user)
        return self.get_response(request)
