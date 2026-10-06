from django.apps import AppConfig
from django.db.models.signals import post_migrate


class AgentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.agents"
    verbose_name = "Gestion du personnel"

    def ready(self):
        from apps.agents.referentiel import ensure_referentiel

        post_migrate.connect(ensure_referentiel, sender=self, dispatch_uid="agents_referentiel")
