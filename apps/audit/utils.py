"""Journal d'audit : sérialisation sûre et écriture des événements."""

from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

from django.db import models


EXCLUDED_FIELDS = {"password"}


def get_client_ip(request):
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()[:45] or None
    return request.META.get("REMOTE_ADDR") or None


def _jsonable(value):
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    return value


def model_snapshot(instance):
    """Dictionnaire JSON-compatible, sans mot de passe."""
    data = {}
    for field in instance._meta.concrete_fields:
        if field.name in EXCLUDED_FIELDS:
            continue
        if isinstance(field, models.FileField):
            file_value = getattr(instance, field.name)
            data[field.name] = file_value.name if file_value else ""
            continue
        data[field.name] = _jsonable(getattr(instance, field.attname))
    return data


def journaliser(
    *,
    action,
    request=None,
    user=None,
    instance=None,
    model_name="",
    object_id="",
    old_values=None,
    new_values=None,
):
    from apps.audit.models import AuditLog

    if instance is not None:
        model_name = model_name or instance.__class__.__name__
        object_id = object_id or str(instance.pk or "")
    if user is None and request is not None and getattr(request.user, "is_authenticated", False):
        user = request.user
    if user is not None and not getattr(user, "is_authenticated", False):
        user = None
    ip_address = get_client_ip(request)
    user_agent = ""
    if request is not None:
        user_agent = request.META.get("HTTP_USER_AGENT", "")[:500]
    return AuditLog.objects.create(
        user=user,
        action=action,
        model_name=model_name[:100],
        object_id=str(object_id)[:64],
        old_values=old_values or {},
        new_values=new_values or {},
        ip_address=ip_address,
        user_agent=user_agent,
    )
