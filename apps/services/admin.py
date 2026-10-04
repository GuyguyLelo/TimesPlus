from django.contrib import admin

from apps.audit.admin_mixins import AuditAdminMixin
from apps.services.models import Service


@admin.register(Service)
class ServiceAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("code", "nom", "service_parent", "actif", "updated_at")
    list_filter = ("actif",)
    search_fields = ("code", "nom", "description")
    autocomplete_fields = ("service_parent",)
    list_per_page = 20
