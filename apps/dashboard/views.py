from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Sum
from django.shortcuts import render
from django.utils import timezone
from django.views.generic import TemplateView

from apps.overtime.formatting import format_minutes, format_montant
from apps.overtime.forms import ANNEE_MOIS, _NOMS_MOIS, _bornes_mois, _choix_mois
from apps.overtime.models import OvertimeRequest, OvertimeType, PaiementMois
from apps.overtime.paiement import mois_payes_numeros
from apps.overtime.selectors import overtime_for_user
from apps.reports.services import by_agent
from apps.services.selectors import services_for_user


def error_403(request, exception):
    return render(request, "403.html", status=403)


def error_404(request, exception):
    return render(request, "404.html", status=404)


def error_500(request):
    return render(request, "500.html", status=500)

class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        mois_courant = today.month if today.year == ANNEE_MOIS else 10
        choisi = (self.request.GET.get("mois") or "").strip()
        if choisi not in {f"{ANNEE_MOIS}-{month:02d}" for month in range(1, 13)}:
            choisi = f"{ANNEE_MOIS}-{mois_courant:02d}"
        numero = int(choisi[5:7])
        debut, fin = _bornes_mois(choisi)
        payes = set(mois_payes_numeros(ANNEE_MOIS))

        def restreint(queryset):
            service = self.request.GET.get("service") or ""
            type_heure = self.request.GET.get("type") or ""
            if str(service).isdigit():
                queryset = queryset.filter(agent__service_id=int(service))
            if str(type_heure).isdigit():
                queryset = queryset.filter(type_heure_id=int(type_heure))
            return queryset

        saisies = restreint(
            overtime_for_user(self.request.user).filter(statut=OvertimeRequest.Statut.APPROUVE)
        )
        du_mois = saisies.filter(date_travail__gte=debut, date_travail__lte=fin)
        totaux = du_mois.aggregate(
            minutes=Sum("duree_minutes"),
            montant=Sum("montant_estime"),
            nombre=Count("id"),
        )
        paiement = PaiementMois.objects.filter(annee=ANNEE_MOIS, mois=numero).first()
        context.update(
            {
                "title": "Tableau de bord",
                "periode": f"{_NOMS_MOIS[numero - 1]} {ANNEE_MOIS}",
                "mois_valeur": choisi,
                "cards": {
                    "agents": du_mois.order_by().values("agent_id").distinct().count(),
                    "saisies": totaux["nombre"] or 0,
                    "duree": format_minutes(totaux["minutes"] or 0),
                    "montant": format_montant(totaux["montant"] or 0),
                    "paye": numero in payes,
                    "cloture": paiement.cloture_le if paiement else None,
                },
                "chart_montants": [
                    {"label": row["nom"], "value": float(row["montant"] or 0)}
                    for row in by_agent(du_mois)
                ],
                "chart_types": [
                    {"label": row["type_heure__libelle"] or "—", "value": float(row["total"] or 0)}
                    for row in du_mois.values("type_heure__libelle")
                    .annotate(total=Sum("montant_estime"))
                    .order_by("-total")
                ],
                "services": services_for_user(self.request.user),
                "types": OvertimeType.objects.filter(actif=True),
                "mois_choices": _choix_mois({ANNEE_MOIS}),
                "selected": {
                    "mois": choisi,
                    "service": self.request.GET.get("service", ""),
                    "type": self.request.GET.get("type", ""),
                },
            }
        )
        return context
