from django.core.cache import cache
from django.db import models


class SiteSettings(models.Model):
    """Paramètres généraux. Une seule ligne (clé primaire 1) est utilisée."""

    nom_administration = models.CharField(
        "nom de l'administration",
        max_length=200,
        default="Administration publique",
    )
    sigle = models.CharField("sigle", max_length=50, default="RDC")
    devise = models.CharField(
        "devise",
        max_length=10,
        default="CDF",
        help_text="Libellé monétaire affiché. Le calcul utilise le barème du grade et de la fonction.",
    )
    adresse = models.TextField("adresse", blank=True)
    email_contact = models.EmailField("e-mail de contact", blank=True)
    jours_weekend = models.CharField(
        "jours de week-end",
        max_length=20,
        default="5,6",
        help_text="Jours ISO séparés par des virgules : 0 = lundi … 6 = dimanche.",
    )
    plafond_journalier_minutes = models.PositiveIntegerField(
        "plafond journalier (minutes)",
        null=True,
        blank=True,
        help_text="Laisser vide pour ne pas appliquer de plafond global.",
    )
    plafond_mensuel_minutes = models.PositiveIntegerField(
        "plafond mensuel (minutes)",
        null=True,
        blank=True,
        help_text="Laisser vide pour ne pas appliquer de plafond global.",
    )
    taille_max_fichier_mo = models.PositiveIntegerField(
        "taille maximale d'un fichier (Mo)",
        default=5,
    )
    elements_par_page = models.PositiveIntegerField("éléments par page", default=20)
    autoriser_date_future = models.BooleanField(
        "autoriser une date de travail future",
        default=True,
    )
    autoriser_agent_inactif = models.BooleanField(
        "autoriser une déclaration pour un agent inactif",
        default=False,
    )
    updated_at = models.DateTimeField("modifié le", auto_now=True)

    class Meta:
        verbose_name = "paramètres du site"
        verbose_name_plural = "paramètres du site"

    def __str__(self):
        return self.nom_administration

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        cache.delete("site_settings")

    def delete(self, *args, **kwargs):
        raise PermissionError("Les paramètres du site ne peuvent pas être supprimés.")

    @classmethod
    def load(cls):
        cached = cache.get("site_settings")
        if cached is not None:
            return cached
        obj, _created = cls.objects.get_or_create(pk=1)
        cache.set("site_settings", obj, 60)
        return obj

    def jours_weekend_set(self):
        days = set()
        for part in (self.jours_weekend or "").split(","):
            part = part.strip()
            if part.isdigit():
                number = int(part)
                if 0 <= number <= 6:
                    days.add(number)
        return days
