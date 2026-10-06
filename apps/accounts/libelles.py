"""Noms français des permissions Django enregistrées en anglais."""

_PREFIXES = (
    ("Can add ", "Peut ajouter "),
    ("Can change ", "Peut modifier "),
    ("Can delete ", "Peut supprimer "),
    ("Can view ", "Peut consulter "),
)

_OBJETS = {
    "user": "utilisateur",
    "group": "groupe",
    "permission": "permission",
    "log entry": "entrée d'historique",
    "content type": "type de contenu",
    "session": "session",
}


def traduire_permission(nom):
    texte = nom or ""
    for source, cible in _PREFIXES:
        if texte.startswith(source):
            objet = texte[len(source):]
            return cible + _OBJETS.get(objet, objet)
    return texte
