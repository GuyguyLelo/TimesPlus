from datetime import date, timedelta

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from apps.accounts.mixins import AppPermissionMixin, page_size
from apps.audit.utils import journaliser
from apps.overtime.formatting import format_minutes
from apps.overtime.forms import ANNEE_MOIS, _bornes_mois, _NOMS_MOIS
from apps.reports.forms import MonthlyReportFilterForm, ReportFilterForm
from apps.reports.models import GeneratedReport, ReportSequence
from apps.agents.models import Agent
from apps.reports.services import (
    agent_unique,
    by_agent,
    by_service,
    by_type,
    historique_par_mois,
    parse_report_params,
    report_queryset,
    report_totals,
)
from apps.reports.services.excel import build_workbook
from apps.reports.services.pdf import build_pdf
from apps.settings_app.models import SiteSettings


def _month_bounds(day):
    start = day.replace(day=1)
    if day.month == 12:
        next_month = day.replace(year=day.year + 1, month=1, day=1)
    else:
        next_month = day.replace(month=day.month + 1, day=1)
    return start, next_month - timedelta(days=1)


def _params_from_form(form, fallback_month=False, mois=""):
    if form.is_valid():
        data = form.cleaned_data
        raw = {
            "debut": data.get("debut"),
            "fin": data.get("fin"),
            "service": data["service"].pk if data.get("service") else "",
            "agent": data["agent"].pk if data.get("agent") else "",
            "statut": data.get("statut") or "",
            "type_heure": data["type_heure"].pk if data.get("type_heure") else "",
        }
        mois = data.get("mois") or mois
    else:
        raw = {}
    params = parse_report_params(raw)
    if mois:
        try:
            params["debut"], params["fin"] = _bornes_mois(mois)
        except ValueError:
            pass
    if fallback_month and not params["debut"] and not params["fin"]:
        params["debut"], params["fin"] = _month_bounds(timezone.localdate())
    return params


def _periode_label(params):
    debut = params.get("debut")
    fin = params.get("fin")
    if (
        debut
        and fin
        and debut.year == fin.year
        and debut.month == 1
        and debut.day == 1
        and fin.month == 12
        and fin.day == 31
    ):
        return f"Année {debut.year}"
    if debut and fin and debut.day == 1 and debut.year == fin.year and debut.month == fin.month:
        from calendar import monthrange

        if fin.day == monthrange(fin.year, fin.month)[1]:
            return f"{_NOMS_MOIS[debut.month - 1]} {debut.year}"
    if debut and fin:
        return f"{debut:%d/%m/%Y} — {fin:%d/%m/%Y}"
    if debut:
        return f"À partir du {debut:%d/%m/%Y}"
    if fin:
        return f"Jusqu'au {fin:%d/%m/%Y}"
    return "Toutes périodes"


def allocate_numero():
    year = timezone.localdate().year
    with transaction.atomic():
        try:
            sequence, _created = ReportSequence.objects.select_for_update().get_or_create(
                annee=year,
                defaults={"dernier": 0},
            )
        except IntegrityError:
            sequence = ReportSequence.objects.select_for_update().get(annee=year)
        sequence.dernier += 1
        sequence.save(update_fields=["dernier"])
    return f"HS-{year}-{sequence.dernier:05d}"


def _record(request, numero, kind, file_format, params):
    report = GeneratedReport.objects.create(
        numero=numero,
        type_rapport=kind,
        format=file_format,
        periode_debut=params.get("debut"),
        periode_fin=params.get("fin"),
        filtres={key: str(value) for key, value in params.items() if value},
        genere_par=request.user,
    )
    journaliser(
        request=request,
        action="GENERATION_RAPPORT",
        instance=report,
        new_values={"numero": numero, "type": kind, "format": file_format},
    )
    return report


class ReportPage(AppPermissionMixin, TemplateView):
    permission_required = "reports.view_reports"
    template_name = "reports/preview.html"
    kind = "ADMINISTRATIF"
    fallback_month = False
    form_class = ReportFilterForm
    title = "Rapport"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        data = self.request.GET.copy()
        if self.fallback_month and not data.get("mois") and not data.get("debut") and not data.get("fin"):
            data["mois"] = timezone.localdate().strftime("%Y-%m")
        form = self.form_class(data)
        params = _params_from_form(form, fallback_month=self.fallback_month, mois=data.get("mois") or "")
        queryset = report_queryset(self.request.user, params)
        totals = report_totals(queryset)
        service_label = ""
        if params.get("service"):
            from apps.services.models import Service

            service = Service.objects.filter(pk=params["service"]).first()
            service_label = str(service) if service else ""
        page = paginate(self.request, queryset)
        agent_fiche = None
        if self.kind == "MENSUEL":
            if params.get("agent"):
                agent_fiche = (
                    Agent.objects.select_related("grade", "fonction", "service")
                    .filter(pk=params["agent"])
                    .first()
                )
            else:
                agent_fiche = agent_unique(queryset)
        context.update(
            {
                "form": form,
                "title": self.title,
                "kind": self.kind,
                "params": params,
                "periode": _periode_label(params),
                "service_label": service_label,
                "totaux": totals,
                "duree": format_minutes(totals["minutes"]),
                "par_service": by_service(queryset),
                "par_type": by_type(queryset),
                "par_agent": by_agent(queryset),
                "declarations": page.object_list,
                "agent_fiche": agent_fiche,
                "lignes_fiche": list(queryset) if agent_fiche else [],
                "page_obj": page,
                "querystring": self.request.GET.urlencode(),
            }
        )
        return context


class ReportHubView(ReportPage):
    template_name = "reports/hub.html"
    title = "Rapports"
    kind = "ADMINISTRATIF"


class MonthlyReportView(ReportPage):
    title = "Rapport mensuel"
    kind = "MENSUEL"
    fallback_month = True
    form_class = MonthlyReportFilterForm


class HistoricalReportView(AppPermissionMixin, TemplateView):
    permission_required = "reports.view_reports"
    template_name = "reports/historique.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        annee = ANNEE_MOIS
        params = {
            "debut": date(annee, 1, 1),
            "fin": date(annee, 12, 31),
            "statut": "",
        }
        queryset = report_queryset(self.request.user, params)
        totals = report_totals(queryset)
        context.update(
            {
                "title": "Rapport historique",
                "annee": annee,
                "periode": f"Année {annee}",
                "totaux": totals,
                "duree": format_minutes(totals["minutes"]),
                "mois_rows": historique_par_mois(queryset, annee),
                "par_agent": by_agent(queryset),
                "querystring": f"debut={annee}-01-01&fin={annee}-12-31",
            }
        )
        return context


class ServiceReportView(ReportPage):
    title = "Rapport par service"
    kind = "SERVICE"
    fallback_month = True
    form_class = MonthlyReportFilterForm


class AgentReportView(ReportPage):
    title = "Rapport par agent"
    kind = "INDIVIDUEL"


class ExportExcelView(AppPermissionMixin, View):
    permission_required = "reports.export_reports"

    def get(self, request):
        form = ReportFilterForm(request.GET or None)
        params = _params_from_form(form, fallback_month=True, mois=request.GET.get("mois") or "")
        queryset = report_queryset(request.user, params)
        site = SiteSettings.load()
        numero = allocate_numero()
        utilisateur = request.user.get_full_name() or request.user.get_username()
        workbook = build_workbook(
            queryset,
            site=site,
            numero=numero,
            periode=_periode_label(params),
            utilisateur=utilisateur,
        )
        _record(request, numero, GeneratedReport.TypeRapport.EXCEL, GeneratedReport.Format.XLSX, params)
        response = HttpResponse(
            workbook.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{numero}.xlsx"'
        return response


class ExportPdfView(AppPermissionMixin, View):
    permission_required = "reports.export_reports"

    def get(self, request):
        kind = request.GET.get("kind") or "ADMINISTRATIF"
        allowed = {"INDIVIDUEL", "SERVICE", "MENSUEL", "ADMINISTRATIF", "HISTORIQUE"}
        if kind not in allowed:
            kind = "ADMINISTRATIF"
        form = ReportFilterForm(request.GET or None)
        params = _params_from_form(
            form,
            fallback_month=(kind in {"MENSUEL", "SERVICE"}),
            mois="" if kind == "HISTORIQUE" else (request.GET.get("mois") or ""),
        )
        if kind == "HISTORIQUE":
            params["debut"] = date(ANNEE_MOIS, 1, 1)
            params["fin"] = date(ANNEE_MOIS, 12, 31)
        if kind == "INDIVIDUEL" and not params.get("agent"):
            messages.warning(request, "Choisissez un agent pour le rapport individuel.")
            return render(request, "reports/preview.html", _empty_context(request, form, kind))
        if kind == "SERVICE" and not params.get("service"):
            messages.warning(request, "Choisissez un service pour le rapport de service.")
            return render(request, "reports/preview.html", _empty_context(request, form, kind))
        queryset = report_queryset(request.user, params)
        site = SiteSettings.load()
        numero = allocate_numero()
        utilisateur = request.user.get_full_name() or request.user.get_username()
        service_label = ""
        if params.get("service"):
            from apps.services.models import Service

            service = Service.objects.filter(pk=params["service"]).first()
            service_label = str(service) if service else ""
        agent = None
        if params.get("agent"):
            agent = (
                Agent.objects.select_related("grade", "fonction", "service")
                .filter(pk=params["agent"])
                .first()
            )
        elif kind == "MENSUEL":
            agent = agent_unique(queryset)
        if kind == "MENSUEL" and agent is not None:
            kind = "INDIVIDUEL"
        genere_le = timezone.localtime().strftime("%d/%m/%Y %H:%M")
        payload = build_pdf(
            kind,
            queryset,
            site=site,
            numero=numero,
            periode=_periode_label(params),
            utilisateur=utilisateur,
            genere_le=genere_le,
            service_label=service_label,
            agent=agent,
        )
        _record(request, numero, kind, GeneratedReport.Format.PDF, params)
        response = HttpResponse(payload.getvalue(), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{numero}.pdf"'
        return response


def paginate(request, queryset):
    paginator = Paginator(queryset, page_size())
    return paginator.get_page(request.GET.get("page") or 1)


def _empty_context(request, form, kind):
    return {
        "form": form,
        "title": "Rapport",
        "kind": kind,
        "totaux": {"minutes": 0, "montant": 0, "nombre": 0},
        "duree": "00h00",
        "par_service": [],
        "par_type": [],
        "par_agent": [],
        "declarations": [],
        "agent_fiche": None,
        "lignes_fiche": [],
        "periode": "",
        "service_label": "",
        "querystring": request.GET.urlencode(),
    }
