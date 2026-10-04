"""Matrice des rôles. Elle est réappliquée à chaque migration complète."""

from django.db.utils import OperationalError, ProgrammingError

GROUP_NAMES = (
    "SUPER_ADMIN",
    "ADMIN_RH",
    "CHEF_SERVICE",
    "VALIDATEUR",
    "AGENT",
    "AUDITEUR",
    "CONSULTATION",
)

_AGENT_PERMS = (
    "agents.view_agent",
    "agents.add_agent",
    "agents.change_agent",
    "agents.delete_agent",
)

_SERVICE_PERMS = (
    "services.view_service",
    "services.add_service",
    "services.change_service",
    "services.delete_service",
)

_REFERENTIEL = (
    "overtime.view_workschedule",
    "overtime.add_workschedule",
    "overtime.change_workschedule",
    "overtime.delete_workschedule",
    "overtime.view_holiday",
    "overtime.add_holiday",
    "overtime.change_holiday",
    "overtime.delete_holiday",
    "overtime.view_overtimetype",
    "overtime.add_overtimetype",
    "overtime.change_overtimetype",
    "overtime.delete_overtimetype",
    "overtime.view_overtimerule",
    "overtime.add_overtimerule",
    "overtime.change_overtimerule",
    "overtime.delete_overtimerule",
    "overtime.manage_rules",
)

_OVERTIME_CUSTOM = (
    "overtime.view_overtime",
    "overtime.add_overtime",
    "overtime.change_overtime",
    "overtime.delete_overtime",
    "overtime.submit_overtime",
    "overtime.approve_overtime",
    "overtime.reject_overtime",
    "overtime.view_all_overtime",
    "overtime.validate_all_overtime",
)

_OVERTIME_MODEL = (
    "overtime.view_overtimerequest",
    "overtime.add_overtimerequest",
    "overtime.change_overtimerequest",
    "overtime.delete_overtimerequest",
    "overtime.view_attachment",
    "overtime.add_attachment",
    "overtime.change_attachment",
    "overtime.delete_attachment",
)

_WORKFLOW = (
    "workflow.view_workflowdefinition",
    "workflow.add_workflowdefinition",
    "workflow.change_workflowdefinition",
    "workflow.delete_workflowdefinition",
    "workflow.view_workflowstep",
    "workflow.add_workflowstep",
    "workflow.change_workflowstep",
    "workflow.delete_workflowstep",
    "workflow.view_validationdecision",
    "workflow.add_validationdecision",
    "workflow.change_validationdecision",
    "workflow.delete_validationdecision",
    "workflow.view_requestevent",
    "workflow.add_requestevent",
    "workflow.change_requestevent",
    "workflow.delete_requestevent",
)

_USERS = (
    "accounts.manage_users",
    "accounts.view_userprofile",
    "accounts.add_userprofile",
    "accounts.change_userprofile",
    "accounts.delete_userprofile",
    "auth.view_user",
    "auth.add_user",
    "auth.change_user",
    "auth.delete_user",
    "auth.view_group",
    "auth.add_group",
    "auth.change_group",
    "auth.delete_group",
)

_SETTINGS = (
    "settings_app.view_sitesettings",
    "settings_app.add_sitesettings",
    "settings_app.change_sitesettings",
    "settings_app.delete_sitesettings",
)

_AUDIT = (
    "audit.view_audit",
    "audit.view_auditlog",
)

_REPORTS = (
    "reports.view_reports",
    "reports.export_reports",
    "reports.view_generatedreport",
    "reports.add_generatedreport",
    "reports.change_generatedreport",
    "reports.delete_generatedreport",
)

ADMIN_RH_PERMS = (
    _AGENT_PERMS
    + _SERVICE_PERMS
    + _REFERENTIEL
    + _OVERTIME_CUSTOM
    + _OVERTIME_MODEL
    + _WORKFLOW
    + _USERS
    + _SETTINGS
    + _AUDIT
    + _REPORTS
)

GROUP_PERMISSIONS = {
    "SUPER_ADMIN": "__all__",
    "ADMIN_RH": ADMIN_RH_PERMS,
    "CHEF_SERVICE": (
        "agents.view_agent",
        "services.view_service",
        "overtime.view_overtime",
        "overtime.approve_overtime",
        "overtime.reject_overtime",
        "overtime.view_workschedule",
        "overtime.view_holiday",
        "overtime.view_overtimerequest",
        "workflow.view_validationdecision",
        "workflow.view_requestevent",
        "reports.view_reports",
        "reports.export_reports",
    ),
    "VALIDATEUR": (
        "agents.view_agent",
        "services.view_service",
        "overtime.view_overtime",
        "overtime.approve_overtime",
        "overtime.reject_overtime",
        "overtime.view_overtimerequest",
        "workflow.view_validationdecision",
        "workflow.view_requestevent",
        "reports.view_reports",
    ),
    "AGENT": (
        "overtime.view_overtime",
        "overtime.add_overtime",
        "overtime.change_overtime",
        "overtime.delete_overtime",
        "overtime.submit_overtime",
        "overtime.view_holiday",
        "overtime.view_workschedule",
        "overtime.view_overtimerequest",
        "overtime.add_overtimerequest",
        "overtime.change_overtimerequest",
        "overtime.add_attachment",
        "overtime.view_attachment",
    ),
    "AUDITEUR": (
        "audit.view_audit",
        "audit.view_auditlog",
        "reports.view_reports",
        "overtime.view_overtime",
        "overtime.view_all_overtime",
        "overtime.view_overtimerequest",
        "agents.view_agent",
        "services.view_service",
        "workflow.view_validationdecision",
        "workflow.view_requestevent",
        "overtime.view_holiday",
        "overtime.view_workschedule",
    ),
    "CONSULTATION": (
        "agents.view_agent",
        "services.view_service",
        "overtime.view_overtime",
        "overtime.view_all_overtime",
        "overtime.view_overtimerequest",
        "overtime.view_holiday",
        "overtime.view_workschedule",
        "reports.view_reports",
        "workflow.view_validationdecision",
        "workflow.view_requestevent",
    ),
}


def _expected_codes():
    codes = []
    for value in GROUP_PERMISSIONS.values():
        if value == "__all__":
            continue
        codes.extend(value)
    return codes


def ensure_groups(sender=None, force=False, **kwargs):
    """Crée les groupes et leur associe la matrice de permissions."""
    try:
        from django.contrib.auth.models import Group, Permission
    except ImportError:
        return None
    try:
        permissions = Permission.objects.select_related("content_type")
        available = {
            f"{item.content_type.app_label}.{item.codename}": item
            for item in permissions
        }
    except (OperationalError, ProgrammingError):
        return None

    missing = [code for code in _expected_codes() if code not in available]
    if missing and not force:
        return None

    for name in GROUP_NAMES:
        group, _created = Group.objects.get_or_create(name=name)
        codes = GROUP_PERMISSIONS[name]
        if codes == "__all__":
            group.permissions.set(Permission.objects.all())
            continue
        selected = [available[code] for code in codes if code in available]
        group.permissions.set(selected)
    return True
