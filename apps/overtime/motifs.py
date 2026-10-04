"""Motifs proposés à la saisie des heures supplémentaires."""

MOTIFS = (
    ("PERMANENCE", "Permanence"),
    ("URGENCE", "Urgence de service"),
    ("CLOTURE", "Clôture des opérations"),
    ("PAIEMENT", "Traitement des paiements"),
    ("INVENTAIRE", "Inventaire et arrêté de caisse"),
    ("CONTROLE", "Mission de contrôle"),
    ("RENFORT", "Renfort de service"),
)


def libelle_motif(code):
    return dict(MOTIFS).get(code, code)
