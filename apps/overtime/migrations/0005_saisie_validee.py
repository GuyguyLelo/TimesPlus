from django.db import migrations, models
from django.utils import timezone


def marquer_saisies_validees(apps, schema_editor):
    OvertimeRequest = apps.get_model("overtime", "OvertimeRequest")
    OvertimeRequest.objects.exclude(statut__in=["APPROUVE", "ANNULE"]).update(
        statut="APPROUVE",
        current_step=None,
        approved_at=timezone.now(),
    )


class Migration(migrations.Migration):

    dependencies = [
        ("overtime", "0004_observation"),
    ]

    operations = [
        migrations.AlterField(
            model_name="overtimerequest",
            name="statut",
            field=models.CharField(
                choices=[
                    ("BROUILLON", "Brouillon"),
                    ("SOUMIS", "Soumis"),
                    ("EN_VALIDATION", "En validation"),
                    ("APPROUVE", "Approuvé"),
                    ("REJETE", "Rejeté"),
                    ("ANNULE", "Annulé"),
                ],
                default="APPROUVE",
                max_length=20,
                verbose_name="statut",
            ),
        ),
        migrations.RunPython(marquer_saisies_validees, migrations.RunPython.noop),
    ]
