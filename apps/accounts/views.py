from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import Group, User
from django.contrib.auth.views import LoginView
from django.db.models import Count, ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.csrf import csrf_failure as django_csrf_failure
from django.views.generic import DeleteView, DetailView, FormView, ListView

from apps.accounts.access import get_profile
from apps.accounts.forms import (
    GroupForm,
    UserCreateForm,
    UserUpdateForm,
    permissions_par_application,
    valeurs_cochees,
)
from apps.accounts.roles import GROUP_NAMES
from apps.accounts.mixins import DENIED, AppPermissionMixin, PageSizeMixin, page_size
from apps.audit.utils import journaliser


def csrf_failure(request, reason=""):
    """Renvoie au tableau de bord si la session est déjà ouverte.

    Un second envoi du formulaire de connexion arrive après la rotation du
    jeton : la session est valide, seul le jeton du premier envoi est périmé.
    """
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        return redirect(settings.LOGIN_REDIRECT_URL)
    if request.path == reverse("login"):
        return redirect("login")
    return django_csrf_failure(request, reason=reason)


class AppLoginView(LoginView):
    template_name = "registration/login.html"
    redirect_authenticated_user = True


class UserListView(AppPermissionMixin, ListView):
    permission_required = "accounts.manage_users"
    template_name = "accounts/user_list.html"
    context_object_name = "utilisateurs"

    def get_paginate_by(self, queryset):
        return page_size()

    def get_queryset(self):
        queryset = User.objects.prefetch_related("groups").select_related("profile", "profile__agent", "profile__service")
        q = self.request.GET.get("q", "").strip()
        if q:
            queryset = queryset.filter(
                Q(username__icontains=q)
                | Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(email__icontains=q)
            )
        return queryset.order_by("username")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.request.GET.get("q", "")
        return context


class UserCreateView(AppPermissionMixin, FormView):
    permission_required = "accounts.manage_users"
    template_name = "accounts/user_form.html"
    form_class = UserCreateForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Nouvel utilisateur"
        return context

    def form_valid(self, form):
        user = User(
            username=form.cleaned_data["username"],
            first_name=form.cleaned_data["first_name"],
            last_name=form.cleaned_data["last_name"],
            email=form.cleaned_data["email"],
            is_active=form.cleaned_data["is_active"],
            is_staff=form.cleaned_data["is_staff"],
        )
        user.set_password(form.cleaned_data["password1"])
        user.save()
        user.groups.set(form.cleaned_data["groups"])
        profile = get_profile(user)
        profile.agent = form.cleaned_data["agent"]
        profile.service = form.cleaned_data["service"]
        profile.save()
        journaliser(
            request=self.request,
            action="CREATION",
            model_name="User",
            object_id=user.pk,
            new_values={
                "username": user.username,
                "groupes": list(user.groups.values_list("name", flat=True)),
                "agent": profile.agent_id,
                "service": profile.service_id,
            },
        )
        messages.success(self.request, "✓ Utilisateur créé avec succès.")
        return redirect("accounts:users")


class UserUpdateView(AppPermissionMixin, FormView):
    permission_required = "accounts.manage_users"
    template_name = "accounts/user_form.html"
    form_class = UserUpdateForm

    def dispatch(self, request, *args, **kwargs):
        self.user_obj = get_object_or_404(User, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user_obj"] = self.user_obj
        return kwargs

    def get_initial(self):
        profile = get_profile(self.user_obj)
        return {
            "first_name": self.user_obj.first_name,
            "last_name": self.user_obj.last_name,
            "email": self.user_obj.email,
            "groups": self.user_obj.groups.all(),
            "is_active": self.user_obj.is_active,
            "is_staff": self.user_obj.is_staff,
            "agent": profile.agent,
            "service": profile.service,
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = f"Modifier {self.user_obj.get_username()}"
        context["user_obj"] = self.user_obj
        return context

    def form_valid(self, form):
        user = self.user_obj
        old = {
            "email": user.email,
            "is_active": user.is_active,
            "is_staff": user.is_staff,
            "groupes": list(user.groups.values_list("name", flat=True)),
        }
        user.first_name = form.cleaned_data["first_name"]
        user.last_name = form.cleaned_data["last_name"]
        user.email = form.cleaned_data["email"]
        user.is_active = form.cleaned_data["is_active"]
        user.is_staff = form.cleaned_data["is_staff"]
        if form.cleaned_data.get("password1"):
            user.set_password(form.cleaned_data["password1"])
        user.save()
        user.groups.set(form.cleaned_data["groups"])
        profile = get_profile(user)
        profile.agent = form.cleaned_data["agent"]
        profile.service = form.cleaned_data["service"]
        profile.save()
        user._profile_cache = profile
        journaliser(
            request=self.request,
            action="MODIFICATION",
            model_name="User",
            object_id=user.pk,
            old_values=old,
            new_values={
                "email": user.email,
                "is_active": user.is_active,
                "is_staff": user.is_staff,
                "groupes": list(user.groups.values_list("name", flat=True)),
                "mot_de_passe_modifie": bool(form.cleaned_data.get("password1")),
            },
        )
        messages.success(self.request, "✓ Utilisateur modifié avec succès.")
        return redirect("accounts:users")


class UserDeleteView(AppPermissionMixin, DeleteView):
    permission_required = "accounts.manage_users"
    model = User
    template_name = "confirm.html"
    success_url = reverse_lazy("accounts:users")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.is_superuser:
            messages.warning(request, DENIED)
            return redirect("dashboard:home")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        refus = self._refus_propre_compte()
        if refus is not None:
            return refus
        return self.render_to_response(self.get_context_data())

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        refus = self._refus_propre_compte()
        if refus is not None:
            return refus
        return super().post(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Supprimer l'utilisateur"
        context["message"] = f"Confirmez la suppression du compte {self.object.get_username()}."
        context["cancel_url"] = reverse("accounts:users")
        return context

    def form_valid(self, form):
        username = self.object.get_username()
        object_id = str(self.object.pk)
        anciens = {
            "username": username,
            "email": self.object.email,
            "groupes": list(self.object.groups.values_list("name", flat=True)),
        }
        try:
            response = super().form_valid(form)
        except ProtectedError:
            messages.error(
                self.request,
                "Cet utilisateur ne peut pas être supprimé car des données y sont rattachées.",
            )
            return redirect("accounts:users")
        journaliser(
            request=self.request,
            action="SUPPRESSION",
            model_name="User",
            object_id=object_id,
            old_values=anciens,
        )
        messages.success(self.request, "✓ Utilisateur supprimé.")
        return response

    def _refus_propre_compte(self):
        if self.object.pk != self.request.user.pk:
            return None
        messages.error(self.request, "Vous ne pouvez pas supprimer votre propre compte.")
        return redirect("accounts:users")


class GroupListView(PageSizeMixin, AppPermissionMixin, ListView):
    permission_required = "accounts.manage_users"
    template_name = "accounts/group_list.html"
    context_object_name = "groupes"

    def get_queryset(self):
        return Group.objects.annotate(
            nb_permissions=Count("permissions", distinct=True),
            nb_membres=Count("user", distinct=True),
        ).order_by("name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["groupes_proteges"] = GROUP_NAMES
        return context


class GroupFormMixin:
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = context["form"]
        context["permissions_groupes"] = permissions_par_application()
        context["permissions_cochees"] = valeurs_cochees(form, "permissions")
        context["protege"] = getattr(form, "protege", False)
        return context


class GroupCreateView(GroupFormMixin, AppPermissionMixin, FormView):
    permission_required = "accounts.manage_users"
    template_name = "accounts/group_form.html"
    form_class = GroupForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Nouveau groupe"
        return context

    def form_valid(self, form):
        groupe = form.save()
        journaliser(
            request=self.request,
            action="CREATION",
            model_name="Group",
            object_id=groupe.pk,
            new_values={
                "nom": groupe.name,
                "permissions": groupe.permissions.count(),
                "membres": list(groupe.user_set.values_list("username", flat=True)),
            },
        )
        messages.success(self.request, "✓ Groupe créé.")
        return redirect("accounts:group_detail", pk=groupe.pk)


class GroupUpdateView(GroupFormMixin, AppPermissionMixin, FormView):
    permission_required = "accounts.manage_users"
    template_name = "accounts/group_form.html"
    form_class = GroupForm

    def dispatch(self, request, *args, **kwargs):
        self.groupe = get_object_or_404(Group, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.groupe
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = f"Modifier {self.groupe.name}"
        context["groupe"] = self.groupe
        return context

    def form_valid(self, form):
        anciens = {
            "nom": self.groupe.name,
            "permissions": self.groupe.permissions.count(),
        }
        groupe = form.save()
        journaliser(
            request=self.request,
            action="MODIFICATION",
            model_name="Group",
            object_id=groupe.pk,
            old_values=anciens,
            new_values={
                "nom": groupe.name,
                "permissions": groupe.permissions.count(),
                "membres": list(groupe.user_set.values_list("username", flat=True)),
            },
        )
        messages.success(self.request, "✓ Groupe modifié.")
        return redirect("accounts:group_detail", pk=groupe.pk)


class GroupDeleteView(AppPermissionMixin, DeleteView):
    permission_required = "accounts.manage_users"
    model = Group
    template_name = "confirm.html"
    success_url = reverse_lazy("accounts:groups")
    context_object_name = "groupe"

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        refus = self._refus_role_application()
        if refus is not None:
            return refus
        return self.render_to_response(self.get_context_data())

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        refus = self._refus_role_application()
        if refus is not None:
            return refus
        return super().post(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Supprimer le groupe"
        context["message"] = f"Confirmez la suppression du groupe {self.object.name}."
        context["cancel_url"] = reverse("accounts:group_detail", args=[self.object.pk])
        return context

    def form_valid(self, form):
        nom = self.object.name
        object_id = str(self.object.pk)
        response = super().form_valid(form)
        journaliser(
            request=self.request,
            action="SUPPRESSION",
            model_name="Group",
            object_id=object_id,
            old_values={"nom": nom},
        )
        messages.success(self.request, "✓ Groupe supprimé.")
        return response

    def _refus_role_application(self):
        if self.object.name not in GROUP_NAMES:
            return None
        messages.error(self.request, "Ce rôle fait partie de l'application et ne peut pas être supprimé.")
        return redirect("accounts:group_detail", pk=self.object.pk)


class GroupDetailView(AppPermissionMixin, DetailView):
    permission_required = "accounts.manage_users"
    model = Group
    template_name = "accounts/group_detail.html"
    context_object_name = "groupe"

    def get_queryset(self):
        return Group.objects.prefetch_related("permissions__content_type", "user_set")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["protege"] = self.object.name in GROUP_NAMES
        return context
