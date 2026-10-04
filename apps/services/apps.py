from django.apps import AppConfig
from django.db.models.signals import post_migrate


class ServicesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.services"
    verbose_name = "Services"

    def ready(self):
        from apps.services.dgtcp import ensure_dgtcp

        post_migrate.connect(ensure_dgtcp, sender=self, dispatch_uid="services_dgtcp")
