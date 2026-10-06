from pathlib import Path
from uuid import uuid4

from django.db import models


def agent_photo_path(instance, filename):
    extension = Path(filename).suffix.lower()
    if extension not in {".jpg", ".jpeg", ".png", ".webp"}:
        extension = ".jpg"
    return f"agents/photos/{uuid4().hex}{extension}"


class Grade(models.Model):
    """Grade de la loi n° 16/013 du 15 juillet 2016, articles 17 et 18."""

    class Categorie(models.TextChoices):
        A = "A", "Catégorie A — hauts fonctionnaires"
        B = "B", "Catégorie B — cadres supérieurs"
        C = "C", "Catégorie C — agents de collaboration"
        D = "D", "Catégorie D — agents d'exécution"

    code = models.CharField("code", max_length=16, unique=True)
    abreviation = models.CharField(
        "abréviation",
        max_length=16,
        blank=True,
        help_text="Code court utilisé dans les listes du personnel, par exemple DIR, CD ou ATA1.",
    )
    libelle = models.CharField("libellé", max_length=120)
    categorie = models.CharField("catégorie", max_length=1, choices=Categorie.choices)
    echelon = models.PositiveSmallIntegerField("échelon", null=True, blank=True)
    ordre = models.PositiveSmallIntegerField("ordre", default=0)
    actif = models.BooleanField("actif", default=True)

    class Meta:
        verbose_name = "grade"
        verbose_name_plural = "grades"
        ordering = ["ordre", "libelle"]

    def __str__(self):
        if self.echelon:
            return f"{self.libelle}, échelon {self.echelon}"
        return self.libelle


class Fonction(models.Model):
    """Emploi ou fonction de l'administration publique centrale."""

    class Famille(models.TextChoices):
        COMMANDEMENT = "COMMANDEMENT", "Commandement"
        STRUCTURE = "STRUCTURE", "Structures standards"
        EMPLOI = "EMPLOI", "Emplois"

    code = models.CharField("code", max_length=32, unique=True)
    libelle = models.CharField("libellé", max_length=180)
    famille = models.CharField("famille", max_length=20, choices=Famille.choices)
    ordre = models.PositiveSmallIntegerField("ordre", default=0)
    actif = models.BooleanField("actif", default=True)

    class Meta:
        verbose_name = "fonction"
        verbose_name_plural = "fonctions"
        ordering = ["ordre", "libelle"]

    def __str__(self):
        return self.libelle


class Bareme(models.Model):
    """Taux horaire d'un couple grade et fonction.

    Le montant est paramétré par l'administration. Il ne reprend pas un barème légal figé.
    """

    grade = models.ForeignKey(
        Grade,
        verbose_name="grade",
        on_delete=models.PROTECT,
        related_name="baremes",
    )
    fonction = models.ForeignKey(
        Fonction,
        verbose_name="fonction",
        on_delete=models.PROTECT,
        related_name="baremes",
    )
    taux_horaire = models.DecimalField(
        "taux horaire",
        max_digits=12,
        decimal_places=2,
        help_text="Montant horaire appliqué aux agents de ce grade et de cette fonction.",
    )
    actif = models.BooleanField("actif", default=True)

    class Meta:
        verbose_name = "barème"
        verbose_name_plural = "barèmes"
        ordering = ["grade__ordre", "fonction__ordre"]
        constraints = [
            models.UniqueConstraint(fields=["grade", "fonction"], name="bareme_grade_fonction"),
        ]

    def __str__(self):
        return f"{self.grade} — {self.fonction}"


def taux_horaire_bareme(agent):
    """Taux horaire actif du grade et de la fonction, ou None."""
    grade_id = getattr(agent, "grade_id", None)
    fonction_id = getattr(agent, "fonction_id", None)
    if not grade_id or not fonction_id:
        return None
    return (
        Bareme.objects.filter(grade_id=grade_id, fonction_id=fonction_id, actif=True)
        .values_list("taux_horaire", flat=True)
        .first()
    )


class Agent(models.Model):
    """Agent de l'administration. Son taux horaire vient du barème grade et fonction."""

    class Sexe(models.TextChoices):
        MASCULIN = "M", "Masculin"
        FEMININ = "F", "Féminin"

    class Statut(models.TextChoices):
        ACTIF = "ACTIF", "Actif"
        SUSPENDU = "SUSPENDU", "Suspendu"
        RETRAITE = "RETRAITE", "Retraité"
        SORTI = "SORTI", "Sorti"

    photo = models.ImageField(
        "photo",
        upload_to=agent_photo_path,
        blank=True,
        help_text="JPEG, PNG ou WebP. Taille maximale : 2 Mo.",
    )
    matricule = models.CharField("matricule", max_length=32, unique=True)
    nom = models.CharField("nom", max_length=100)
    postnom = models.CharField("postnom", max_length=100, blank=True)
    prenom = models.CharField("prénom", max_length=100)
    sexe = models.CharField("sexe", max_length=1, choices=Sexe.choices)
    date_naissance = models.DateField("date de naissance", null=True, blank=True)
    email = models.EmailField("e-mail", blank=True)
    telephone = models.CharField("téléphone", max_length=32, blank=True)
    grade = models.ForeignKey(
        Grade,
        verbose_name="grade",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="agents",
    )
    fonction = models.ForeignKey(
        Fonction,
        verbose_name="fonction",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="agents",
    )
    service = models.ForeignKey(
        "services.Service",
        verbose_name="service",
        on_delete=models.PROTECT,
        related_name="agents",
    )
    date_engagement = models.DateField("date d'engagement", null=True, blank=True)
    statut = models.CharField(
        "statut",
        max_length=20,
        choices=Statut.choices,
        default=Statut.ACTIF,
    )
    ordre = models.PositiveIntegerField(
        "ordre dans la liste",
        null=True,
        blank=True,
        help_text="Place dans la liste déclarative. Vide : le nom sert de tri.",
    )
    actif = models.BooleanField("actif", default=True)
    created_at = models.DateTimeField("créé le", auto_now_add=True)
    updated_at = models.DateTimeField("modifié le", auto_now=True)

    class Meta:
        verbose_name = "agent"
        verbose_name_plural = "agents"
        ordering = ["nom", "postnom", "prenom"]
        indexes = [
            models.Index(fields=["nom", "prenom"]),
            models.Index(fields=["actif"]),
            models.Index(fields=["service"]),
            models.Index(fields=["statut"]),
        ]

    def __str__(self):
        return f"{self.matricule} — {self.nom_complet}"

    def delete(self, *args, **kwargs):
        photo_name = self.photo.name if self.photo else ""
        storage = self.photo.storage
        result = super().delete(*args, **kwargs)
        if photo_name:
            storage.delete(photo_name)
        return result

    @property
    def nom_complet(self):
        return " ".join(part for part in (self.nom, self.postnom, self.prenom) if part)

    @property
    def initiales(self):
        letters = "".join(part[0] for part in (self.prenom, self.nom) if part)
        return letters.upper()[:2] or "AG"

    @property
    def taux_applique(self):
        return taux_horaire_bareme(self)
