"""Présentation lisible d'un matricule, sans modifier la valeur enregistrée."""

import re

_CHIFFRES = re.compile(r"^(\d{4,})(.*)$")


def format_matricule(valeur):
    """1515048 devient 1.515.048. Un code comme DTMF-001 reste inchangé."""
    texte = "" if valeur is None else str(valeur).strip()
    if not texte:
        return "—"
    correspondance = _CHIFFRES.match(texte)
    if correspondance is None:
        return texte
    nombre, suite = correspondance.groups()
    groupes = []
    while nombre:
        groupes.append(nombre[-3:])
        nombre = nombre[:-3]
    return ".".join(reversed(groupes)) + suite
