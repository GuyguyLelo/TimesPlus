from django.db.utils import OperationalError, ProgrammingError


def site_context(request):
    from apps.settings_app.models import SiteSettings

    try:
        site = SiteSettings.load()
    except (OperationalError, ProgrammingError):
        site = None
    return {"site_settings": site}
