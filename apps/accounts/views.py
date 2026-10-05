from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import Group, User
from django.contrib.auth.views import LoginView
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import DetailView, FormView, ListView

from apps.accounts.access import get_profile
from apps.accounts.forms import UserCreateForm, UserUpdateForm
from apps.accounts.mixins import AppPermissionMixin, PageSizeMixin, page_size
from apps.audit.utils import journaliser


class AppLoginView(LoginView):
    template_name = "registration/login.html"
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if settings.DEBUG:
            context["demo_accounts"] = [
                {"username": "admin", "password": "admin123", "role": "Super administrateur"},
                {"username": "rh", "password": "Gestion-Heures-Rh-2026!", "role": "Administration RH"},
            ]
        return context


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


class GroupListView(PageSizeMixin, AppPermissionMixin, ListView):
    permission_required = "accounts.manage_users"
    template_name = "accounts/group_list.html"
    context_object_name = "groupes"
    queryset = Group.objects.prefetch_related("permissions").order_by("name")


class GroupDetailView(AppPermissionMixin, DetailView):
    permission_required = "accounts.manage_users"
    model = Group
    template_name = "accounts/group_detail.html"
    context_object_name = "groupe"

    def get_queryset(self):
        return Group.objects.prefetch_related("permissions__content_type", "user_set")
