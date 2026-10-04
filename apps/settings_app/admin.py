from django.contrib import admin

from apps.audit.admin_mixins import AuditAdminMixin
from apps.settings_app.models import SiteSettings


@admin.register(SiteSettings)
class SiteSettingsAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("nom_administration", "sigle", "devise", "updated_at")

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
