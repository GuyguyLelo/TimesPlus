from django import forms
from django.utils import timezone

from apps.accounts.form_mixins import BootstrapFormMixin, apply_bootstrap
from apps.agents.models import Agent
from apps.overtime.forms import ANNEE_MOIS, _choix_mois
from apps.overtime.models import OvertimeRequest, OvertimeType
from apps.services.models import Service


class ReportFilterForm(BootstrapFormMixin, forms.Form):
    debut = forms.DateField(
        label="Du",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        input_formats=["%Y-%m-%d"],
    )
    fin = forms.DateField(
        label="Au",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        input_formats=["%Y-%m-%d"],
    )
    service = forms.ModelChoiceField(
        label="Service",
        queryset=Service.objects.filter(actif=True),
        required=False,
    )
    agent = forms.ModelChoiceField(
        label="Agent",
        queryset=Agent.objects.filter(actif=True).select_related("service"),
        required=False,
    )
    statut = forms.ChoiceField(
        label="Statut",
        required=False,
        choices=[("", "Approuvées")] + [("TOUS", "Tous les statuts")] + list(OvertimeRequest.Statut.choices),
    )
    type_heure = forms.ModelChoiceField(
        label="Type d'heure",
        queryset=OvertimeType.objects.filter(actif=True),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["debut"].widget.format = "%Y-%m-%d"
        self.fields["fin"].widget.format = "%Y-%m-%d"


class MonthlyReportFilterForm(ReportFilterForm):
    mois = forms.ChoiceField(label="Mois", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop("debut", None)
        self.fields.pop("fin", None)
        today = timezone.localdate()
        raw = (self.data.get("mois") or "") if self.is_bound else ""
        self.fields["mois"].choices = _choix_mois({ANNEE_MOIS})
        if not raw:
            self.initial["mois"] = today.strftime("%Y-%m")
        self.order_fields(["mois", "service", "agent", "statut", "type_heure"])
        apply_bootstrap(self)


class RapportMensuelFilterForm(MonthlyReportFilterForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop("statut", None)
