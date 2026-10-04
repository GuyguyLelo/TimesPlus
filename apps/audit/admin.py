from django.contrib import admin

from apps.audit.admin_mixins import AuditAdminMixin
from apps.audit.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "action", "model_name", "object_id", "ip_address")
    list_filter = ("action", "model_name", "created_at")
    search_fields = ("action", "model_name", "object_id", "user__username", "ip_address")
    date_hierarchy = "created_at"
    list_per_page = 20
    readonly_fields = (
        "user",
        "action",
        "model_name",
        "object_id",
        "old_values",
        "new_values",
        "ip_address",
        "user_agent",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
