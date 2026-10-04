from django.db.models import Q
from django.views.generic import DetailView, ListView

from apps.accounts.mixins import AppPermissionMixin, page_size
from apps.audit.models import AuditLog


class AuditListView(AppPermissionMixin, ListView):
    permission_required = "audit.view_audit"
    template_name = "audit/list.html"
    context_object_name = "journaux"

    def get_paginate_by(self, queryset):
        return page_size()

    def get_queryset(self):
        queryset = AuditLog.objects.select_related("user")
        q = self.request.GET.get("q", "").strip()
        if q:
            queryset = queryset.filter(
                Q(action__icontains=q)
                | Q(model_name__icontains=q)
                | Q(object_id__icontains=q)
                | Q(user__username__icontains=q)
            )
        action = self.request.GET.get("action", "").strip()
        if action:
            queryset = queryset.filter(action=action)
        model_name = self.request.GET.get("modele", "").strip()
        if model_name:
            queryset = queryset.filter(model_name=model_name)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["actions"] = (
            AuditLog.objects.order_by("action").values_list("action", flat=True).distinct()
        )
        context["query"] = self.request.GET.get("q", "")
        return context


class AuditDetailView(AppPermissionMixin, DetailView):
    permission_required = "audit.view_audit"
    model = AuditLog
    template_name = "audit/detail.html"
    context_object_name = "journal"
