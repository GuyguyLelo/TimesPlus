from django import forms
from django.core.files.uploadedfile import UploadedFile
from django.db.models import Q

from apps.accounts.form_mixins import BootstrapFormMixin
from apps.agents.models import Agent, Bareme, Fonction, Grade
from apps.services.selectors import services_pour_affectation

MAX_PHOTO_BYTES = 2 * 1024 * 1024
PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp"}


def _arbre_services(queryset):
    nodes = {}
    for item in queryset:
        nodes[item.pk] = {
            "id": item.pk,
            "code": item.code,
            "nom": item.nom,
            "niveau": item.niveau,
            "niveau_label": item.get_niveau_display(),
            "parent": item.service_parent_id,
            "children": [],
        }
    roots = []
    for node in nodes.values():
        parent = nodes.get(node["parent"])
        if parent is None:
            roots.append(node)
        else:
            parent["children"].append(node)

    def sort_tree(items):
        items.sort(key=lambda row: (row["code"], row["nom"]))
        for row in items:
            sort_tree(row["children"])

    sort_tree(roots)
    return roots


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
        self.fields["grade"].label = "Grade statutaire"
        self.fields["grade"].empty_label = "Choisir un grade"
        self.fields["fonction"].empty_label = "Choisir une fonction"
        self.fields["grade"].label_from_instance = lambda item: (
            f"{item.abreviation} · {item}" if item.abreviation else f"{item.categorie} · {item}"
        )
        self.fields["fonction"].label_from_instance = lambda item: f"{item.get_famille_display()} · {item.libelle}"
        self.fields["service"].queryset = services_pour_affectation(self.instance.service_id)
        self.fields["service"].label = "Cadre organique"
        self.fields["service"].empty_label = "Choisir un cadre organique"
        self.service_arbre = _arbre_services(self.fields["service"].queryset)

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


class BaremeForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Bareme
        fields = ["grade", "fonction", "taux_horaire", "actif"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["grade"].queryset = _kept(Grade, self.instance.grade_id)
        self.fields["fonction"].queryset = _kept(Fonction, self.instance.fonction_id)
        self.fields["grade"].empty_label = "Choisir un grade"
        self.fields["fonction"].empty_label = "Choisir une fonction"
        self.fields["grade"].label_from_instance = lambda item: (
            f"{item.abreviation} · {item}" if item.abreviation else f"{item.categorie} · {item}"
        )
        self.fields["fonction"].label_from_instance = lambda item: f"{item.get_famille_display()} · {item.libelle}"

    def clean_taux_horaire(self):
        value = self.cleaned_data["taux_horaire"]
        if value < 0:
            raise forms.ValidationError("Le taux horaire ne peut pas être négatif.")
        return value

    def clean(self):
        cleaned = super().clean()
        grade = cleaned.get("grade")
        fonction = cleaned.get("fonction")
        if not grade or not fonction:
            return cleaned
        doublon = Bareme.objects.filter(grade=grade, fonction=fonction)
        if self.instance.pk:
            doublon = doublon.exclude(pk=self.instance.pk)
        if doublon.exists():
            raise forms.ValidationError("Un barème existe déjà pour ce grade et cette fonction.")
        return cleaned


class AgentPhotoForm(forms.Form):
    photo = forms.ImageField(
        label="Photo",
        widget=forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
    )

    def clean_photo(self):
        return validate_agent_photo(self.cleaned_data.get("photo"))
