from django.contrib import messages
from django.db.models import ProtectedError
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from apps.accounts.mixins import AppPermissionMixin, PageSizeMixin
from apps.agents.forms import BaremeForm
from apps.agents.models import Bareme
from apps.audit.utils import journaliser, model_snapshot


class _AuditedSaveMixin:
    def form_valid(self, form):
        instance = getattr(self, "object", None)
        created = instance is None or not getattr(instance, "pk", None)
        old = None if created else model_snapshot(Bareme.objects.get(pk=instance.pk))
        response = super().form_valid(form)
        journaliser(
            request=self.request,
            action="CREATION" if created else "MODIFICATION",
            instance=self.object,
            old_values=old,
            new_values=model_snapshot(self.object),
        )
        messages.success(self.request, self.success_message)
        return response


class BaremeListView(PageSizeMixin, AppPermissionMixin, ListView):
    permission_required = "overtime.manage_rules"
    model = Bareme
    template_name = "agents/bareme_list.html"
    context_object_name = "baremes"

    def get_queryset(self):
        return Bareme.objects.select_related("grade", "fonction").order_by(
            "grade__ordre",
            "fonction__ordre",
        )


class BaremeCreateView(_AuditedSaveMixin, AppPermissionMixin, CreateView):
    permission_required = "overtime.manage_rules"
    model = Bareme
    form_class = BaremeForm
    template_name = "agents/bareme_form.html"
    success_url = reverse_lazy("agents:bareme")
    success_message = "✓ Barème enregistré avec succès."
    extra_context = {"title": "Nouveau barème"}


class BaremeUpdateView(_AuditedSaveMixin, AppPermissionMixin, UpdateView):
    permission_required = "overtime.manage_rules"
    model = Bareme
    form_class = BaremeForm
    template_name = "agents/bareme_form.html"
    success_url = reverse_lazy("agents:bareme")
    success_message = "✓ Barème modifié avec succès."
    extra_context = {"title": "Modifier le barème"}


class BaremeDeleteView(AppPermissionMixin, DeleteView):
    permission_required = "overtime.manage_rules"
    model = Bareme
    template_name = "confirm.html"
    success_url = reverse_lazy("agents:bareme")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Supprimer le barème"
        context["message"] = (
            f"Confirmez la suppression du barème {self.object.grade} — {self.object.fonction}."
        )
        context["cancel_url"] = reverse("agents:bareme")
        return context

    def form_valid(self, form):
        snapshot = model_snapshot(self.object)
        object_id = str(self.object.pk)
        try:
            response = super().form_valid(form)
        except ProtectedError:
            messages.error(self.request, "Ce barème ne peut pas être supprimé.")
            return redirect("agents:bareme")
        journaliser(
            request=self.request,
            action="SUPPRESSION",
            model_name="Bareme",
            object_id=object_id,
            old_values=snapshot,
        )
        messages.success(self.request, "✓ Barème supprimé.")
        return response
