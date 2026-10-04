from django.conf import settings
from django.db import models


class ReportSequence(models.Model):
    """Compteur annuel des numéros de rapport."""

    annee = models.PositiveIntegerField("année", unique=True)
    dernier = models.PositiveIntegerField("dernier numéro", default=0)

    class Meta:
        verbose_name = "séquence de rapport"
        verbose_name_plural = "séquences de rapport"

    def __str__(self):
        return f"{self.annee} — {self.dernier}"


class GeneratedReport(models.Model):
    """Trace de chaque rapport produit."""

    class TypeRapport(models.TextChoices):
        INDIVIDUEL = "INDIVIDUEL", "Rapport individuel"
        SERVICE = "SERVICE", "Rapport par service"
        ADMINISTRATIF = "ADMINISTRATIF", "Rapport administratif"
        MENSUEL = "MENSUEL", "Rapport mensuel"
        HISTORIQUE = "HISTORIQUE", "Rapport historique"
        EXCEL = "EXCEL", "Export Excel"

    class Format(models.TextChoices):
        PDF = "PDF", "PDF"
        XLSX = "XLSX", "Excel"

    numero = models.CharField("numéro", max_length=32, unique=True)
    type_rapport = models.CharField(
        "type",
        max_length=20,
        choices=TypeRapport.choices,
    )
    format = models.CharField("format", max_length=8, choices=Format.choices)
    periode_debut = models.DateField("début de période", null=True, blank=True)
    periode_fin = models.DateField("fin de période", null=True, blank=True)
    filtres = models.JSONField("filtres", default=dict, blank=True)
    genere_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="généré par",
        null=True,
        on_delete=models.SET_NULL,
        related_name="rapports_generes",
    )
    genere_le = models.DateTimeField("généré le", auto_now_add=True)

    class Meta:
        verbose_name = "rapport généré"
        verbose_name_plural = "rapports générés"
        ordering = ["-genere_le"]
        permissions = [
            ("view_reports", "Peut consulter les rapports"),
            ("export_reports", "Peut exporter les rapports"),
        ]
        indexes = [
            models.Index(fields=["-genere_le"]),
            models.Index(fields=["type_rapport"]),
        ]

    def __str__(self):
        return f"{self.numero} — {self.get_type_rapport_display()}"
