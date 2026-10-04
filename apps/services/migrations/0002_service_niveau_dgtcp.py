from django.db import migrations, models


def charger_dgtcp(apps, schema_editor):
    from apps.services.dgtcp import rattacher_anciens_services

    rattacher_anciens_services()


class Migration(migrations.Migration):

    dependencies = [
        ("services", "0001_initial"),
        ("agents", "0003_grades_fonctions"),
        ("accounts", "0001_initial"),
        ("overtime", "0002_initial"),
        ("settings_app", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="service",
            name="niveau",
            field=models.CharField(
                choices=[
                    ("DG", "Direction générale"),
                    ("SECRETARIAT", "Secrétariat"),
                    ("DIRECTION", "Direction"),
                    ("DIVISION", "Division"),
                    ("BUREAU", "Bureau"),
                    ("POSTE", "Poste comptable"),
                ],
                default="DIRECTION",
                max_length=20,
                verbose_name="niveau",
            ),
        ),
        migrations.RunPython(charger_dgtcp, migrations.RunPython.noop),
    ]
