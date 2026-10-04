from django import template

from apps.overtime.formatting import format_minutes, format_montant

register = template.Library()

BADGES = {
    "BROUILLON": "secondary",
    "SOUMIS": "info",
    "EN_VALIDATION": "warning",
    "APPROUVE": "success",
    "REJETE": "danger",
    "ANNULE": "dark",
}


@register.filter
def duree(value):
    return format_minutes(value)


@register.filter
def montant(value):
    return format_montant(value)


@register.filter
def creneau(demande):
    """Position du créneau sur une barre de 16:00 à minuit."""
    debut = demande.heure_debut
    fin = demande.heure_fin
    origin = 16 * 60
    span = 8 * 60
    start = debut.hour * 60 + debut.minute
    end = fin.hour * 60 + fin.minute
    if end <= start:
        end += 24 * 60
    left = max(0, min(94, (start - origin) / span * 100))
    width = max(8, min(100 - left, (end - start) / span * 100))
    return {"left": f"{left:.1f}", "width": f"{width:.1f}"}


@register.filter
def statut_badge(value):
    return BADGES.get(value, "secondary")


@register.simple_tag(takes_context=True)
def nav_class(context, prefix, *excludes):
    """Classe du lien de menu, active si l'URL courante correspond au préfixe."""
    path = context["request"].path
    for item in excludes:
        if path == item or path.startswith(item):
            return "nav-link"
    if path == prefix or path.startswith(prefix):
        return "nav-link is-active"
    return "nav-link"


@register.simple_tag(takes_context=True)
def querystring(context, **kwargs):
    params = context["request"].GET.copy()
    for key, value in kwargs.items():
        if value in (None, ""):
            params.pop(key, None)
        else:
            params[key] = value
    return params.urlencode()
