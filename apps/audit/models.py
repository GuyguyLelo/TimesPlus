from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    """Journal d'audit. Non supprimable depuis les interfaces applicatives."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="utilisateur",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
    )
    action = models.CharField("action", max_length=50)
    model_name = models.CharField("modèle", max_length=100, blank=True)
    object_id = models.CharField("identifiant objet", max_length=64, blank=True)
    old_values = models.JSONField("anciennes valeurs", default=dict, blank=True)
    new_values = models.JSONField("nouvelles valeurs", default=dict, blank=True)
    ip_address = models.GenericIPAddressField("adresse IP", null=True, blank=True)
    user_agent = models.CharField("agent utilisateur", max_length=500, blank=True)
    created_at = models.DateTimeField("date", auto_now_add=True)

    class Meta:
        verbose_name = "journal d'audit"
        verbose_name_plural = "journaux d'audit"
        ordering = ["-created_at"]
        default_permissions = ("add", "view")
        permissions = [
            ("view_audit", "Peut consulter le journal d'audit"),
        ]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["action"]),
            models.Index(fields=["model_name"]),
            models.Index(fields=["user"]),
        ]

    def __str__(self):
        who = self.user.get_username() if self.user_id else "système"
        return f"{self.created_at:%Y-%m-%d %H:%M} — {who} — {self.action}"
