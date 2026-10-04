from django.contrib import admin

from apps.reports.models import GeneratedReport, ReportSequence


@admin.register(GeneratedReport)
class GeneratedReportAdmin(admin.ModelAdmin):
    list_display = ("numero", "type_rapport", "format", "periode_debut", "periode_fin", "genere_par", "genere_le")
    list_filter = ("type_rapport", "format")
    search_fields = ("numero", "genere_par__username")
    date_hierarchy = "genere_le"
    list_select_related = ("genere_par",)
    readonly_fields = ("numero", "type_rapport", "format", "periode_debut", "periode_fin", "filtres", "genere_par", "genere_le")
    list_per_page = 20

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ReportSequence)
class ReportSequenceAdmin(admin.ModelAdmin):
    list_display = ("annee", "dernier")
    list_per_page = 20
