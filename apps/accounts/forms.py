from django import forms
from django.contrib.auth.models import Group, Permission, User
from django.contrib.auth.password_validation import validate_password

from apps.accounts.form_mixins import BootstrapFormMixin
from apps.accounts.roles import GROUP_NAMES
from apps.agents.models import Agent
from apps.services.models import Service

LIBELLES_APPLICATIONS = {
    "accounts": "Comptes",
    "agents": "Personnel",
    "audit": "Audit",
    "auth": "Authentification",
    "overtime": "Heures supplémentaires",
    "reports": "Rapports",
    "services": "Services",
    "settings_app": "Paramètres",
    "workflow": "Validation",
}


class UserCreateForm(BootstrapFormMixin, forms.Form):
    username = forms.CharField(label="Identifiant", max_length=150)
    first_name = forms.CharField(label="Prénom", max_length=150, required=False)
    last_name = forms.CharField(label="Nom", max_length=150, required=False)
    email = forms.EmailField(label="E-mail", required=False)
    password1 = forms.CharField(label="Mot de passe", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirmation", widget=forms.PasswordInput)
    groups = forms.ModelMultipleChoiceField(
        label="Rôles",
        queryset=Group.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    is_active = forms.BooleanField(label="Compte actif", required=False, initial=True)
    is_staff = forms.BooleanField(label="Accès à l'administration Django", required=False)
    agent = forms.ModelChoiceField(
        label="Agent lié",
        queryset=Agent.objects.none(),
        required=False,
    )
    service = forms.ModelChoiceField(
        label="Service de responsabilité",
        queryset=Service.objects.filter(actif=True),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["groups"].queryset = Group.objects.order_by("name")
        self.fields["agent"].queryset = Agent.objects.select_related("service").order_by("nom")

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("Cet identifiant est déjà utilisé.")
        return username

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get("password1")
        password2 = cleaned.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "Les deux mots de passe ne correspondent pas.")
        if password1:
            user = User(
                username=cleaned.get("username", ""),
                first_name=cleaned.get("first_name", ""),
                last_name=cleaned.get("last_name", ""),
                email=cleaned.get("email", ""),
            )
            try:
                validate_password(password1, user=user)
            except forms.ValidationError as exc:
                self.add_error("password1", exc)
        agent = cleaned.get("agent")
        if agent and hasattr(agent, "user_profile"):
            self.add_error("agent", "Cet agent est déjà lié à un utilisateur.")
        return cleaned


class UserUpdateForm(BootstrapFormMixin, forms.Form):
    first_name = forms.CharField(label="Prénom", max_length=150, required=False)
    last_name = forms.CharField(label="Nom", max_length=150, required=False)
    email = forms.EmailField(label="E-mail", required=False)
    password1 = forms.CharField(label="Nouveau mot de passe", widget=forms.PasswordInput, required=False)
    password2 = forms.CharField(label="Confirmation", widget=forms.PasswordInput, required=False)
    groups = forms.ModelMultipleChoiceField(
        label="Rôles",
        queryset=Group.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    is_active = forms.BooleanField(label="Compte actif", required=False)
    is_staff = forms.BooleanField(label="Accès à l'administration Django", required=False)
    agent = forms.ModelChoiceField(label="Agent lié", queryset=Agent.objects.none(), required=False)
    service = forms.ModelChoiceField(
        label="Service de responsabilité",
        queryset=Service.objects.filter(actif=True),
        required=False,
    )

    def __init__(self, *args, user_obj=None, **kwargs):
        self.user_obj = user_obj
        super().__init__(*args, **kwargs)
        self.fields["groups"].queryset = Group.objects.order_by("name")
        linked = Agent.objects.select_related("service").order_by("nom")
        self.fields["agent"].queryset = linked

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get("password1")
        password2 = cleaned.get("password2")
        if password1 or password2:
            if password1 != password2:
                self.add_error("password2", "Les deux mots de passe ne correspondent pas.")
            elif password1:
                try:
                    validate_password(password1, user=self.user_obj)
                except forms.ValidationError as exc:
                    self.add_error("password1", exc)
        agent = cleaned.get("agent")
        if agent:
            existing = getattr(agent, "user_profile", None)
            if existing and existing.user_id != self.user_obj.id:
                self.add_error("agent", "Cet agent est déjà lié à un utilisateur.")
        return cleaned


class GroupForm(BootstrapFormMixin, forms.ModelForm):
    permissions = forms.ModelMultipleChoiceField(
        label="Permissions",
        queryset=Permission.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    membres = forms.ModelMultipleChoiceField(
        label="Membres",
        queryset=User.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = Group
        fields = ["name"]
        labels = {"name": "Nom"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["permissions"].queryset = (
            Permission.objects.select_related("content_type")
            .exclude(content_type__app_label__in={"admin", "contenttypes", "sessions"})
            .order_by("content_type__app_label", "name")
        )
        self.fields["membres"].queryset = User.objects.order_by("username")
        self.fields["name"].widget.attrs["autofocus"] = True
        self.protege = bool(self.instance.pk and self.instance.name in GROUP_NAMES)
        if self.instance.pk:
            self.fields["permissions"].initial = self.instance.permissions.all()
            self.fields["membres"].initial = self.instance.user_set.all()
        if self.protege:
            self.fields["name"].disabled = True
            self.fields["name"].help_text = "Le nom d'un rôle de l'application ne peut pas être modifié."

    def clean_name(self):
        nom = (self.cleaned_data.get("name") or self.instance.name or "").strip()
        doublon = Group.objects.filter(name__iexact=nom)
        if self.instance.pk:
            doublon = doublon.exclude(pk=self.instance.pk)
        if doublon.exists():
            raise forms.ValidationError("Ce nom est déjà utilisé.")
        if self.protege and nom != self.instance.name:
            raise forms.ValidationError("Le nom d'un rôle de l'application ne peut pas être modifié.")
        return nom

    def save(self, commit=True):
        groupe = super().save(commit=commit)
        if commit:
            groupe.permissions.set(self.cleaned_data["permissions"])
            groupe.user_set.set(self.cleaned_data["membres"])
        return groupe


def permissions_par_application():
    blocs = {}
    permissions = (
        Permission.objects.select_related("content_type")
        .exclude(content_type__app_label__in={"admin", "contenttypes", "sessions"})
        .order_by("content_type__app_label", "name")
    )
    for permission in permissions:
        blocs.setdefault(permission.content_type.app_label, []).append(permission)
    return sorted(
        (
            {
                "code": code,
                "label": LIBELLES_APPLICATIONS.get(code, code),
                "perms": perms,
            }
            for code, perms in blocs.items()
        ),
        key=lambda bloc: bloc["label"],
    )


def valeurs_cochees(form, nom):
    valeur = form[nom].value()
    if valeur is None:
        return []
    if hasattr(valeur, "values_list"):
        return list(valeur.values_list("pk", flat=True))
    coches = []
    for item in valeur:
        if hasattr(item, "pk"):
            coches.append(item.pk)
        elif str(item).isdigit():
            coches.append(int(item))
    return coches
