from django.contrib import admin

from apps.agents.models import Agent, Fonction, Grade
from apps.audit.admin_mixins import AuditAdminMixin


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ("ordre", "code", "libelle", "categorie", "echelon", "actif")
    list_filter = ("categorie", "actif")
    search_fields = ("code", "libelle")
    ordering = ("ordre",)


@admin.register(Fonction)
class FonctionAdmin(admin.ModelAdmin):
    list_display = ("ordre", "code", "libelle", "famille", "actif")
    list_filter = ("famille", "actif")
    search_fields = ("code", "libelle")
    ordering = ("ordre",)


@admin.register(Agent)
class AgentAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("matricule", "nom", "postnom", "prenom", "service", "grade", "statut", "actif")
    readonly_fields = ("created_at", "updated_at")
    list_filter = ("actif", "statut", "sexe", "service")
    search_fields = ("matricule", "nom", "postnom", "prenom", "email")
    autocomplete_fields = ("service",)
    list_select_related = ("service",)
    list_per_page = 20
