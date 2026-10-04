"""Mixin d'administration : listes lisibles et journalisation."""

from apps.audit.utils import journaliser, model_snapshot


class AuditAdminMixin:
    list_per_page = 20

    def save_model(self, request, obj, form, change):
        old = None
        if change and obj.pk:
            previous = obj.__class__.objects.filter(pk=obj.pk).first()
            if previous is not None:
                old = model_snapshot(previous)
        super().save_model(request, obj, form, change)
        action = "MODIFICATION" if change else "CREATION"
        if obj.__class__.__name__ in {"OvertimeRule", "OvertimeType", "SiteSettings"} and change:
            action = "MODIFICATION_REGLE"
        journaliser(
            request=request,
            action=action,
            instance=obj,
            old_values=old,
            new_values=model_snapshot(obj),
        )

    def delete_model(self, request, obj):
        snapshot = model_snapshot(obj)
        model_name = obj.__class__.__name__
        object_id = str(obj.pk)
        super().delete_model(request, obj)
        journaliser(
            request=request,
            action="SUPPRESSION",
            model_name=model_name,
            object_id=object_id,
            old_values=snapshot,
        )
