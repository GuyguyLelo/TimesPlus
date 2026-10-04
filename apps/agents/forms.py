from django import forms
from django.core.files.uploadedfile import UploadedFile
from django.db.models import Q

from apps.accounts.form_mixins import BootstrapFormMixin
from apps.agents.models import Agent, Fonction, Grade

MAX_PHOTO_BYTES = 2 * 1024 * 1024
PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp"}


def _kept(model, current_id):
    query = Q(actif=True)
    if current_id:
        query |= Q(pk=current_id)
    return model.objects.filter(query).order_by("ordre", "libelle")


def validate_agent_photo(photo):
    if not isinstance(photo, UploadedFile):
        return photo
    if photo.size > MAX_PHOTO_BYTES:
        raise forms.ValidationError("La photo ne doit pas dépasser 2 Mo.")
    content_type = (getattr(photo, "content_type", "") or "").split(";")[0].lower()
    if content_type not in PHOTO_TYPES:
        raise forms.ValidationError("Formats acceptés : JPEG, PNG ou WebP.")
    return photo


class AgentForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Agent
        fields = [
            "photo",
            "matricule",
            "nom",
            "postnom",
            "prenom",
            "sexe",
            "date_naissance",
            "email",
            "telephone",
            "grade",
            "fonction",
            "service",
            "date_engagement",
            "statut",
            "taux_horaire",
            "actif",
        ]
        widgets = {
            "date_naissance": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "date_engagement": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "photo": forms.ClearableFileInput(
                attrs={"accept": "image/jpeg,image/png,image/webp"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("date_naissance", "date_engagement"):
            self.fields[name].input_formats = ["%Y-%m-%d"]
        self.fields["grade"].queryset = _kept(Grade, self.instance.grade_id)
        self.fields["fonction"].queryset = _kept(Fonction, self.instance.fonction_id)
        self.fields["grade"].empty_label = "Choisir un grade"
        self.fields["fonction"].empty_label = "Choisir une fonction"
        self.fields["grade"].label_from_instance = lambda item: f"{item.categorie} · {item}"
        self.fields["fonction"].label_from_instance = lambda item: f"{item.get_famille_display()} · {item.libelle}"

    def clean_photo(self):
        return validate_agent_photo(self.cleaned_data.get("photo"))

    def save(self, commit=True):
        previous = ""
        if self.instance.pk:
            stored = Agent.objects.filter(pk=self.instance.pk).values_list("photo", flat=True).first()
            previous = stored or ""
        agent = super().save(commit=commit)
        current = agent.photo.name if agent.photo else ""
        if commit and previous and previous != current:
            agent.photo.storage.delete(previous)
        return agent

    def clean_matricule(self):
        return (self.cleaned_data["matricule"] or "").strip().upper()

    def clean_taux_horaire(self):
        value = self.cleaned_data["taux_horaire"]
        if value < 0:
            raise forms.ValidationError("Le taux horaire ne peut pas être négatif.")
        return value


class AgentPhotoForm(forms.Form):
    photo = forms.ImageField(
        label="Photo",
        widget=forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
    )

    def clean_photo(self):
        return validate_agent_photo(self.cleaned_data.get("photo"))
