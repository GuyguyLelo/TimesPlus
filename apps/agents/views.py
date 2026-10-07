import mimetypes
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import ProtectedError, Q
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView

from apps.accounts.mixins import DENIED, AppPermissionMixin, page_size
from apps.agents.forms import AgentForm, AgentPhotoForm
from apps.agents.models import Agent, Fonction, Grade
from apps.audit.utils import journaliser, model_snapshot
from apps.overtime.selectors import agents_visible
from apps.reports.services.apercu import rendre_apercu
from apps.services.selectors import services_for_user


class AgentListView(AppPermissionMixin, ListView):
    permission_required = "agents.view_agent"
    template_name = "agents/list.html"
    context_object_name = "agents"

    def get_paginate_by(self, queryset):
        return page_size()

    def get_queryset(self):
        return _agents_liste(self.request).order_by("nom", "postnom", "prenom")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["services"] = services_for_user(self.request.user)
        context["query"] = self.request.GET.get("q", "")
        return context


def _agents_liste(request):
    queryset = agents_visible(request.user).select_related(
        "grade",
        "fonction",
        "service",
        "service__service_parent",
        "service__service_parent__service_parent",
        "service__service_parent__service_parent__service_parent",
        "service__service_parent__service_parent__service_parent__service_parent",
    )
    q = request.GET.get("q", "").strip()
    if q:
        queryset = queryset.filter(
            Q(matricule__icontains=q)
            | Q(nom__icontains=q)
            | Q(postnom__icontains=q)
            | Q(prenom__icontains=q)
        )
    service = request.GET.get("service")
    if str(service).isdigit():
        queryset = queryset.filter(service_id=int(service))
    actif = request.GET.get("actif")
    if actif in {"0", "1"}:
        queryset = queryset.filter(actif=(actif == "1"))
    return queryset


@login_required
def agent_list_pdf(request):
    if not request.user.has_perm("agents.view_agent") and not request.user.is_superuser:
        messages.warning(request, DENIED)
        return redirect("dashboard:home")
    from apps.agents.annuaire import build_annuaire_pdf
    from apps.settings_app.models import SiteSettings

    agents = list(_agents_liste(request))
    genere_le = timezone.localtime().strftime("%d/%m/%Y %H:%M")
    payload = build_annuaire_pdf(agents, site=SiteSettings.load(), genere_le=genere_le)
    params = {key: value for key, value in request.GET.items() if key != "page" and value}
    retour = reverse("agents:list")
    if params:
        retour = f"{retour}?{urlencode(params)}"
    return rendre_apercu(
        request,
        payload.getvalue(),
        "liste-du-personnel.pdf",
        "Liste déclarative par emboîtement",
        retour,
    )


class ReferentielView(AppPermissionMixin, TemplateView):
    permission_required = "agents.view_agent"
    template_name = "agents/referentiel.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["grades"] = Grade.objects.filter(actif=True)
        context["fonctions"] = Fonction.objects.filter(actif=True)
        return context


class AgentCreateView(AppPermissionMixin, CreateView):
    permission_required = "agents.add_agent"
    model = Agent
    form_class = AgentForm
    template_name = "agents/form.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        journaliser(
            request=self.request,
            action="CREATION",
            instance=self.object,
            new_values=model_snapshot(self.object),
        )
        messages.success(self.request, "✓ Agent enregistré avec succès.")
        return response

    def get_success_url(self):
        return reverse("agents:detail", args=[self.object.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Nouvel agent"
        return context


class AgentDetailView(AppPermissionMixin, DetailView):
    permission_required = "agents.view_agent"
    template_name = "agents/detail.html"
    context_object_name = "agent"

    def get_queryset(self):
        return agents_visible(self.request.user).select_related(
            "grade",
            "fonction",
            "service",
            "service__service_parent",
            "service__service_parent__service_parent",
            "service__service_parent__service_parent__service_parent",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        declarations = []
        mois_label = ""
        if self.request.user.has_perm("overtime.view_overtime"):
            from apps.overtime.forms import _NOMS_MOIS
            from apps.overtime.selectors import overtime_for_user

            today = timezone.localdate()
            mois_label = f"{_NOMS_MOIS[today.month - 1]} {today.year}"
            declarations = list(
                overtime_for_user(self.request.user)
                .filter(
                    agent=self.object,
                    date_travail__year=today.year,
                    date_travail__month=today.month,
                )
                .order_by("-date_travail", "-pk")
            )
        context["declarations"] = declarations
        context["declarations_mois"] = mois_label
        return context


class AgentUpdateView(AppPermissionMixin, UpdateView):
    permission_required = "agents.change_agent"
    form_class = AgentForm
    template_name = "agents/form.html"

    def get_queryset(self):
        return agents_visible(self.request.user)

    def form_valid(self, form):
        old = model_snapshot(Agent.objects.get(pk=self.object.pk))
        response = super().form_valid(form)
        journaliser(
            request=self.request,
            action="MODIFICATION",
            instance=self.object,
            old_values=old,
            new_values=model_snapshot(self.object),
        )
        messages.success(self.request, "✓ Agent modifié avec succès.")
        return response

    def get_success_url(self):
        return reverse("agents:detail", args=[self.object.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Modifier l'agent"
        return context


class AgentDeleteView(AppPermissionMixin, DeleteView):
    permission_required = "agents.delete_agent"
    template_name = "confirm.html"
    success_url = reverse_lazy("agents:list")

    def get_queryset(self):
        return agents_visible(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Supprimer l'agent"
        context["message"] = f"Confirmez la suppression de {self.object}."
        context["cancel_url"] = reverse("agents:detail", args=[self.object.pk])
        return context

    def form_valid(self, form):
        snapshot = model_snapshot(self.object)
        object_id = str(self.object.pk)
        try:
            response = super().form_valid(form)
        except ProtectedError:
            messages.error(
                self.request,
                "Cet agent ne peut pas être supprimé car des données y sont rattachées.",
            )
            return redirect("agents:detail", pk=object_id)
        journaliser(
            request=self.request,
            action="SUPPRESSION",
            model_name="Agent",
            object_id=object_id,
            old_values=snapshot,
        )
        messages.success(self.request, "✓ Agent supprimé.")
        return response


class AgentPhotoUpdateView(AppPermissionMixin, View):
    permission_required = "agents.change_agent"

    def post(self, request, pk):
        agent = get_object_or_404(agents_visible(request.user), pk=pk)
        if request.POST.get("supprimer") and not request.FILES.get("photo"):
            _replace_photo(agent, None)
            journaliser(
                request=request,
                action="MODIFICATION",
                instance=agent,
                new_values={"photo": ""},
            )
            messages.success(request, "✓ Photo retirée.")
            return redirect("agents:detail", pk=agent.pk)
        form = AgentPhotoForm(request.POST, request.FILES)
        if not form.is_valid():
            error = form.errors.get("photo")
            messages.error(request, error[0] if error else "La photo n'a pas pu être enregistrée.")
            return redirect("agents:detail", pk=agent.pk)
        _replace_photo(agent, form.cleaned_data["photo"])
        journaliser(
            request=request,
            action="MODIFICATION",
            instance=agent,
            new_values={"photo": agent.photo.name},
        )
        messages.success(request, "✓ Photo enregistrée.")
        return redirect("agents:detail", pk=agent.pk)


def _replace_photo(agent, uploaded):
    previous = agent.photo.name if agent.photo else ""
    if uploaded is None:
        if previous:
            agent.photo.delete(save=False)
        agent.photo = ""
        agent.save(update_fields=["photo", "updated_at"])
        return
    agent.photo = uploaded
    agent.save(update_fields=["photo", "updated_at"])
    current = agent.photo.name if agent.photo else ""
    if previous and previous != current:
        agent.photo.storage.delete(previous)


@login_required
def agent_photo(request, pk):
    if not request.user.has_perm("agents.view_agent"):
        messages.warning(request, DENIED)
        return redirect("dashboard:home")
    agent = agents_visible(request.user).filter(pk=pk).first()
    if agent is None or not agent.photo:
        raise Http404
    content_type = mimetypes.guess_type(agent.photo.name)[0] or "application/octet-stream"
    if content_type not in {"image/jpeg", "image/png", "image/webp"}:
        content_type = "application/octet-stream"
    response = FileResponse(agent.photo.open("rb"), content_type=content_type)
    response["Content-Disposition"] = "inline"
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, max-age=3600"
    return response
