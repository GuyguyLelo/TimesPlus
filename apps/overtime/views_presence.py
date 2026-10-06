"""Liste de présence signée, jointe à une date."""

from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import FormView, ListView

from apps.accounts.mixins import AppPermissionMixin, PageSizeMixin
from apps.audit.utils import journaliser
from apps.overtime.forms import ListePresenceForm
from apps.overtime.models import ListePresence


class PresenceListView(PageSizeMixin, AppPermissionMixin, ListView):
    permission_required = "overtime.view_overtime"
    model = ListePresence
    template_name = "overtime/presence_list.html"
    context_object_name = "listes"

    def get_queryset(self):
        return ListePresence.objects.select_related("depose_par")


class PresenceCreateView(AppPermissionMixin, FormView):
    permission_required = "overtime.add_overtime"
    form_class = ListePresenceForm
    template_name = "overtime/presence_form.html"
    success_url = reverse_lazy("overtime:presences")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Joindre une liste"
        context["intro"] = "La liste signée est rattachée à la date choisie. Une date déjà pourvue est refusée."
        return context

    def form_valid(self, form):
        jour = form.cleaned_data["date"]
        if ListePresence.objects.filter(date=jour).exists():
            form.add_error("date", "Cette date a déjà une liste de présence. Une date n'en reçoit qu'une.")
            return self.form_invalid(form)
        uploaded = form.cleaned_data["fichier"]
        liste = ListePresence(
            date=jour,
            effectifs=form.cleaned_data["effectifs"],
            nom_original=form.nom_sur,
            taille=uploaded.size,
            content_type=(getattr(uploaded, "content_type", "") or "")[:120],
            depose_par=self.request.user,
        )
        uploaded.seek(0)
        try:
            with transaction.atomic():
                liste.fichier.save(form.nom_sur, uploaded, save=False)
                liste.save()
        except IntegrityError:
            form.add_error("date", "Cette date a déjà une liste de présence. Une date n'en reçoit qu'une.")
            return self.form_invalid(form)
        journaliser(
            request=self.request,
            action="CREATION",
            instance=liste,
            new_values={"date": liste.date.isoformat(), "fichier": liste.nom_original},
        )
        messages.success(self.request, "✓ Liste de présence enregistrée.")
        return redirect(self.success_url)


class PresenceUpdateView(AppPermissionMixin, FormView):
    permission_required = "overtime.add_overtime"
    form_class = ListePresenceForm
    template_name = "overtime/presence_form.html"
    success_url = reverse_lazy("overtime:presences")

    def dispatch(self, request, *args, **kwargs):
        self.object = get_object_or_404(ListePresence, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["liste"] = self.object
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Modifier la liste"
        context["intro"] = "La date, l'effectif et le document peuvent être remplacés."
        return context

    def form_valid(self, form):
        liste = self.object
        ancien = {
            "date": liste.date.isoformat(),
            "effectifs": liste.effectifs,
            "fichier": liste.nom_original,
        }
        liste.date = form.cleaned_data["date"]
        liste.effectifs = form.cleaned_data["effectifs"]
        uploaded = form.cleaned_data.get("fichier")
        if uploaded:
            if liste.fichier:
                liste.fichier.delete(save=False)
            uploaded.seek(0)
            liste.nom_original = form.nom_sur
            liste.taille = uploaded.size
            liste.content_type = (getattr(uploaded, "content_type", "") or "")[:120]
            liste.depose_par = self.request.user
            liste.fichier.save(form.nom_sur, uploaded, save=False)
        try:
            with transaction.atomic():
                liste.save()
        except IntegrityError:
            form.add_error("date", "Cette date a déjà une liste de présence. Une date n'en reçoit qu'une.")
            return self.form_invalid(form)
        journaliser(
            request=self.request,
            action="MODIFICATION",
            instance=liste,
            old_values=ancien,
            new_values={
                "date": liste.date.isoformat(),
                "effectifs": liste.effectifs,
                "fichier": liste.nom_original,
            },
        )
        messages.success(self.request, "✓ Liste de présence modifiée.")
        return redirect(self.success_url)


@login_required
def presence_effectifs(request):
    if not (
        request.user.has_perm("overtime.view_overtime")
        or request.user.is_superuser
    ):
        return JsonResponse({"effectifs": None}, status=403)
    raw = request.GET.get("date") or ""
    try:
        jour = datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"effectifs": None})
    liste = ListePresence.objects.filter(date=jour).only("effectifs").first()
    return JsonResponse({"effectifs": liste.effectifs if liste is not None else None})


@login_required
def download_presence(request, pk):
    if not request.user.has_perm("overtime.view_overtime"):
        messages.warning(request, "⚠ Vous n'êtes pas autorisé à effectuer cette opération.")
        return redirect("dashboard:home")
    liste = get_object_or_404(ListePresence, pk=pk)
    handle = liste.fichier.open("rb")
    response = FileResponse(handle, as_attachment=True, filename=liste.nom_original)
    response["X-Content-Type-Options"] = "nosniff"
    return response
