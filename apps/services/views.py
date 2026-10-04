from django.contrib import messages
from django.db.models import F, ProtectedError, Q
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.accounts.mixins import AppPermissionMixin, PageSizeMixin
from apps.audit.utils import journaliser, model_snapshot
from apps.services.forms import ServiceForm
from apps.services.models import Service
from apps.services.selectors import services_for_user


class ServiceListView(PageSizeMixin, AppPermissionMixin, ListView):
    permission_required = "services.view_service"
    template_name = "services/list.html"
    context_object_name = "services"

    def get_queryset(self):
        queryset = services_for_user(self.request.user)
        q = self.request.GET.get("q", "").strip()
        if q:
            queryset = queryset.filter(Q(code__icontains=q) | Q(nom__icontains=q))
        return queryset.prefetch_related("agents").order_by(
            F("service_parent__code").asc(nulls_first=True), "code"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.request.GET.get("q", "")
        return context


class ServiceCreateView(AppPermissionMixin, CreateView):
    permission_required = "services.add_service"
    model = Service
    form_class = ServiceForm
    template_name = "services/form.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        journaliser(request=self.request, action="CREATION", instance=self.object, new_values=model_snapshot(self.object))
        messages.success(self.request, "✓ Service enregistré avec succès.")
        return response

    def get_success_url(self):
        return reverse("services:detail", args=[self.object.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Nouveau service"
        return context


class ServiceDetailView(AppPermissionMixin, DetailView):
    permission_required = "services.view_service"
    template_name = "services/detail.html"
    context_object_name = "service"

    def get_queryset(self):
        return services_for_user(self.request.user).prefetch_related("sous_services", "agents")


class ServiceUpdateView(AppPermissionMixin, UpdateView):
    permission_required = "services.change_service"
    form_class = ServiceForm
    template_name = "services/form.html"

    def get_queryset(self):
        return services_for_user(self.request.user)

    def form_valid(self, form):
        old = model_snapshot(Service.objects.get(pk=self.object.pk))
        response = super().form_valid(form)
        journaliser(
            request=self.request,
            action="MODIFICATION",
            instance=self.object,
            old_values=old,
            new_values=model_snapshot(self.object),
        )
        messages.success(self.request, "✓ Service modifié avec succès.")
        return response

    def get_success_url(self):
        return reverse("services:detail", args=[self.object.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Modifier le service"
        return context


class ServiceDeleteView(AppPermissionMixin, DeleteView):
    permission_required = "services.delete_service"
    template_name = "confirm.html"
    success_url = reverse_lazy("services:list")

    def get_queryset(self):
        return services_for_user(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Supprimer le service"
        context["message"] = f"Confirmez la suppression de {self.object}."
        context["cancel_url"] = reverse("services:detail", args=[self.object.pk])
        return context

    def form_valid(self, form):
        snapshot = model_snapshot(self.object)
        object_id = str(self.object.pk)
        try:
            response = super().form_valid(form)
        except ProtectedError:
            messages.error(self.request, "Ce service est encore utilisé et ne peut pas être supprimé.")
            return redirect("services:detail", pk=object_id)
        journaliser(
            request=self.request,
            action="SUPPRESSION",
            model_name="Service",
            object_id=object_id,
            old_values=snapshot,
        )
        messages.success(self.request, "✓ Service supprimé.")
        return response
