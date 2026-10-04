from django.core.exceptions import ValidationError
from django.db import models


class Service(models.Model):
    """Unité de la DGTCP : direction générale, direction, division ou bureau."""

    class Niveau(models.TextChoices):
        DIRECTION_GENERALE = "DG", "Direction générale"
        SECRETARIAT = "SECRETARIAT", "Secrétariat"
        DIRECTION = "DIRECTION", "Direction"
        DIVISION = "DIVISION", "Division"
        BUREAU = "BUREAU", "Bureau"
        POSTE = "POSTE", "Poste comptable"

    code = models.CharField("code", max_length=32, unique=True)
    niveau = models.CharField(
        "niveau",
        max_length=20,
        choices=Niveau.choices,
        default=Niveau.DIRECTION,
    )
    nom = models.CharField("nom", max_length=200)
    description = models.TextField("description", blank=True)
    service_parent = models.ForeignKey(
        "self",
        verbose_name="service parent",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="sous_services",
    )
    actif = models.BooleanField("actif", default=True)
    created_at = models.DateTimeField("créé le", auto_now_add=True)
    updated_at = models.DateTimeField("modifié le", auto_now=True)

    class Meta:
        verbose_name = "service"
        verbose_name_plural = "services"
        ordering = ["code"]
        indexes = [
            models.Index(fields=["nom"]),
            models.Index(fields=["actif"]),
        ]

    def __str__(self):
        return f"{self.code} — {self.nom}"

    def filiation(self):
        """Chaîne du directeur général jusqu'à cette unité."""
        chaine = []
        courant = self
        vus = set()
        while courant is not None and courant.pk not in vus:
            chaine.append(courant)
            vus.add(courant.pk)
            courant = courant.service_parent
        chaine.reverse()
        return chaine

    def hierarchie(self):
        """Direction générale, direction, division et bureau de cette unité."""
        niveaux = {
            self.Niveau.DIRECTION_GENERALE,
            self.Niveau.DIRECTION,
            self.Niveau.DIVISION,
            self.Niveau.BUREAU,
        }
        return [unite for unite in self.filiation() if unite.niveau in niveaux]

    def clean(self):
        if self.niveau == self.Niveau.DIRECTION_GENERALE and self.service_parent_id:
            raise ValidationError(
                {"service_parent": "La direction générale n'a pas de service parent."}
            )
        if self.niveau != self.Niveau.DIRECTION_GENERALE and not self.service_parent_id:
            raise ValidationError(
                {"service_parent": "Ce niveau doit être rattaché à un service parent."}
            )
        if self.service_parent_id and self.pk and self.service_parent_id == self.pk:
            raise ValidationError(
                {"service_parent": "Un service ne peut pas être son propre parent."}
            )
        allowed = {
            self.Niveau.SECRETARIAT: {self.Niveau.DIRECTION_GENERALE, self.Niveau.DIRECTION},
            self.Niveau.DIRECTION: {self.Niveau.DIRECTION_GENERALE},
            self.Niveau.DIVISION: {self.Niveau.DIRECTION},
            self.Niveau.BUREAU: {self.Niveau.DIVISION, self.Niveau.SECRETARIAT},
            self.Niveau.POSTE: {self.Niveau.DIRECTION_GENERALE},
        }
        if self.service_parent_id and self.niveau in allowed:
            if self.service_parent.niveau not in allowed[self.niveau]:
                raise ValidationError(
                    {
                        "service_parent": (
                            "Le rattachement ne respecte pas la hiérarchie : "
                            "direction générale, direction, division, bureau."
                        )
                    }
                )
        parent = self.service_parent
        seen = set()
        while parent is not None:
            if self.pk and parent.pk == self.pk or parent.pk in seen:
                raise ValidationError(
                    {"service_parent": "Cette hiérarchie crée un cycle."}
                )
            seen.add(parent.pk)
            parent = parent.service_parent
