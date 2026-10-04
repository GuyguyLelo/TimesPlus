from django.conf import settings
from django.db import models


class WorkflowDefinition(models.Model):
    """Circuit de validation. L'administration peut l'activer ou le remplacer."""

    nom = models.CharField("nom", max_length=150)
    code = models.CharField("code", max_length=50, unique=True)
    description = models.TextField("description", blank=True)
    actif = models.BooleanField("actif", default=True)

    class Meta:
        verbose_name = "circuit de validation"
        verbose_name_plural = "circuits de validation"
        ordering = ["nom"]

    def __str__(self):
        return self.nom


class WorkflowStep(models.Model):
    """Étape ordonnée d'un circuit. Les groupes autorisés sont paramétrables."""

    workflow = models.ForeignKey(
        WorkflowDefinition,
        verbose_name="circuit",
        on_delete=models.CASCADE,
        related_name="etapes",
    )
    ordre = models.PositiveIntegerField("ordre")
    code = models.CharField("code", max_length=50)
    libelle = models.CharField("libellé", max_length=150)
    limiter_au_service = models.BooleanField(
        "limiter au service de l'agent",
        default=True,
        help_text="Si coché, le valideur doit couvrir le service de l'agent, sauf permission explicite.",
    )
    groupes = models.ManyToManyField(
        "auth.Group",
        verbose_name="groupes autorisés",
        blank=True,
        related_name="etapes_workflow",
    )

    class Meta:
        verbose_name = "étape de validation"
        verbose_name_plural = "étapes de validation"
        ordering = ["workflow", "ordre"]
        constraints = [
            models.UniqueConstraint(fields=["workflow", "ordre"], name="workflow_step_ordre_unique"),
            models.UniqueConstraint(fields=["workflow", "code"], name="workflow_step_code_unique"),
        ]

    def __str__(self):
        return f"{self.workflow.nom} — {self.ordre}. {self.libelle}"


class ValidationDecision(models.Model):
    """Décision horodatée : utilisateur, motif, adresse IP."""

    class Decision(models.TextChoices):
        APPROBATION = "APPROBATION", "Approbation"
        REJET = "REJET", "Rejet"

    demande = models.ForeignKey(
        "overtime.OvertimeRequest",
        verbose_name="déclaration",
        on_delete=models.CASCADE,
        related_name="decisions",
    )
    etape = models.ForeignKey(
        WorkflowStep,
        verbose_name="étape",
        null=True,
        on_delete=models.PROTECT,
        related_name="decisions",
    )
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="utilisateur",
        null=True,
        on_delete=models.SET_NULL,
        related_name="decisions_validation",
    )
    decision = models.CharField("décision", max_length=20, choices=Decision.choices)
    commentaire = models.TextField("commentaire", blank=True)
    ip_address = models.GenericIPAddressField("adresse IP", null=True, blank=True)
    created_at = models.DateTimeField("date", auto_now_add=True)

    class Meta:
        verbose_name = "décision de validation"
        verbose_name_plural = "décisions de validation"
        ordering = ["created_at"]
        indexes = [models.Index(fields=["demande", "created_at"])]

    def __str__(self):
        return f"{self.get_decision_display()} — {self.created_at:%d/%m/%Y %H:%M}"


class RequestEvent(models.Model):
    """Historique visible d'une déclaration."""

    demande = models.ForeignKey(
        "overtime.OvertimeRequest",
        verbose_name="déclaration",
        on_delete=models.CASCADE,
        related_name="evenements",
    )
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="utilisateur",
        null=True,
        on_delete=models.SET_NULL,
        related_name="evenements_demandes",
    )
    action = models.CharField("action", max_length=50)
    commentaire = models.TextField("commentaire", blank=True)
    ancien_statut = models.CharField("ancien statut", max_length=20, blank=True)
    nouveau_statut = models.CharField("nouveau statut", max_length=20, blank=True)
    ip_address = models.GenericIPAddressField("adresse IP", null=True, blank=True)
    created_at = models.DateTimeField("date", auto_now_add=True)

    class Meta:
        verbose_name = "événement de déclaration"
        verbose_name_plural = "événements de déclaration"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.action} — {self.created_at:%d/%m/%Y %H:%M}"
