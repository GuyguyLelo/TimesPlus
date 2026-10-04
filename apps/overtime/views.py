"""Vues des déclarations d'heures supplémentaires."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, FormView, ListView, RedirectView

from apps.accounts.access import get_profile
from apps.accounts.mixins import AppPermissionMixin, DENIED, page_size
from apps.audit.utils import journaliser, model_snapshot
from apps.overtime.formatting import format_minutes, format_montant
from apps.overtime.forms import ANNEE_MOIS, AttachmentForm, OvertimeRequestForm, _bornes_mois, _choix_mois
from apps.overtime.models import Attachment, OvertimeRequest, OvertimeType, WorkSchedule
from apps.overtime.selectors import (
    apply_overtime_filters,
    can_view_all,
    fiche_agent,
    my_overtime,
    overtime_for_user,
)
from apps.overtime.services.calculation import CalculationError, calculer_declaration
from apps.overtime.services.declaration import enregistrer_declaration
from apps.overtime.validators import validate_uploaded_file
from apps.workflow.services import WorkflowError, soumettre


def _scoped(user):
    if can_view_all(user) or user.is_superuser:
        return overtime_for_user(user)
    return my_overtime(user)


def _store_uploads(demande, prepared, type_document, user):
    allowed = {key for key, _label in Attachment.TypeDocument.choices}
    if type_document not in allowed:
        type_document = Attachment.TypeDocument.JUSTIFICATIF
    for uploaded, safe_name in prepared:
        attachment = Attachment(
            demande=demande,
            type_document=type_document,
            nom_original=safe_name,
            taille=uploaded.size,
            content_type=(getattr(uploaded, "content_type", "") or "")[:120],
            uploaded_by=user,
        )
        uploaded.seek(0)
        attachment.fichier.save(safe_name, uploaded, save=False)
        attachment.save()


def _libelle_periode(debut, fin):
    from datetime import datetime

    noms = (
        "",
        "janvier",
        "février",
        "mars",
        "avril",
        "mai",
        "juin",
        "juillet",
        "août",
        "septembre",
        "octobre",
        "novembre",
        "décembre",
    )
    try:
        start = datetime.strptime(debut, "%Y-%m-%d").date()
        end = datetime.strptime(fin, "%Y-%m-%d").date()
    except ValueError:
        return ""
    if start.year == end.year and start.month == end.month and start.day == 1:
        from calendar import monthrange

        if end.day == monthrange(end.year, end.month)[1]:
            return f"{noms[start.month].capitalize()} {start.year}"
    return f"Du {start:%d/%m/%Y} au {end:%d/%m/%Y}"


def _date_param(value):
    from datetime import datetime

    try:
        return datetime.strptime(value or "", "%Y-%m-%d").date()
    except ValueError:
        return None


def _mois_depuis_bornes(debut, fin):
    from datetime import datetime

    try:
        start = datetime.strptime(debut, "%Y-%m-%d").date()
        end = datetime.strptime(fin, "%Y-%m-%d").date()
    except ValueError:
        return ""
    if start.year == end.year and start.month == end.month and start.day == 1:
        from calendar import monthrange

        if end.day == monthrange(end.year, end.month)[1]:
            return start.strftime("%Y-%m")
    return ""


def _bornes_mois_courant():
    from calendar import monthrange

    today = timezone.localdate()
    last = monthrange(today.year, today.month)[1]
    return today.replace(day=1), today.replace(day=last)


class OvertimeListView(AppPermissionMixin, ListView):
    permission_required = "overtime.view_overtime"
    template_name = "overtime/list.html"
    context_object_name = "declarations"

    def get_paginate_by(self, queryset):
        return page_size()

    def _showing_all(self):
        if not can_view_all(self.request.user):
            return False
        return self.request.GET.get("portee") != "miennes"

    def _params(self):
        params = self.request.GET.copy()
        mois = (params.get("mois") or "").strip()
        try:
            debut_mois, fin_mois = _bornes_mois(mois)
        except ValueError:
            debut_mois, fin_mois = (None, None)
        if debut_mois is None and not (params.get("debut") or params.get("fin")):
            debut_mois, fin_mois = _bornes_mois_courant()
        if debut_mois is not None:
            debut = _date_param(params.get("debut")) or debut_mois
            fin = _date_param(params.get("fin")) or fin_mois
            if not (debut_mois <= debut <= fin_mois and debut_mois <= fin <= fin_mois and debut <= fin):
                debut, fin = debut_mois, fin_mois
            params["mois"] = debut_mois.strftime("%Y-%m")
            params["debut"] = debut.isoformat()
            params["fin"] = fin.isoformat()
        else:
            params["mois"] = _mois_depuis_bornes(params.get("debut") or "", params.get("fin") or "")
        return params

    def get_queryset(self):
        source = overtime_for_user(self.request.user) if self._showing_all() else my_overtime(self.request.user)
        return apply_overtime_filters(source, self._params())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        showing_all = self._showing_all()
        params = self._params()
        context["title"] = "Liste des Heures supplémentaires"
        context["filtre_debut"] = params.get("debut") or ""
        context["filtre_fin"] = params.get("fin") or ""
        context["filtre_mois"] = params.get("mois") or ""
        context["periode_label"] = _libelle_periode(context["filtre_debut"], context["filtre_fin"])
        context["mois_choices"] = _choix_mois({ANNEE_MOIS})
        context["types"] = OvertimeType.objects.filter(actif=True)
        context["statuts"] = OvertimeRequest.Statut.choices
        context["show_agent"] = showing_all
        context["showing_all"] = showing_all
        context["can_switch"] = can_view_all(self.request.user)
        context["mon_agent_id"] = get_profile(self.request.user).agent_id
        return context


class AllOvertimeRedirectView(RedirectView):
    """Ancienne adresse « Toutes les déclarations », renvoyée vers la page unique."""

    pattern_name = "overtime:mine"
    query_string = True


class OvertimeFormView(AppPermissionMixin, FormView):
    permission_required = "overtime.add_overtime"
    template_name = "overtime/form.html"
    form_class = OvertimeRequestForm

    def dispatch(self, request, *args, **kwargs):
        self.object = None
        if "pk" in kwargs:
            self.object = get_object_or_404(_scoped(request.user), pk=kwargs["pk"])
            if not self.object.editable:
                messages.warning(request, "Une déclaration annulée ne peut plus être modifiée.")
                return redirect("overtime:detail", pk=self.object.pk)
            if not request.user.has_perm("overtime.change_overtime") and not request.user.is_superuser:
                messages.warning(request, DENIED)
                return redirect("dashboard:home")
        return super().dispatch(request, *args, **kwargs)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if self.request.method == "GET" and not self.object:
            raw = self.request.GET.get("date") or ""
            if raw:
                from datetime import datetime

                try:
                    jour = datetime.strptime(raw, "%Y-%m-%d").date()
                except ValueError:
                    jour = None
                if jour is not None:
                    form.initial["date_travail"] = jour
                    form.initial["mois"] = jour.strftime("%Y-%m")
                    start = jour.replace(day=1)
                    from calendar import monthrange

                    end = jour.replace(day=monthrange(jour.year, jour.month)[1])
                    form.fields["date_travail"].widget.attrs["min"] = start.isoformat()
                    form.fields["date_travail"].widget.attrs["max"] = end.isoformat()
        return form

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        if self.object is not None:
            kwargs["instance"] = self.object
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Modifier la déclaration" if self.object else "Saisie Heure Supplémentaire"
        context["declaration"] = self.object
        context["calculation"] = getattr(context.get("form"), "calculation", None)
        jour = None
        if self.request.method == "POST":
            raw = self.request.POST.get("date_travail")
        elif self.object:
            raw = self.object.date_travail.isoformat()
        else:
            raw = self.request.GET.get("date") or timezone.localdate().isoformat()
        schedule = None
        if raw:
            from datetime import datetime

            try:
                jour = datetime.strptime(raw, "%Y-%m-%d").date()
            except ValueError:
                jour = None
        if jour is not None:
            schedule = (
                WorkSchedule.objects.filter(actif=True, jour_semaine=jour.weekday())
                .order_by("service_id")
                .first()
            )
        context["horaire"] = schedule
        return context

    def form_valid(self, form):
        old = model_snapshot(self.object) if self.object else None
        try:
            with transaction.atomic():
                demande, _result = enregistrer_declaration(
                    agent=form.cleaned_data["agent"],
                    date_travail=form.cleaned_data["date_travail"],
                    heure_debut=form.cleaned_data["heure_debut"],
                    heure_fin=form.cleaned_data["heure_fin"],
                    motif=form.cleaned_data["motif"],
                    observation=form.cleaned_data.get("observation", ""),
                    user=self.request.user,
                    existing=self.object,
                )
        except CalculationError as exc:
            form.add_error(None, exc.message)
            return self.form_invalid(form)
        self.object = demande
        journaliser(
            request=self.request,
            action="MODIFICATION" if old else "CREATION",
            instance=demande,
            old_values=old,
            new_values=model_snapshot(demande),
        )
        messages.success(self.request, "✓ Saisie enregistrée sur la liste.")
        debut = demande.date_travail.replace(day=1)
        from calendar import monthrange

        fin = demande.date_travail.replace(day=monthrange(demande.date_travail.year, demande.date_travail.month)[1])
        return redirect(f"{reverse('overtime:mine')}?debut={debut.isoformat()}&fin={fin.isoformat()}")


class OvertimeDetailView(AppPermissionMixin, DetailView):
    permission_required = "overtime.view_overtime"
    template_name = "overtime/detail.html"
    context_object_name = "declaration"

    def get_queryset(self):
        return _scoped(self.request.user).prefetch_related(
            "pieces",
            "evenements__utilisateur",
            "decisions__utilisateur",
            "decisions__etape",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["attachment_form"] = AttachmentForm()
        return context


class OvertimeDeleteView(AppPermissionMixin, View):
    permission_required = "overtime.delete_overtime"

    def get_object(self):
        return get_object_or_404(_scoped(self.request.user), pk=self.kwargs["pk"])

    def get(self, request, pk):
        demande = self.get_object()
        if not demande.supprimable:
            messages.warning(request, "Une déclaration annulée ne peut plus être supprimée.")
            return redirect("overtime:detail", pk=demande.pk)
        from django.shortcuts import render

        return render(
            request,
            "confirm.html",
            {
                "title": "Supprimer la déclaration",
                "message": "Cette déclaration sera définitivement supprimée.",
                "cancel_url": reverse("overtime:detail", args=[demande.pk]),
            },
        )

    def post(self, request, pk):
        demande = self.get_object()
        if not demande.supprimable:
            messages.warning(request, "Une déclaration annulée ne peut plus être supprimée.")
            return redirect("overtime:detail", pk=demande.pk)
        snapshot = model_snapshot(demande)
        object_id = str(demande.pk)
        demande.delete()
        journaliser(
            request=request,
            action="SUPPRESSION",
            model_name="OvertimeRequest",
            object_id=object_id,
            old_values=snapshot,
        )
        messages.success(request, "✓ Déclaration supprimée.")
        return redirect("overtime:mine")


class OvertimeSubmitView(AppPermissionMixin, View):
    permission_required = "overtime.submit_overtime"

    def get_object(self):
        return get_object_or_404(my_overtime(self.request.user), pk=self.kwargs["pk"])

    def get(self, request, pk):
        demande = self.get_object()
        if not demande.soumissible:
            messages.warning(request, "Cette demande ne peut plus être soumise.")
            return redirect("overtime:detail", pk=demande.pk)
        from django.shortcuts import render

        return render(
            request,
            "confirm.html",
            {
                "title": "Soumettre la déclaration",
                "message": "La demande sera transmise au circuit de validation. Vérifiez la durée calculée par le serveur.",
                "cancel_url": reverse("overtime:detail", args=[demande.pk]),
                "confirm_label": "Soumettre",
                "confirm_class": "btn-primary",
            },
        )

    def post(self, request, pk):
        demande = self.get_object()
        try:
            soumettre(demande, request.user, request)
        except WorkflowError as exc:
            messages.error(request, exc.message)
            return redirect("overtime:detail", pk=demande.pk)
        messages.success(request, "✓ Demande soumise pour validation.")
        return redirect("overtime:detail", pk=demande.pk)


class AddAttachmentView(AppPermissionMixin, View):
    permission_required = "overtime.add_overtime"

    def post(self, request, pk):
        demande = get_object_or_404(_scoped(request.user), pk=pk)
        if not demande.editable:
            messages.warning(request, "Les pièces ne peuvent plus être ajoutées sur cette demande.")
            return redirect("overtime:detail", pk=pk)
        form = AttachmentForm(request.POST, request.FILES)
        if not form.is_valid():
            messages.error(request, "Le fichier n'a pas pu être ajouté.")
            return redirect("overtime:detail", pk=pk)
        try:
            prepared = [(form.cleaned_data["fichier"], validate_uploaded_file(form.cleaned_data["fichier"]))]
        except Exception as exc:
            message = exc.messages[0] if getattr(exc, "messages", None) else str(exc)
            messages.error(request, message)
            return redirect("overtime:detail", pk=pk)
        _store_uploads(demande, prepared, form.cleaned_data["type_document"], request.user)
        journaliser(
            request=request,
            action="MODIFICATION",
            instance=demande,
            new_values={"piece": prepared[0][1]},
        )
        messages.success(request, "✓ Pièce jointe enregistrée.")
        return redirect("overtime:detail", pk=pk)


@login_required
def download_attachment(request, pk):
    attachment = get_object_or_404(
        Attachment.objects.select_related("demande"),
        pk=pk,
    )
    if not _scoped(request.user).filter(pk=attachment.demande_id).exists():
        messages.warning(request, DENIED)
        return redirect("dashboard:home")
    handle = attachment.fichier.open("rb")
    response = FileResponse(handle, as_attachment=True, filename=attachment.nom_original)
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
@require_POST
def delete_attachment(request, pk):
    attachment = get_object_or_404(Attachment.objects.select_related("demande"), pk=pk)
    demande = get_object_or_404(_scoped(request.user), pk=attachment.demande_id)
    if not demande.editable or not request.user.has_perm("overtime.change_overtime"):
        messages.warning(request, DENIED)
        return redirect("overtime:detail", pk=demande.pk)
    name = attachment.nom_original
    if attachment.fichier:
        attachment.fichier.delete(save=False)
    attachment.delete()
    journaliser(
        request=request,
        action="SUPPRESSION",
        model_name="Attachment",
        object_id=str(pk),
        old_values={"nom": name, "demande": demande.pk},
    )
    messages.success(request, "✓ Pièce jointe supprimée.")
    return redirect("overtime:detail", pk=demande.pk)


@login_required
@require_POST
def signer_liste(request, pk):
    from apps.overtime.models import ListeJournaliere, SignatureListe

    liste = get_object_or_404(ListeJournaliere, pk=pk)
    qualite = request.POST.get("qualite") or ""
    if qualite not in {SignatureListe.Qualite.AGENT, SignatureListe.Qualite.CADRE}:
        messages.warning(request, "Qualité de signature inconnue.")
    else:
        from apps.overtime.listes import signer

        ok, message = signer(request.user, liste, qualite)
        if ok:
            messages.success(request, "✓ Signature enregistrée.")
        else:
            messages.warning(request, message)
    suivant = request.POST.get("next") or ""
    if suivant.startswith("/") and not suivant.startswith("//"):
        return redirect(suivant)
    return redirect(f"{reverse('overtime:create')}?date={liste.date.isoformat()}")


@login_required
def search_agents(request):
    if not (
        request.user.has_perm("overtime.add_overtime")
        or request.user.has_perm("overtime.change_overtime")
        or request.user.is_superuser
    ):
        return JsonResponse({"results": []}, status=403)
    if not can_view_all(request.user):
        return JsonResponse({"results": []})
    from django.db.models import Q

    from apps.agents.models import Agent

    query = (request.GET.get("q") or "").strip()
    terms = [term for term in query.split() if term]
    if not terms:
        return JsonResponse({"results": []})
    queryset = Agent.objects.filter(actif=True).select_related("service", "grade", "fonction")
    for term in terms:
        queryset = queryset.filter(
            Q(matricule__icontains=term)
            | Q(nom__icontains=term)
            | Q(postnom__icontains=term)
            | Q(prenom__icontains=term)
        )
    results = [fiche_agent(agent) for agent in queryset.order_by("nom", "postnom", "prenom")[:12]]
    return JsonResponse({"results": results})


@login_required
def preview_calculation(request):
    if not (
        request.user.has_perm("overtime.add_overtime")
        or request.user.has_perm("overtime.change_overtime")
        or request.user.is_superuser
    ):
        return JsonResponse({"ok": False, "message": DENIED}, status=403)
    from datetime import datetime

    from apps.agents.models import Agent

    raw_date = request.GET.get("date") or ""
    raw_start = request.GET.get("heure_debut") or ""
    raw_end = request.GET.get("heure_fin") or ""
    agent_id = request.GET.get("agent") or ""
    exclude = request.GET.get("exclude") or ""
    try:
        jour = datetime.strptime(raw_date, "%Y-%m-%d").date()
        debut = _parse_time(raw_start)
        fin = _parse_time(raw_end)
    except ValueError:
        return JsonResponse({"ok": False, "message": "Indiquez la date et les heures."})
    if not str(agent_id).isdigit():
        return JsonResponse({"ok": False, "message": "Sélectionnez un agent."})
    agent = Agent.objects.filter(pk=int(agent_id)).first()
    if agent is None or not _agent_allowed(request.user, agent):
        return JsonResponse({"ok": False, "message": DENIED}, status=403)
    exclude_id = int(exclude) if str(exclude).isdigit() else None
    try:
        result = calculer_declaration(agent, jour, debut, fin, exclude_id=exclude_id)
    except CalculationError as exc:
        return JsonResponse({"ok": False, "message": exc.message})
    return JsonResponse(
        {
            "ok": True,
            "duree": format_minutes(result.duree_minutes),
            "minutes": result.duree_minutes,
            "type": result.type_code,
            "libelle": result.type_libelle,
            "regle": result.regle_nom,
            "coefficient": str(result.coefficient),
            "montant": format_montant(result.montant_estime),
            "ventilation": result.ventilation,
        }
    )


def _parse_time(value):
    from datetime import datetime

    for pattern in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(value, pattern).time()
        except ValueError:
            continue
    raise ValueError(value)


def _agent_allowed(user, agent):
    if can_view_all(user) or user.is_superuser:
        return True
    from apps.accounts.access import get_profile

    profile = get_profile(user)
    return profile.agent_id == agent.id
