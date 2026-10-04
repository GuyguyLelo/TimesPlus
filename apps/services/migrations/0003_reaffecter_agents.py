from django.db import migrations


def reaffecter(apps, schema_editor):
    from apps.services.dgtcp import reaffecter_agents

    reaffecter_agents()


class Migration(migrations.Migration):

    dependencies = [
        ("services", "0002_service_niveau_dgtcp"),
    ]

    operations = [
        migrations.RunPython(reaffecter, migrations.RunPython.noop),
    ]
