from django import forms

from apps.accounts.form_mixins import BootstrapFormMixin
from apps.settings_app.models import SiteSettings


class SiteSettingsForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = SiteSettings
        fields = [
            "nom_administration",
            "sigle",
            "devise",
            "adresse",
            "email_contact",
            "jours_weekend",
            "plafond_journalier_minutes",
            "plafond_mensuel_minutes",
            "taille_max_fichier_mo",
            "elements_par_page",
            "autoriser_date_future",
            "autoriser_agent_inactif",
        ]
        widgets = {"adresse": forms.Textarea(attrs={"rows": 3})}

    def clean_elements_par_page(self):
        value = self.cleaned_data["elements_par_page"]
        if value < 5 or value > 100:
            raise forms.ValidationError("Choisissez une pagination entre 5 et 100.")
        return value

    def clean_taille_max_fichier_mo(self):
        value = self.cleaned_data["taille_max_fichier_mo"]
        if value < 1 or value > 25:
            raise forms.ValidationError("La taille maximale doit être comprise entre 1 et 25 Mo.")
        return value

    def clean_jours_weekend(self):
        raw = self.cleaned_data["jours_weekend"]
        days = []
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            if not part.isdigit() or not 0 <= int(part) <= 6:
                raise forms.ValidationError("Utilisez des numéros de 0 (lundi) à 6 (dimanche), séparés par des virgules.")
            days.append(str(int(part)))
        return ",".join(days)
