"""Affiche un PDF généré, puis permet de télécharger le même fichier."""

import re
import secrets
import tempfile
import time
from pathlib import Path

from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.urls import reverse

_TOKEN = re.compile(r"^[A-Za-z0-9_-]{16,128}$")
_DUREE = 30 * 60


def deposer_pdf(user_id, contenu, nom_fichier):
    jeton = secrets.token_urlsafe(24)
    dossier = _dossier(user_id)
    dossier.mkdir(parents=True, exist_ok=True)
    _nettoyer(dossier)
    (dossier / f"{jeton}.pdf").write_bytes(contenu)
    (dossier / f"{jeton}.name").write_text(_nom(nom_fichier), encoding="utf-8")
    return jeton


def lire_pdf(user_id, jeton):
    if not _TOKEN.fullmatch(jeton or ""):
        return None
    dossier = _dossier(user_id).resolve()
    chemin = (dossier / f"{jeton}.pdf").resolve()
    if dossier not in chemin.parents or not chemin.is_file():
        return None
    nom = (dossier / f"{jeton}.name").read_text(encoding="utf-8").strip()
    return chemin.read_bytes(), _nom(nom)


def rendre_apercu(request, contenu, nom_fichier, titre, retour):
    jeton = deposer_pdf(request.user.pk, contenu, nom_fichier)
    fichier = reverse("reports:pdf_file", args=[jeton])
    return render(
        request,
        "pdf_apercu.html",
        {
            "titre": titre,
            "retour": retour,
            "fichier": fichier,
            "telecharger": f"{fichier}?telecharger=1",
        },
    )


def reponse_pdf(user_id, jeton, telecharger):
    trouve = lire_pdf(user_id, jeton)
    if trouve is None:
        raise Http404
    contenu, nom = trouve
    mode = "attachment" if telecharger else "inline"
    response = HttpResponse(contenu, content_type="application/pdf")
    response["Content-Disposition"] = f'{mode}; filename="{nom}"'
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Frame-Options"] = "SAMEORIGIN"
    return response


def _dossier(user_id):
    return Path(tempfile.gettempdir()) / "e-heuresup-pdf" / str(user_id)


def _nettoyer(dossier):
    limite = time.time() - _DUREE
    for chemin in dossier.glob("*"):
        try:
            if chemin.stat().st_mtime < limite:
                chemin.unlink()
        except OSError:
            continue


def _nom(nom_fichier):
    nom = Path(str(nom_fichier or "document.pdf")).name
    nom = nom.replace('"', "").replace("\\", "").replace("\n", "").replace("\r", "")
    if not nom.lower().endswith(".pdf"):
        nom = f"{nom}.pdf" if nom else "document.pdf"
    return nom or "document.pdf"
