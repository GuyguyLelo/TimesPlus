from calendar import monthrange
from datetime import datetime, time

from django import forms
from django.utils import timezone

from apps.accounts.access import get_profile
from apps.accounts.form_mixins import BootstrapFormMixin, apply_bootstrap
from apps.agents.models import Agent
from apps.overtime.models import (
    Attachment,
    Holiday,
    OvertimeRequest,
    OvertimeRule,
    OvertimeType,
    WorkSchedule,
)
from apps.overtime.motifs import MOTIFS
from apps.overtime.selectors import can_view_all, fiche_agent
from apps.overtime.services.calculation import CalculationError, calculer_declaration


class _DateTimeMixin:
    def _prepare_temporal(self, date_fields=(), time_fields=()):
        for name in date_fields:
            self.fields[name].input_formats = ["%Y-%m-%d"]
            self.fields[name].widget.format = "%Y-%m-%d"
        for name in time_fields:
            self.fields[name].input_formats = ["%H:%M", "%H:%M:%S"]
            self.fields[name].widget.format = "%H:%M"


class OvertimeRequestForm(BootstrapFormMixin, _DateTimeMixin, forms.ModelForm):
    class Meta:
        model = OvertimeRequest
        fields = ["agent", "date_travail", "heure_debut", "heure_fin", "motif", "observation"]
        widgets = {
            "date_travail": forms.DateInput(attrs={"type": "date"}),
            "heure_debut": forms.TimeInput(attrs={"type": "time"}),
            "heure_fin": forms.TimeInput(attrs={"type": "time"}),
            "motif": forms.Select(),
            "observation": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self._prepare_temporal(("date_travail",), ("heure_debut", "heure_fin"))
        profile = get_profile(user)
        if can_view_all(user) or user.is_superuser:
            self.fields["agent"].queryset = Agent.objects.filter(actif=True).select_related("service")
        else:
            self.fields["agent"].queryset = Agent.objects.filter(pk=profile.agent_id)
            self.fields["agent"].initial = profile.agent_id
            self.fields["agent"].widget = forms.HiddenInput()
        motifs = list(MOTIFS)
        if self.instance.pk and self.instance.motif and self.instance.motif not in dict(MOTIFS):
            motifs.insert(0, (self.instance.motif, self.instance.motif))
        self.fields["motif"] = forms.ChoiceField(label="Motif", choices=motifs)
        self.recherche_agent = can_view_all(user) or user.is_superuser
        if self.recherche_agent:
            self.fields["agent"].widget = forms.HiddenInput()
            self.fields["agent"].required = True
        self.agent_label = ""
        self.agent_carte = None
        chosen_id = self.data.get("agent") if self.is_bound else self.instance.agent_id
        if str(chosen_id or "").isdigit():
            chosen = (
                Agent.objects.select_related("service", "grade", "fonction")
                .filter(pk=int(chosen_id))
                .first()
            )
            if chosen is not None:
                self.agent_label = str(chosen)
                self.agent_carte = fiche_agent(chosen)
        today = timezone.localdate()
        from apps.overtime.paiement import mois_est_paye, mois_ouverts

        ouverts = mois_ouverts(ANNEE_MOIS)
        self.saisie_fermee = not ouverts
        choix = [
            (f"{ANNEE_MOIS}-{month:02d}", f"{_NOMS_MOIS[month - 1]} {ANNEE_MOIS}")
            for month in ouverts
        ]
        if self.instance.pk and self.instance.date_travail:
            reference = self.instance.date_travail
        else:
            reference = _prochaine_date_ouverte(today, ouverts)
            if not self.is_bound:
                self.initial["date_travail"] = reference
        self.fields["date_travail"].widget.attrs["data-today"] = today.isoformat()
        mois = reference.strftime("%Y-%m")
        if self.is_bound and self.data.get("mois"):
            mois = self.data.get("mois")
        elif mois_est_paye(reference.year, reference.month) and choix:
            mois = choix[0][0]
            if not self.is_bound and not self.instance.pk:
                self.initial["date_travail"] = _bornes_mois(mois)[0]
        try:
            start, end = _bornes_mois(mois)
        except ValueError:
            mois = choix[0][0] if choix else reference.strftime("%Y-%m")
            start, end = _bornes_mois(mois) if choix else (reference, reference)
        self.fields["mois"] = forms.ChoiceField(
            label="Mois",
            required=False,
            choices=choix or [("", "Aucun mois ouvert")],
            initial=mois if not self.saisie_fermee else "",
        )
        self.fields["date_travail"].widget.attrs["min"] = start.isoformat()
        self.fields["date_travail"].widget.attrs["max"] = end.isoformat()
        self.initial["heure_debut"] = time(16, 0)
        self.fields["heure_debut"].widget.attrs["readonly"] = True
        self.fields["heure_debut"].widget.attrs["aria-readonly"] = "true"
        self.fields["heure_debut"].widget.attrs["tabindex"] = "-1"
        self.fields["heure_debut"].help_text = "Heure de début fixée à 16:00."
        self.fields["heure_fin"].widget.attrs["min"] = "16:00"
        self.fields["heure_fin"].help_text = "L'heure de fin ne peut pas être inférieure à 16:00."
        self.fields["observation"].required = False
        self.order_fields(["agent", "mois", "date_travail", "heure_debut", "heure_fin", "motif", "observation"])
        apply_bootstrap(self)
        locked = self.fields["heure_debut"].widget.attrs.get("class", "")
        self.fields["heure_debut"].widget.attrs["class"] = f"{locked} is-locked".strip()

    def clean_heure_debut(self):
        return time(16, 0)

    def clean_heure_fin(self):
        value = self.cleaned_data.get("heure_fin")
        if value is not None and value < time(16, 0):
            raise forms.ValidationError("L'heure de fin ne peut pas être inférieure à 16:00.")
        return value

    def clean(self):
        cleaned = super().clean()
        agent = cleaned.get("agent")
        jour = cleaned.get("date_travail")
        debut = cleaned.get("heure_debut")
        fin = cleaned.get("heure_fin")
        mois = (cleaned.get("mois") or "").strip()
        if mois and jour:
            try:
                start, end = _bornes_mois(mois)
            except ValueError:
                self.add_error("mois", "Choisissez un mois valide.")
            else:
                if not start <= jour <= end:
                    self.add_error("date_travail", "La date doit appartenir au mois sélectionné.")
        if self.saisie_fermee or (mois and mois not in dict(self.fields["mois"].choices)):
            self.add_error("mois", "Ce mois est clôturé. Aucune saisie n'est autorisée.")
            return cleaned
        if jour is not None:
            from apps.overtime.paiement import mois_est_paye

            if mois_est_paye(jour.year, jour.month):
                self.add_error(
                    "date_travail",
                    "Ce mois est clôturé. Les heures supplémentaires payées ne peuvent plus être saisies.",
                )
                return cleaned
        if not agent or not jour or not debut or not fin:
            return cleaned
        if not can_view_all(self.user) and not self.user.is_superuser:
            profile = get_profile(self.user)
            if profile.agent_id != agent.id:
                raise forms.ValidationError("Vous ne pouvez déclarer que vos propres heures.")
        try:
            self.calculation = calculer_declaration(
                agent,
                jour,
                debut,
                fin,
                exclude_id=self.instance.pk,
            )
        except CalculationError as exc:
            raise forms.ValidationError(exc.message) from exc
        return cleaned


ANNEE_MOIS = 2026
_NOMS_MOIS = (
    "Janvier",
    "Février",
    "Mars",
    "Avril",
    "Mai",
    "Juin",
    "Juillet",
    "Août",
    "Septembre",
    "Octobre",
    "Novembre",
    "Décembre",
)


def _prochaine_date_ouverte(jour, ouverts):
    """Première date encore saisissable, à partir du jour courant."""
    if jour.year == ANNEE_MOIS and jour.month in ouverts:
        return jour
    suivants = [month for month in ouverts if jour.year < ANNEE_MOIS or month >= jour.month]
    month = suivants[0] if suivants else (ouverts[0] if ouverts else jour.month)
    if month == jour.month and jour.year == ANNEE_MOIS:
        return jour
    return jour.replace(year=ANNEE_MOIS, month=month, day=1)


def _choix_mois(annees):
    choices = []
    for year in sorted(annees):
        for month in range(1, 13):
            choices.append((f"{year}-{month:02d}", f"{_NOMS_MOIS[month - 1]} {year}"))
    return choices


def _bornes_mois(value):
    parsed = datetime.strptime(value, "%Y-%m")
    last = monthrange(parsed.year, parsed.month)[1]
    return parsed.date().replace(day=1), parsed.date().replace(day=last)


class AttachmentForm(BootstrapFormMixin, forms.Form):
    type_document = forms.ChoiceField(label="Type de document", choices=Attachment.TypeDocument.choices)
    fichier = forms.FileField(label="Fichier")


class WorkScheduleForm(BootstrapFormMixin, _DateTimeMixin, forms.ModelForm):
    class Meta:
        model = WorkSchedule
        fields = [
            "nom",
            "service",
            "jour_semaine",
            "heure_debut",
            "heure_fin",
            "pause_debut",
            "pause_fin",
            "actif",
        ]
        widgets = {
            "heure_debut": forms.TimeInput(attrs={"type": "time"}),
            "heure_fin": forms.TimeInput(attrs={"type": "time"}),
            "pause_debut": forms.TimeInput(attrs={"type": "time"}),
            "pause_fin": forms.TimeInput(attrs={"type": "time"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._prepare_temporal((), ("heure_debut", "heure_fin", "pause_debut", "pause_fin"))
        self.fields["service"].required = False


class HolidayForm(BootstrapFormMixin, _DateTimeMixin, forms.ModelForm):
    class Meta:
        model = Holiday
        fields = ["date", "libelle", "type", "actif"]
        widgets = {"date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._prepare_temporal(("date",), ())


class OvertimeTypeForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = OvertimeType
        fields = ["code", "libelle", "coefficient", "description", "actif"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def clean_code(self):
        return (self.cleaned_data["code"] or "").strip().upper()


class OvertimeRuleForm(BootstrapFormMixin, _DateTimeMixin, forms.ModelForm):
    class Meta:
        model = OvertimeRule
        fields = [
            "nom",
            "type_heure",
            "priorite",
            "heure_debut",
            "heure_fin",
            "applicable_weekend",
            "applicable_ferie",
            "plafond_journalier",
            "plafond_mensuel",
            "coefficient",
            "actif",
            "date_debut_validite",
            "date_fin_validite",
        ]
        widgets = {
            "heure_debut": forms.TimeInput(attrs={"type": "time"}),
            "heure_fin": forms.TimeInput(attrs={"type": "time"}),
            "date_debut_validite": forms.DateInput(attrs={"type": "date"}),
            "date_fin_validite": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._prepare_temporal(
            ("date_debut_validite", "date_fin_validite"),
            ("heure_debut", "heure_fin"),
        )
        self.fields["type_heure"].queryset = OvertimeType.objects.filter(actif=True)
