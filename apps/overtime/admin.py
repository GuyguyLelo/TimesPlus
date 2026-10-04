from django.contrib import admin

from apps.audit.admin_mixins import AuditAdminMixin
from apps.overtime.formatting import format_montant
from apps.overtime.models import (
    Attachment,
    Holiday,
    OvertimeRequest,
    OvertimeRule,
    OvertimeType,
    PaiementMois,
    WorkSchedule,
)


@admin.register(WorkSchedule)
class WorkScheduleAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("nom", "service", "jour_semaine", "heure_debut", "heure_fin", "actif")
    list_filter = ("actif", "jour_semaine", "service")
    search_fields = ("nom",)
    list_per_page = 20


@admin.register(Holiday)
class HolidayAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("date", "libelle", "type", "actif")
    list_filter = ("actif", "type")
    search_fields = ("libelle",)
    date_hierarchy = "date"
    list_per_page = 20


@admin.register(OvertimeType)
class OvertimeTypeAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("code", "libelle", "coefficient", "actif")
    list_filter = ("actif",)
    search_fields = ("code", "libelle")
    list_per_page = 20


@admin.register(OvertimeRule)
class OvertimeRuleAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = (
        "nom",
        "type_heure",
        "priorite",
        "coefficient",
        "applicable_weekend",
        "applicable_ferie",
        "actif",
    )
    list_filter = ("actif", "applicable_weekend", "applicable_ferie", "type_heure")
    search_fields = ("nom", "type_heure__code")
    list_select_related = ("type_heure",)
    list_per_page = 20


class AttachmentInline(admin.TabularInline):
    model = Attachment
    extra = 0
    readonly_fields = ("nom_original", "taille", "content_type", "uploaded_by", "uploaded_at")


@admin.register(OvertimeRequest)
class OvertimeRequestAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = (
        "agent",
        "date_travail",
        "heure_debut",
        "heure_fin",
        "duree_minutes",
        "type_heure",
        "statut",
        "montant",
    )
    list_filter = ("statut", "type_heure", "date_travail", "agent__service")
    search_fields = ("agent__matricule", "agent__nom", "agent__prenom", "motif", "observation")
    date_hierarchy = "date_travail"
    list_select_related = ("agent", "agent__service", "type_heure")
    autocomplete_fields = ("agent", "type_heure", "regle_appliquee", "created_by")
    readonly_fields = ("created_at", "updated_at", "submitted_at", "approved_at", "ventilation")
    inlines = [AttachmentInline]
    list_per_page = 20

    @admin.display(description="montant estimé", ordering="montant_estime")
    def montant(self, obj):
        return format_montant(obj.montant_estime)

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj and obj.statut == OvertimeRequest.Statut.APPROUVE:
            return [field.name for field in obj._meta.fields]
        return fields


@admin.register(PaiementMois)
class PaiementMoisAdmin(admin.ModelAdmin):
    list_display = ("annee", "mois", "agents", "nombre", "minutes", "montant", "cloture_le", "cloture_par")
    list_filter = ("annee",)
    ordering = ("-annee", "-mois")
    list_per_page = 20

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Attachment)
class AttachmentAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("nom_original", "demande", "type_document", "taille", "uploaded_at")
    list_filter = ("type_document",)
    search_fields = ("nom_original", "demande__agent__matricule")
    list_select_related = ("demande", "demande__agent")
    list_per_page = 20
