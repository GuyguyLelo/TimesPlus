from django.contrib import messages
from django.db.models import Count, F, ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.accounts.mixins import AppPermissionMixin, PageSizeMixin
from apps.audit.utils import journaliser, model_snapshot
from apps.services.forms import ServiceForm
from apps.services.models import Service
from apps.services.selectors import appliquer_activite, descendant_ids, services_for_user


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
        previous = Service.objects.get(pk=self.object.pk)
        old = model_snapshot(previous)
        response = super().form_valid(form)
        if previous.niveau == Service.Niveau.DIRECTION and previous.actif != self.object.actif:
            appliquer_activite(self.object, self.object.actif)
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


class ServiceActiviteView(AppPermissionMixin, View):
    """Rend une direction inactive ou active, avec les unités qui en dépendent."""

    permission_required = "services.change_service"

    def _service(self):
        return get_object_or_404(services_for_user(self.request.user), pk=self.kwargs["pk"])

    def _actif(self, service):
        choix = self.request.GET.get("actif")
        if choix == "1":
            return True
        if choix == "0":
            return False
        return not service.actif

    def get(self, request, pk):
        service = self._service()
        if service.niveau != Service.Niveau.DIRECTION:
            messages.warning(request, "Seule une direction peut entraîner ses divisions et ses bureaux.")
            return redirect("services:list")
        actif = self._actif(service)
        if actif:
            title = "Rendre la direction active"
            message = (
                f"Confirmez la réactivation de {service.nom}. "
                "Les divisions, secrétariats et bureaux qui en dépendent seront aussi actifs."
            )
            confirm_label = "Rendre actif"
            confirm_class = "btn-primary"
        else:
            title = "Rendre la direction inactive"
            message = (
                f"Confirmez la mise en inactivité de {service.nom}. "
                "Les divisions, secrétariats et bureaux qui en dépendent seront aussi inactifs."
            )
            confirm_label = "Rendre inactif"
            confirm_class = "btn-danger"
        unites = list(
            Service.objects.filter(pk__in=descendant_ids(service.pk))
            .exclude(pk=service.pk)
            .annotate(nb_agents=Count("agents"))
            .order_by("code")
        )
        parents = {unite.pk: unite.service_parent_id for unite in unites}

        def profondeur(pk):
            niveau = 0
            courant = parents.get(pk)
            vus = set()
            while courant and courant != service.pk and courant not in vus:
                vus.add(courant)
                niveau += 1
                courant = parents.get(courant)
            return niveau

        for unite in unites:
            unite.profondeur = profondeur(unite.pk)
        return render(
            request,
            "services/activite.html",
            {
                "title": title,
                "message": message,
                "confirm_label": confirm_label,
                "confirm_class": confirm_class,
                "cancel_url": reverse("services:list"),
                "service": service,
                "unites": unites,
                "agents": service.agents.count() + sum(unite.nb_agents for unite in unites),
                "actif": actif,
            },
        )

    def post(self, request, pk):
        service = self._service()
        if service.niveau != Service.Niveau.DIRECTION:
            messages.warning(request, "Seule une direction peut entraîner ses divisions et ses bureaux.")
            return redirect("services:list")
        actif = self._actif(service)
        ancien = service.actif
        nombre = appliquer_activite(service, actif)
        rattaches = max(nombre - 1, 0)
        journaliser(
            request=request,
            action="MODIFICATION",
            instance=service,
            old_values={"actif": ancien},
            new_values={"actif": actif, "unites": nombre},
        )
        if rattaches == 0:
            suite = "est de nouveau active." if actif else "est inactive."
            messages.success(request, f"✓ {service.nom} {suite}")
        else:
            mot = "unité rattachée" if rattaches == 1 else "unités rattachées"
            etat = "de nouveau actives" if actif else "inactives"
            messages.success(request, f"✓ {service.nom} et ses {rattaches} {mot} sont {etat}.")
        return redirect("services:list")


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
