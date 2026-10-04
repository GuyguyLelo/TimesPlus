from django.contrib import admin

from apps.audit.admin_mixins import AuditAdminMixin
from apps.workflow.models import RequestEvent, ValidationDecision, WorkflowDefinition, WorkflowStep


class WorkflowStepInline(admin.TabularInline):
    model = WorkflowStep
    extra = 0
    filter_horizontal = ("groupes",)


@admin.register(WorkflowDefinition)
class WorkflowDefinitionAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("nom", "code", "actif")
    list_filter = ("actif",)
    search_fields = ("nom", "code")
    inlines = [WorkflowStepInline]
    list_per_page = 20


@admin.register(WorkflowStep)
class WorkflowStepAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("workflow", "ordre", "code", "libelle", "limiter_au_service")
    list_filter = ("workflow", "limiter_au_service")
    search_fields = ("code", "libelle")
    filter_horizontal = ("groupes",)
    list_per_page = 20


@admin.register(ValidationDecision)
class ValidationDecisionAdmin(admin.ModelAdmin):
    list_display = ("demande", "etape", "utilisateur", "decision", "ip_address", "created_at")
    list_filter = ("decision", "created_at")
    search_fields = ("demande__agent__matricule", "utilisateur__username", "commentaire")
    date_hierarchy = "created_at"
    list_select_related = ("demande", "etape", "utilisateur")
    readonly_fields = ("demande", "etape", "utilisateur", "decision", "commentaire", "ip_address", "created_at")
    list_per_page = 20

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(RequestEvent)
class RequestEventAdmin(admin.ModelAdmin):
    list_display = ("demande", "action", "utilisateur", "ancien_statut", "nouveau_statut", "created_at")
    list_filter = ("action", "nouveau_statut")
    search_fields = ("demande__agent__matricule", "action", "commentaire")
    list_select_related = ("demande", "utilisateur")
    readonly_fields = (
        "demande",
        "utilisateur",
        "action",
        "commentaire",
        "ancien_statut",
        "nouveau_statut",
        "ip_address",
        "created_at",
    )
    list_per_page = 20

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
