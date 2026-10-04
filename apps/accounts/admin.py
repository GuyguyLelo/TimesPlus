from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import User

from apps.accounts.models import UserProfile
from apps.audit.admin_mixins import AuditAdminMixin

admin.site.unregister(User)


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    autocomplete_fields = ("agent", "service")
    extra = 0


@admin.register(User)
class UserAdmin(AuditAdminMixin, DjangoUserAdmin):
    inlines = [UserProfileInline]
    list_display = ("username", "email", "first_name", "last_name", "is_staff", "is_active")
    list_filter = ("is_staff", "is_active", "groups")
    search_fields = ("username", "first_name", "last_name", "email")
    list_per_page = 20


@admin.register(UserProfile)
class UserProfileAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("user", "agent", "service")
    search_fields = ("user__username", "agent__matricule", "agent__nom")
    autocomplete_fields = ("user", "agent", "service")
    list_select_related = ("user", "agent", "service")
    list_per_page = 20
