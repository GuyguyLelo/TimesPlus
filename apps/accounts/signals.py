"""Signaux d'authentification journalisés sans jamais enregistrer de mot de passe."""


_REGISTERED = False


def register_signals():
    global _REGISTERED
    if _REGISTERED:
        return
    from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed

    user_logged_in.connect(on_login, dispatch_uid="audit_login")
    user_logged_out.connect(on_logout, dispatch_uid="audit_logout")
    user_login_failed.connect(on_login_failed, dispatch_uid="audit_login_failed")
    _REGISTERED = True


def on_login(sender, request, user, **kwargs):
    from apps.audit.utils import journaliser

    journaliser(
        request=request,
        user=user,
        action="CONNEXION",
        model_name="User",
        object_id=str(user.pk),
        new_values={"username": user.get_username()},
    )


def on_logout(sender, request, user, **kwargs):
    from apps.audit.utils import journaliser

    if user is None or not getattr(user, "is_authenticated", False):
        return
    journaliser(
        request=request,
        user=user,
        action="DECONNEXION",
        model_name="User",
        object_id=str(user.pk),
        new_values={"username": user.get_username()},
    )


def on_login_failed(sender, credentials, request, **kwargs):
    from apps.audit.utils import journaliser

    username = ""
    if isinstance(credentials, dict):
        username = str(credentials.get("username", ""))[:150]
    journaliser(
        request=request,
        user=None,
        action="CONNEXION_ECHOUEE",
        model_name="User",
        object_id=username,
        new_values={"username": username},
    )
