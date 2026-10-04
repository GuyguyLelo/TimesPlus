from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView, ListView

from apps.accounts.mixins import AppPermissionMixin, page_size
from apps.overtime.formatting import format_minutes
from apps.overtime.models import OvertimeRequest, OvertimeType
from apps.overtime.selectors import apply_overtime_filters, overtime_for_user, pending_for_user
from apps.services.selectors import services_for_user
from apps.workflow.forms import ApproveForm, RejectForm
from apps.workflow.services import WorkflowError, approuver, rejeter


class _ValidationAccess(AppPermissionMixin):
    def has_permission(self):
        user = self.request.user
        return (
            user.is_superuser
            or user.has_perm("overtime.approve_overtime")
            or user.has_perm("overtime.reject_overtime")
        )


class ValidationQueueView(_ValidationAccess, ListView):
    template_name = "workflow/queue.html"
    context_object_name = "declarations"

    def get_paginate_by(self, queryset):
        return page_size()

    def get_queryset(self):
        return apply_overtime_filters(pending_for_user(self.request.user), self.request.GET)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["types"] = OvertimeType.objects.filter(actif=True)
        context["services"] = services_for_user(self.request.user)
        return context


class ValidationHistoryView(_ValidationAccess, ListView):
    template_name = "workflow/history.html"
    context_object_name = "declarations"

    def get_paginate_by(self, queryset):
        return page_size()

    def get_queryset(self):
        queryset = overtime_for_user(self.request.user).filter(
            decisions__utilisateur=self.request.user
        ).distinct()
        return apply_overtime_filters(queryset, self.request.GET)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["types"] = OvertimeType.objects.filter(actif=True)
        context["services"] = services_for_user(self.request.user)
        return context


class ValidationDetailView(_ValidationAccess, DetailView):
    template_name = "workflow/detail.html"
    context_object_name = "declaration"

    def get_queryset(self):
        return overtime_for_user(self.request.user).prefetch_related(
            "pieces",
            "evenements__utilisateur",
            "decisions__utilisateur",
            "decisions__etape",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["approve_form"] = ApproveForm()
        context["reject_form"] = RejectForm()
        context["duree"] = format_minutes(self.object.duree_minutes)
        user = self.request.user
        from apps.workflow.services import peut_decider

        context["peut_approuver"] = peut_decider(user, self.object, "overtime.approve_overtime")
        context["peut_rejeter"] = peut_decider(user, self.object, "overtime.reject_overtime")
        return context


class ApproveView(_ValidationAccess, View):
    def post(self, request, pk):
        demande = get_object_or_404(pending_for_user(request.user), pk=pk)
        form = ApproveForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Le formulaire d'approbation est incomplet.")
            return redirect("workflow:detail", pk=pk)
        try:
            approuver(demande, request.user, request, form.cleaned_data.get("commentaire", ""))
        except WorkflowError as exc:
            messages.warning(request, exc.message)
            return redirect("workflow:detail", pk=pk)
        demande.refresh_from_db()
        if demande.statut == OvertimeRequest.Statut.APPROUVE:
            messages.success(request, "✓ Demande approuvée.")
        else:
            messages.success(request, "✓ Étape validée. La demande passe à l'étape suivante.")
        return redirect("workflow:detail", pk=pk)


class RejectView(_ValidationAccess, View):
    def post(self, request, pk):
        demande = get_object_or_404(pending_for_user(request.user), pk=pk)
        form = RejectForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Le motif du rejet est obligatoire.")
            return redirect("workflow:detail", pk=pk)
        try:
            rejeter(demande, request.user, request, form.cleaned_data["commentaire"])
        except WorkflowError as exc:
            messages.warning(request, exc.message)
            return redirect("workflow:detail", pk=pk)
        messages.success(request, "✓ Demande rejetée.")
        return redirect("workflow:detail", pk=pk)
