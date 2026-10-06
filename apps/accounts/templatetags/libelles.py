from django import template

from apps.accounts.libelles import traduire_permission

register = template.Library()


@register.filter
def nom_fr(nom):
    return traduire_permission(nom)
