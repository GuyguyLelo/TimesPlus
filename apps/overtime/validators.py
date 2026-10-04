"""Contrôle des pièces jointes : extension, contenu, taille et nom de fichier."""

import re
from pathlib import Path

from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError

BLOCKED_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".com", ".scr", ".js", ".mjs", ".php", ".phtml",
    ".py", ".sh", ".bash", ".ps1", ".dll", ".so", ".html", ".htm", ".svg",
    ".xhtml", ".jar", ".vbs", ".wsf", ".msi", ".apk", ".cgi", ".pl", ".hta",
    ".lnk", ".iso", ".zip", ".rar", ".7z",
}

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".doc", ".docx", ".xls", ".xlsx"}

ALLOWED_MIME = {
    ".pdf": {"application/pdf"},
    ".png": {"image/png"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".doc": {"application/msword"},
    ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    ".xls": {"application/vnd.ms-excel", "application/vnd.ms-excel"},
    ".xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
}


def sanitize_filename(name: str) -> str:
    base = Path(name or "document").name.replace("\x00", "")
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", base)
    cleaned = cleaned.strip("._") or "document"
    return cleaned[:120]


def _magic_ok(extension: str, header: bytes) -> bool:
    if extension == ".pdf":
        return header.startswith(b"%PDF")
    if extension == ".png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    if extension in {".jpg", ".jpeg"}:
        return header.startswith(b"\xff\xd8\xff")
    if extension in {".doc", ".xls"}:
        return header.startswith(b"\xd0\xcf\x11\xe0")
    if extension in {".docx", ".xlsx"}:
        return header.startswith(b"PK\x03\x04")
    return False


def _verify_image(uploaded):
    try:
        image = Image.open(uploaded)
        image.verify()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValidationError("L'image est invalide ou corrompue.") from exc
    finally:
        uploaded.seek(0)


def validate_uploaded_file(uploaded):
    """Valide un fichier déposé et retourne un nom de stockage sûr."""
    from apps.settings_app.models import SiteSettings

    if uploaded is None:
        raise ValidationError("Aucun fichier n'a été transmis.")
    settings_obj = SiteSettings.load()
    max_bytes = int(settings_obj.taille_max_fichier_mo) * 1024 * 1024
    size = getattr(uploaded, "size", 0) or 0
    if size <= 0:
        raise ValidationError("Le fichier est vide.")
    if size > max_bytes:
        raise ValidationError(
            f"Le fichier dépasse la taille maximale de {settings_obj.taille_max_fichier_mo} Mo."
        )

    extension = Path(uploaded.name).suffix.lower()
    if extension in BLOCKED_EXTENSIONS or extension not in ALLOWED_EXTENSIONS:
        raise ValidationError("Cette extension de fichier n'est pas autorisée.")

    content_type = (getattr(uploaded, "content_type", "") or "").split(";")[0].strip().lower()
    allowed = ALLOWED_MIME[extension]
    if content_type and content_type not in allowed and content_type != "application/octet-stream":
        raise ValidationError("Le type de contenu du fichier n'est pas autorisé.")

    header = uploaded.read(16)
    uploaded.seek(0)
    if not _magic_ok(extension, header):
        raise ValidationError("Le contenu du fichier ne correspond pas à son extension.")
    if extension in {".png", ".jpg", ".jpeg"}:
        _verify_image(uploaded)
    return sanitize_filename(uploaded.name)
