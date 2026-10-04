import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


def attachment_upload_to(instance, filename):
    extension = Path(filename).suffix.lower()
    return f"attachments/{instance.demande_id}/{uuid.uuid4().hex}{extension}"


class WorkSchedule(models.Model):
    """Horaire administratif de référence. Il ne fixe aucun taux de rémunération."""

    class Jour(models.IntegerChoices):
        LUNDI = 0, "Lundi"
        MARDI = 1, "Mardi"
        MERCREDI = 2, "Mercredi"
        JEUDI = 3, "Jeudi"
        VENDREDI = 4, "Vendredi"
        SAMEDI = 5, "Samedi"
        DIMANCHE = 6, "Dimanche"

    nom = models.CharField("nom", max_length=100)
    service = models.ForeignKey(
        "services.Service",
        verbose_name="service",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="horaires",
        help_text="Laisser vide pour un horaire commun à toute l'administration.",
    )
    jour_semaine = models.PositiveSmallIntegerField("jour", choices=Jour.choices)
    heure_debut = models.TimeField("heure de début")
    heure_fin = models.TimeField("heure de fin")
    pause_debut = models.TimeField("début de pause", null=True, blank=True)
    pause_fin = models.TimeField("fin de pause", null=True, blank=True)
    actif = models.BooleanField("actif", default=True)

    class Meta:
        verbose_name = "horaire"
        verbose_name_plural = "horaires"
        ordering = ["jour_semaine", "heure_debut"]
        indexes = [models.Index(fields=["jour_semaine", "actif"])]

    def __str__(self):
        return f"{self.nom} — {self.get_jour_semaine_display()} {self.heure_debut:%H:%M}-{self.heure_fin:%H:%M}"

    @staticmethod
    def _sur_axe(heure):
        """Position de 0 à 100 entre 06:00 et 20:00."""
        minutes = heure.hour * 60 + heure.minute
        ratio = (minutes - 6 * 60) / (14 * 60)
        return max(0.0, min(100.0, ratio * 100))

    @property
    def barre(self):
        """Placement de la plage de travail et de la pause sur l'axe 06:00–20:00."""
        debut = self._sur_axe(self.heure_debut)
        largeur = max(self._sur_axe(self.heure_fin) - debut, 0)
        pause = pause_largeur = None
        if self.pause_debut and self.pause_fin and largeur:
            pause = (self._sur_axe(self.pause_debut) - debut) / largeur * 100
            pause_largeur = (self._sur_axe(self.pause_fin) - self._sur_axe(self.pause_debut)) / largeur * 100
        return {
            "debut": f"{debut:.1f}",
            "largeur": f"{largeur:.1f}",
            "pause": None if pause is None else f"{max(pause, 0):.1f}",
            "pause_largeur": None if pause_largeur is None else f"{max(pause_largeur, 0):.1f}",
        }

    def clean(self):
        if self.heure_debut and self.heure_fin and self.heure_fin <= self.heure_debut:
            raise ValidationError("L'heure de fin doit être postérieure à l'heure de début.")
        if bool(self.pause_debut) != bool(self.pause_fin):
            raise ValidationError("La pause doit avoir une heure de début et une heure de fin.")
        if self.pause_debut and self.pause_fin and self.pause_fin <= self.pause_debut:
            raise ValidationError("La fin de pause doit être postérieure au début de pause.")


class Holiday(models.Model):
    """Jour férié saisi par l'administration. Aucune liste n'est figée dans le code."""

    class Type(models.TextChoices):
        NATIONAL = "NATIONAL", "National"
        OFFICIEL = "OFFICIEL", "Officiel"
        LOCAL = "LOCAL", "Local"
        EXCEPTIONNEL = "EXCEPTIONNEL", "Exceptionnel"

    date = models.DateField("date", unique=True)
    libelle = models.CharField("libellé", max_length=200)
    type = models.CharField("type", max_length=20, choices=Type.choices, default=Type.NATIONAL)
    actif = models.BooleanField("actif", default=True)

    class Meta:
        verbose_name = "jour férié"
        verbose_name_plural = "jours fériés"
        ordering = ["date"]
        indexes = [models.Index(fields=["date", "actif"])]

    def __str__(self):
        return f"{self.date:%d/%m/%Y} — {self.libelle}"


class OvertimeType(models.Model):
    """Catégorie d'heure supplémentaire. Le coefficient est modifiable."""

    code = models.CharField("code", max_length=32, unique=True)
    libelle = models.CharField("libellé", max_length=150)
    coefficient = models.DecimalField(
        "coefficient par défaut",
        max_digits=6,
        decimal_places=3,
        default=1,
        help_text="Valeur de référence. Le calcul applique le coefficient de la règle retenue.",
    )
    description = models.TextField("description", blank=True)
    actif = models.BooleanField("actif", default=True)

    class Meta:
        verbose_name = "type d'heure"
        verbose_name_plural = "types d'heures"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} — {self.libelle}"


class OvertimeRule(models.Model):
    """Règle de classification et de coefficient, entièrement paramétrable."""

    nom = models.CharField("nom", max_length=150)
    type_heure = models.ForeignKey(
        OvertimeType,
        verbose_name="type d'heure",
        on_delete=models.PROTECT,
        related_name="regles",
    )
    priorite = models.PositiveIntegerField(
        "priorité",
        default=100,
        help_text="La plus petite valeur est examinée en premier.",
    )
    heure_debut = models.TimeField(
        "heure de début",
        null=True,
        blank=True,
        help_text="Laisser vide, avec l'heure de fin, pour couvrir toute la journée.",
    )
    heure_fin = models.TimeField("heure de fin", null=True, blank=True)
    applicable_weekend = models.BooleanField("applicable le week-end", default=False)
    applicable_ferie = models.BooleanField("applicable un jour férié", default=False)
    plafond_journalier = models.PositiveIntegerField(
        "plafond journalier (minutes)",
        null=True,
        blank=True,
    )
    plafond_mensuel = models.PositiveIntegerField(
        "plafond mensuel (minutes)",
        null=True,
        blank=True,
    )
    coefficient = models.DecimalField("coefficient", max_digits=6, decimal_places=3, default=1)
    actif = models.BooleanField("actif", default=True)
    date_debut_validite = models.DateField("début de validité", null=True, blank=True)
    date_fin_validite = models.DateField("fin de validité", null=True, blank=True)

    class Meta:
        verbose_name = "règle de calcul"
        verbose_name_plural = "règles de calcul"
        ordering = ["priorite", "nom"]
        permissions = [
            ("manage_rules", "Peut gérer les règles de calcul"),
        ]
        indexes = [
            models.Index(fields=["actif", "priorite"]),
        ]

    def __str__(self):
        return self.nom

    def clean(self):
        if (self.heure_debut is None) != (self.heure_fin is None):
            raise ValidationError(
                "L'heure de début et l'heure de fin de la plage doivent être renseignées ensemble."
            )
        if (
            self.date_debut_validite
            and self.date_fin_validite
            and self.date_fin_validite < self.date_debut_validite
        ):
            raise ValidationError("La fin de validité doit être postérieure au début.")


class OvertimeRequest(models.Model):
    """Déclaration d'heures supplémentaires."""

    class Statut(models.TextChoices):
        BROUILLON = "BROUILLON", "Brouillon"
        SOUMIS = "SOUMIS", "Soumis"
        EN_VALIDATION = "EN_VALIDATION", "En validation"
        APPROUVE = "APPROUVE", "Approuvé"
        REJETE = "REJETE", "Rejeté"
        ANNULE = "ANNULE", "Annulé"

    agent = models.ForeignKey(
        "agents.Agent",
        verbose_name="agent",
        on_delete=models.PROTECT,
        related_name="declarations",
    )
    date_travail = models.DateField("date de travail")
    heure_debut = models.TimeField("heure de début")
    heure_fin = models.TimeField("heure de fin")
    duree_minutes = models.PositiveIntegerField("durée (minutes)")
    type_heure = models.ForeignKey(
        OvertimeType,
        verbose_name="type d'heure",
        on_delete=models.PROTECT,
        related_name="declarations",
    )
    regle_appliquee = models.ForeignKey(
        OvertimeRule,
        verbose_name="règle appliquée",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="declarations",
    )
    coefficient_applique = models.DecimalField(
        "coefficient appliqué",
        max_digits=6,
        decimal_places=3,
        default=1,
    )
    ventilation = models.JSONField(
        "ventilation",
        default=list,
        blank=True,
        help_text="Détail des segments et de la règle utilisée au moment du calcul.",
    )
    motif = models.CharField("motif", max_length=120)
    observation = models.TextField("observation", blank=True, default="")
    activite = models.TextField("activité réalisée", blank=True, default="")
    liste = models.ForeignKey(
        "ListeJournaliere",
        verbose_name="liste du jour",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="lignes",
    )
    montant_estime = models.DecimalField(
        "montant estimé",
        max_digits=14,
        decimal_places=2,
        default=0,
    )
    statut = models.CharField(
        "statut",
        max_length=20,
        choices=Statut.choices,
        default=Statut.APPROUVE,
    )
    current_step = models.ForeignKey(
        "workflow.WorkflowStep",
        verbose_name="étape en cours",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="demandes",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="créé par",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="declarations_creees",
    )
    created_at = models.DateTimeField("créé le", auto_now_add=True)
    updated_at = models.DateTimeField("modifié le", auto_now=True)
    submitted_at = models.DateTimeField("soumis le", null=True, blank=True)
    approved_at = models.DateTimeField("approuvé le", null=True, blank=True)

    class Meta:
        verbose_name = "déclaration d'heures supplémentaires"
        verbose_name_plural = "déclarations d'heures supplémentaires"
        ordering = ["-date_travail", "-heure_debut"]
        permissions = [
            ("view_overtime", "Peut consulter les heures supplémentaires"),
            ("add_overtime", "Peut créer une déclaration"),
            ("change_overtime", "Peut modifier une déclaration"),
            ("delete_overtime", "Peut supprimer une déclaration"),
            ("submit_overtime", "Peut soumettre une déclaration"),
            ("approve_overtime", "Peut approuver une déclaration"),
            ("reject_overtime", "Peut rejeter une déclaration"),
            ("view_all_overtime", "Peut consulter toutes les déclarations"),
            ("validate_all_overtime", "Peut valider hors de son service"),
        ]
        indexes = [
            models.Index(fields=["agent", "date_travail"]),
            models.Index(fields=["statut"]),
            models.Index(fields=["date_travail"]),
            models.Index(fields=["type_heure"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(duree_minutes__gt=0),
                name="overtime_duree_positive",
            ),
        ]

    def __str__(self):
        return f"{self.agent.matricule} — {self.date_travail:%d/%m/%Y} ({self.get_statut_display()})"

    @property
    def motif_libelle(self):
        from apps.overtime.motifs import libelle_motif

        return libelle_motif(self.motif)

    @property
    def editable(self):
        return self.statut != self.Statut.ANNULE

    @property
    def supprimable(self):
        return self.statut != self.Statut.ANNULE

    @property
    def soumissible(self):
        return False


class Attachment(models.Model):
    """Pièce jointe contrôlée (extension, type MIME, taille, nom)."""

    class TypeDocument(models.TextChoices):
        ORDRE_SERVICE = "ORDRE_SERVICE", "Ordre de service"
        NOTE = "NOTE", "Note"
        AUTORISATION = "AUTORISATION", "Autorisation"
        JUSTIFICATIF = "JUSTIFICATIF", "Justificatif"
        AUTRE = "AUTRE", "Autre document"

    demande = models.ForeignKey(
        OvertimeRequest,
        verbose_name="déclaration",
        on_delete=models.CASCADE,
        related_name="pieces",
    )
    type_document = models.CharField(
        "type de document",
        max_length=20,
        choices=TypeDocument.choices,
        default=TypeDocument.JUSTIFICATIF,
    )
    fichier = models.FileField("fichier", upload_to=attachment_upload_to)
    nom_original = models.CharField("nom du fichier", max_length=150)
    taille = models.PositiveIntegerField("taille (octets)")
    content_type = models.CharField("type MIME", max_length=120, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="déposé par",
        null=True,
        on_delete=models.SET_NULL,
        related_name="pieces_deposees",
    )
    uploaded_at = models.DateTimeField("déposé le", auto_now_add=True)

    class Meta:
        verbose_name = "pièce jointe"
        verbose_name_plural = "pièces jointes"
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.nom_original


class ListeJournaliere(models.Model):
    """Liste des heures supplémentaires d'un service pour une journée."""

    date = models.DateField("date")
    service = models.ForeignKey(
        "services.Service",
        verbose_name="service",
        on_delete=models.PROTECT,
        related_name="listes_heures",
    )
    created_at = models.DateTimeField("créée le", auto_now_add=True)

    class Meta:
        verbose_name = "liste journalière"
        verbose_name_plural = "listes journalières"
        ordering = ["-date", "service__code"]
        constraints = [
            models.UniqueConstraint(fields=["date", "service"], name="liste_jour_service"),
        ]

    def __str__(self):
        return f"{self.service.code} — {self.date:%d/%m/%Y}"


class SignatureListe(models.Model):
    """Signature d'un agent ou d'un cadre sur la liste du jour."""

    class Qualite(models.TextChoices):
        AGENT = "AGENT", "Agent"
        CADRE = "CADRE", "Cadre"

    liste = models.ForeignKey(
        ListeJournaliere,
        verbose_name="liste",
        on_delete=models.CASCADE,
        related_name="signatures",
    )
    agent = models.ForeignKey(
        "agents.Agent",
        verbose_name="signataire",
        on_delete=models.PROTECT,
        related_name="signatures_listes",
    )
    qualite = models.CharField("qualité", max_length=10, choices=Qualite.choices)
    signed_at = models.DateTimeField("signé le", auto_now_add=True)

    class Meta:
        verbose_name = "signature de liste"
        verbose_name_plural = "signatures de liste"
        ordering = ["qualite", "signed_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["liste", "agent", "qualite"],
                name="signature_liste_unique",
            ),
        ]

    def __str__(self):
        return f"{self.agent} — {self.get_qualite_display()}"
