from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect

DENIED = "⚠ Vous n'êtes pas autorisé à effectuer cette opération."


class AppPermissionMixin(LoginRequiredMixin, PermissionRequiredMixin):
    """Redirige vers le tableau de bord avec un message clair si l'accès est refusé."""

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect_to_login(
                self.request.get_full_path(),
                self.get_login_url(),
                self.get_redirect_field_name(),
            )
        messages.warning(self.request, DENIED)
        return redirect("dashboard:home")


class PageSizeMixin:
    """Découpe chaque liste selon le nombre d'éléments paramétré."""

    def get_paginate_by(self, queryset):
        return page_size()


def page_size():
    from apps.settings_app.models import SiteSettings

    try:
        size = int(SiteSettings.load().elements_par_page or 20)
    except Exception:
        return 20
    return min(max(size, 5), 100)
