from django.apps import AppConfig
from django.db.models.signals import post_migrate


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    verbose_name = "Comptes et accès"

    def ready(self):
        from apps.accounts.roles import ensure_groups
        from apps.accounts.signals import register_signals

        register_signals()
        post_migrate.connect(ensure_groups, dispatch_uid="gestion_heures_ensure_groups")
