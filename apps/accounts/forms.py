from django import forms
from django.contrib.auth.models import Group, User
from django.contrib.auth.password_validation import validate_password

from apps.accounts.form_mixins import BootstrapFormMixin
from apps.agents.models import Agent
from apps.services.models import Service


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
