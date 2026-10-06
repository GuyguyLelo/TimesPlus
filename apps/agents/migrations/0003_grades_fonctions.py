from django.db import migrations, models


GRADE_MAP = {
    "secrétaire général": "SG",
    "secretaire general": "SG",
    "directeur général": "DG",
    "directeur general": "DG",
    "directeur": "DIR",
    "chef de division": "CD-1",
    "chef de bureau": "CB-1",
    "attachée": "AA2-1",
    "attachee": "AA2-1",
    "attaché": "AA2-1",
    "attache": "AA2-1",
}

FONCTION_MAP = {
    "secrétaire général": "SG",
    "directeur général": "DG",
    "directeur": "DIR",
    "directeur rh": "DRH",
    "chef de division": "CD",
    "chef de service": "CD",
    "chef de bureau": "CB",
    "comptable": "CB",
    "analyste": "AA2",
    "attachée": "AA2",
    "attachee": "AA2",
    "attaché": "AA2",
    "huissier": "HUIS",
}


def seed_and_map(apps, schema_editor):
    from apps.agents.referentiel import FONCTIONS, GRADES

    Agent = apps.get_model("agents", "Agent")
    Grade = apps.get_model("agents", "Grade")
    Fonction = apps.get_model("agents", "Fonction")
    grade_fields = {field.name for field in Grade._meta.fields}
    fonction_fields = {field.name for field in Fonction._meta.fields}
    for row in GRADES:
        Grade.objects.update_or_create(
            code=row["code"],
            defaults={key: value for key, value in row.items() if key != "code" and key in grade_fields},
        )
    for row in FONCTIONS:
        Fonction.objects.update_or_create(
            code=row["code"],
            defaults={key: value for key, value in row.items() if key != "code" and key in fonction_fields},
        )
    grades = dict(Grade.objects.values_list("code", "id"))
    fonctions = dict(Fonction.objects.values_list("code", "id"))
    for agent in Agent.objects.all():
        grade_code = GRADE_MAP.get((agent.grade_texte or "").strip().lower())
        fonction_code = FONCTION_MAP.get((agent.fonction_texte or "").strip().lower())
        agent.grade_id = grades.get(grade_code) if grade_code else None
        agent.fonction_id = fonctions.get(fonction_code) if fonction_code else None
        if agent.grade_id or agent.fonction_id:
            agent.save(update_fields=["grade", "fonction"])


class Migration(migrations.Migration):

    dependencies = [
        ("agents", "0002_agent_photo"),
    ]

    operations = [
        migrations.CreateModel(
            name="Grade",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=16, unique=True, verbose_name="code")),
                ("libelle", models.CharField(max_length=120, verbose_name="libellé")),
                ("categorie", models.CharField(choices=[("A", "Catégorie A — hauts fonctionnaires"), ("B", "Catégorie B — cadres supérieurs"), ("C", "Catégorie C — agents de collaboration"), ("D", "Catégorie D — agents d'exécution")], max_length=1, verbose_name="catégorie")),
                ("echelon", models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="échelon")),
                ("ordre", models.PositiveSmallIntegerField(default=0, verbose_name="ordre")),
                ("actif", models.BooleanField(default=True, verbose_name="actif")),
            ],
            options={"verbose_name": "grade", "verbose_name_plural": "grades", "ordering": ["ordre", "libelle"]},
        ),
        migrations.CreateModel(
            name="Fonction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=32, unique=True, verbose_name="code")),
                ("libelle", models.CharField(max_length=180, verbose_name="libellé")),
                ("famille", models.CharField(choices=[("COMMANDEMENT", "Commandement"), ("STRUCTURE", "Structures standards"), ("EMPLOI", "Emplois")], max_length=20, verbose_name="famille")),
                ("ordre", models.PositiveSmallIntegerField(default=0, verbose_name="ordre")),
                ("actif", models.BooleanField(default=True, verbose_name="actif")),
            ],
            options={"verbose_name": "fonction", "verbose_name_plural": "fonctions", "ordering": ["ordre", "libelle"]},
        ),
        migrations.RenameField(model_name="agent", old_name="grade", new_name="grade_texte"),
        migrations.RenameField(model_name="agent", old_name="fonction", new_name="fonction_texte"),
        migrations.AddField(
            model_name="agent",
            name="grade",
            field=models.ForeignKey(blank=True, null=True, on_delete=models.deletion.PROTECT, related_name="agents", to="agents.grade", verbose_name="grade"),
        ),
        migrations.AddField(
            model_name="agent",
            name="fonction",
            field=models.ForeignKey(blank=True, null=True, on_delete=models.deletion.PROTECT, related_name="agents", to="agents.fonction", verbose_name="fonction"),
        ),
        migrations.RunPython(seed_and_map, migrations.RunPython.noop),
        migrations.RemoveField(model_name="agent", name="grade_texte"),
        migrations.RemoveField(model_name="agent", name="fonction_texte"),
    ]
