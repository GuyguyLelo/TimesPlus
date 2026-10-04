from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import UpdateView

from apps.accounts.mixins import AppPermissionMixin
from apps.audit.utils import journaliser, model_snapshot
from apps.settings_app.forms import SiteSettingsForm
from apps.settings_app.models import SiteSettings


class ParametersView(AppPermissionMixin, UpdateView):
    permission_required = "overtime.manage_rules"
    form_class = SiteSettingsForm
    template_name = "settings_app/parameters.html"
    success_url = reverse_lazy("settings_app:parameters")

    def get_object(self, queryset=None):
        return SiteSettings.load()

    def form_valid(self, form):
        old = model_snapshot(SiteSettings.objects.get(pk=1)) if SiteSettings.objects.filter(pk=1).exists() else None
        response = super().form_valid(form)
        journaliser(
            request=self.request,
            action="MODIFICATION_REGLE",
            instance=self.object,
            old_values=old,
            new_values=model_snapshot(self.object),
        )
        messages.success(self.request, "✓ Paramètres enregistrés avec succès.")
        return response
