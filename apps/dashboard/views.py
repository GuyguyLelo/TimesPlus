from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Sum
from django.shortcuts import render
from django.utils import timezone
from django.views.generic import TemplateView

from apps.overtime.formatting import format_minutes
from apps.overtime.models import OvertimeRequest, OvertimeType
from apps.overtime.selectors import agents_visible, apply_overtime_filters, overtime_for_user
from apps.services.selectors import services_for_user


def error_403(request, exception):
    return render(request, "403.html", status=403)


def error_404(request, exception):
    return render(request, "404.html", status=404)


def error_500(request):
    return render(request, "500.html", status=500)

MOIS = [
    "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
    "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
]


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        year = self.request.GET.get("annee") or str(today.year)
        if not str(year).isdigit():
            year = str(today.year)
        params = self.request.GET.copy()
        params["debut"] = f"{year}-01-01"
        params["fin"] = f"{year}-12-31"
        scoped = overtime_for_user(self.request.user)
        filtered = apply_overtime_filters(scoped, params)
        if str(self.request.GET.get("mois") or "").isdigit():
            filtered = filtered.filter(date_travail__month=int(self.request.GET["mois"]))

        approved = filtered.filter(statut=OvertimeRequest.Statut.APPROUVE)
        minutes = approved.aggregate(total=Sum("duree_minutes"))["total"] or 0
        context["cards"] = {
            "agents": agents_visible(self.request.user).filter(actif=True).count(),
            "minutes": minutes,
            "duree": format_minutes(minutes),
            "pending": filtered.filter(
                statut__in=[OvertimeRequest.Statut.SOUMIS, OvertimeRequest.Statut.EN_VALIDATION]
            ).count(),
            "approved": filtered.filter(statut=OvertimeRequest.Statut.APPROUVE).count(),
            "rejected": filtered.filter(statut=OvertimeRequest.Statut.REJETE).count(),
        }

        year_approved = scoped.filter(
            statut=OvertimeRequest.Statut.APPROUVE,
            date_travail__year=int(year),
        )
        if str(self.request.GET.get("service") or "").isdigit():
            year_approved = year_approved.filter(agent__service_id=int(self.request.GET["service"]))
        monthly = {
            row["date_travail__month"]: row["total"] or 0
            for row in year_approved.values("date_travail__month").annotate(total=Sum("duree_minutes"))
        }
        context["chart_months"] = [
            {"label": MOIS[index], "value": int(monthly.get(index + 1, 0))}
            for index in range(12)
        ]
        context["chart_services"] = [
            {"label": row["agent__service__nom"] or "—", "value": int(row["total"] or 0)}
            for row in approved.values("agent__service__nom").annotate(total=Sum("duree_minutes")).order_by("-total")[:8]
        ]
        context["chart_types"] = [
            {"label": row["type_heure__libelle"] or "—", "value": int(row["total"] or 0)}
            for row in approved.values("type_heure__libelle").annotate(total=Sum("duree_minutes")).order_by("-total")
        ]
        context["chart_status"] = [
            {"label": label, "value": count}
            for label, count in (
                (dict(OvertimeRequest.Statut.choices).get(row["statut"], row["statut"]), row["total"])
                for row in filtered.values("statut").annotate(total=Count("id"))
            )
        ]
        context["recent"] = filtered.select_related("agent", "type_heure")[:8]
        context["services"] = services_for_user(self.request.user)
        context["types"] = OvertimeType.objects.filter(actif=True)
        context["statuts"] = OvertimeRequest.Statut.choices
        context["years"] = range(today.year - 3, today.year + 2)
        context["months"] = list(enumerate(MOIS, start=1))
        context["selected"] = {
            "annee": int(year),
            "mois": self.request.GET.get("mois", ""),
            "service": self.request.GET.get("service", ""),
            "statut": self.request.GET.get("statut", ""),
            "type": self.request.GET.get("type", ""),
        }
        return context
