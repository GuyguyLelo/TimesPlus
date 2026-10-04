"""Horaires, jours fériés, types et règles de calcul."""

from django.contrib import messages
from django.db.models import F, ProtectedError
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from apps.accounts.mixins import AppPermissionMixin, PageSizeMixin
from apps.audit.utils import journaliser, model_snapshot
from apps.overtime.forms import HolidayForm, OvertimeRuleForm, OvertimeTypeForm, WorkScheduleForm
from apps.overtime.models import Holiday, OvertimeRule, OvertimeType, WorkSchedule


class _AuditedSaveMixin:
    audit_action_change = "MODIFICATION"

    def form_valid(self, form):
        instance = getattr(self, "object", None)
        created = instance is None or not getattr(instance, "pk", None)
        old = None
        if not created:
            old = model_snapshot(self.model.objects.get(pk=instance.pk))
            action = self.audit_action_change
        else:
            action = "CREATION"
        response = super().form_valid(form)
        journaliser(
            request=self.request,
            action=action,
            instance=self.object,
            old_values=old,
            new_values=model_snapshot(self.object),
        )
        messages.success(self.request, self.success_message)
        return response


class ScheduleListView(PageSizeMixin, AppPermissionMixin, ListView):
    permission_required = "overtime.view_workschedule"
    model = WorkSchedule
    template_name = "overtime/schedule_list.html"
    context_object_name = "horaires"

    def get_queryset(self):
        return WorkSchedule.objects.select_related("service").order_by(
            F("service__code").asc(nulls_first=True),
            "jour_semaine",
            "heure_debut",
        )


class ScheduleCreateView(_AuditedSaveMixin, AppPermissionMixin, CreateView):
    permission_required = "overtime.manage_rules"
    model = WorkSchedule
    form_class = WorkScheduleForm
    template_name = "overtime/simple_form.html"
    success_url = reverse_lazy("overtime:schedules")
    success_message = "✓ Horaire enregistré avec succès."
    extra_context = {"title": "Nouvel horaire"}


class ScheduleUpdateView(_AuditedSaveMixin, AppPermissionMixin, UpdateView):
    permission_required = "overtime.manage_rules"
    model = WorkSchedule
    form_class = WorkScheduleForm
    template_name = "overtime/simple_form.html"
    success_url = reverse_lazy("overtime:schedules")
    success_message = "✓ Horaire modifié avec succès."
    extra_context = {"title": "Modifier l'horaire"}


class ScheduleDeleteView(AppPermissionMixin, DeleteView):
    permission_required = "overtime.manage_rules"
    model = WorkSchedule
    template_name = "confirm.html"
    success_url = reverse_lazy("overtime:schedules")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Supprimer l'horaire"
        context["message"] = f"Confirmez la suppression de {self.object}."
        context["cancel_url"] = reverse("overtime:schedules")
        return context

    def form_valid(self, form):
        snapshot = model_snapshot(self.object)
        object_id = str(self.object.pk)
        response = super().form_valid(form)
        journaliser(request=self.request, action="SUPPRESSION", model_name="WorkSchedule", object_id=object_id, old_values=snapshot)
        messages.success(self.request, "✓ Horaire supprimé.")
        return response


class HolidayListView(PageSizeMixin, AppPermissionMixin, ListView):
    permission_required = "overtime.view_holiday"
    template_name = "overtime/holiday_list.html"
    context_object_name = "jours"

    def get_queryset(self):
        queryset = Holiday.objects.all()
        q = self.request.GET.get("q", "").strip()
        if q:
            queryset = queryset.filter(libelle__icontains=q)
        return queryset.order_by("date")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.request.GET.get("q", "")
        return context


class HolidayCreateView(_AuditedSaveMixin, AppPermissionMixin, CreateView):
    permission_required = "overtime.manage_rules"
    model = Holiday
    form_class = HolidayForm
    template_name = "overtime/simple_form.html"
    success_url = reverse_lazy("overtime:holidays")
    success_message = "✓ Jour férié enregistré avec succès."
    extra_context = {"title": "Nouveau jour férié"}


class HolidayUpdateView(_AuditedSaveMixin, AppPermissionMixin, UpdateView):
    permission_required = "overtime.manage_rules"
    model = Holiday
    form_class = HolidayForm
    template_name = "overtime/simple_form.html"
    success_url = reverse_lazy("overtime:holidays")
    success_message = "✓ Jour férié modifié avec succès."
    extra_context = {"title": "Modifier le jour férié"}


class HolidayDeleteView(AppPermissionMixin, DeleteView):
    permission_required = "overtime.manage_rules"
    model = Holiday
    template_name = "confirm.html"
    success_url = reverse_lazy("overtime:holidays")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Supprimer le jour férié"
        context["message"] = f"Confirmez la suppression de {self.object}."
        context["cancel_url"] = reverse("overtime:holidays")
        return context

    def form_valid(self, form):
        snapshot = model_snapshot(self.object)
        object_id = str(self.object.pk)
        response = super().form_valid(form)
        journaliser(request=self.request, action="SUPPRESSION", model_name="Holiday", object_id=object_id, old_values=snapshot)
        messages.success(self.request, "✓ Jour férié supprimé.")
        return response


class TypeListView(PageSizeMixin, AppPermissionMixin, ListView):
    permission_required = "overtime.manage_rules"
    model = OvertimeType
    template_name = "overtime/type_list.html"
    context_object_name = "types"


class TypeCreateView(_AuditedSaveMixin, AppPermissionMixin, CreateView):
    permission_required = "overtime.manage_rules"
    model = OvertimeType
    form_class = OvertimeTypeForm
    template_name = "overtime/simple_form.html"
    success_url = reverse_lazy("overtime:types")
    success_message = "✓ Type d'heure enregistré avec succès."
    extra_context = {"title": "Nouveau type d'heure"}


class TypeUpdateView(_AuditedSaveMixin, AppPermissionMixin, UpdateView):
    permission_required = "overtime.manage_rules"
    model = OvertimeType
    form_class = OvertimeTypeForm
    template_name = "overtime/simple_form.html"
    success_url = reverse_lazy("overtime:types")
    success_message = "✓ Type d'heure modifié avec succès."
    audit_action_change = "MODIFICATION_REGLE"
    extra_context = {"title": "Modifier le type d'heure"}


class RuleListView(PageSizeMixin, AppPermissionMixin, ListView):
    permission_required = "overtime.manage_rules"
    template_name = "overtime/rule_list.html"
    context_object_name = "regles"

    def get_queryset(self):
        return OvertimeRule.objects.select_related("type_heure")


class RuleCreateView(_AuditedSaveMixin, AppPermissionMixin, CreateView):
    permission_required = "overtime.manage_rules"
    model = OvertimeRule
    form_class = OvertimeRuleForm
    template_name = "overtime/simple_form.html"
    success_url = reverse_lazy("overtime:rules")
    success_message = "✓ Règle de calcul enregistrée avec succès."
    extra_context = {"title": "Nouvelle règle de calcul"}


class RuleUpdateView(_AuditedSaveMixin, AppPermissionMixin, UpdateView):
    permission_required = "overtime.manage_rules"
    model = OvertimeRule
    form_class = OvertimeRuleForm
    template_name = "overtime/simple_form.html"
    success_url = reverse_lazy("overtime:rules")
    success_message = "✓ Règle de calcul modifiée avec succès."
    audit_action_change = "MODIFICATION_REGLE"
    extra_context = {"title": "Modifier la règle de calcul"}


class RuleDeleteView(AppPermissionMixin, DeleteView):
    permission_required = "overtime.manage_rules"
    model = OvertimeRule
    template_name = "confirm.html"
    success_url = reverse_lazy("overtime:rules")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Supprimer la règle"
        context["message"] = (
            "Une règle déjà utilisée par une déclaration ne peut pas être supprimée. "
            "Désactivez-la pour qu'elle ne s'applique plus aux nouveaux calculs."
        )
        context["cancel_url"] = reverse("overtime:rules")
        return context

    def form_valid(self, form):
        snapshot = model_snapshot(self.object)
        object_id = str(self.object.pk)
        try:
            response = super().form_valid(form)
        except ProtectedError:
            messages.error(self.request, "Cette règle est utilisée par des déclarations et ne peut pas être supprimée.")
            return redirect("overtime:rules")
        journaliser(
            request=self.request,
            action="MODIFICATION_REGLE",
            model_name="OvertimeRule",
            object_id=object_id,
            old_values=snapshot,
        )
        messages.success(self.request, "✓ Règle supprimée.")
        return response
