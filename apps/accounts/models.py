from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    """Lien entre un compte Django, un agent et le périmètre d'un responsable."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name="utilisateur",
        on_delete=models.CASCADE,
        related_name="profile",
    )
    agent = models.OneToOneField(
        "agents.Agent",
        verbose_name="agent",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="user_profile",
    )
    service = models.ForeignKey(
        "services.Service",
        verbose_name="service de responsabilité",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="responsables",
        help_text="Périmètre de validation d'un chef de service, y compris les sous-services.",
    )
    created_at = models.DateTimeField("créé le", auto_now_add=True)
    updated_at = models.DateTimeField("modifié le", auto_now=True)

    class Meta:
        verbose_name = "profil utilisateur"
        verbose_name_plural = "profils utilisateurs"
        permissions = [
            ("manage_users", "Peut gérer les utilisateurs"),
        ]

    def __str__(self):
        return f"Profil de {self.user.get_username()}"
