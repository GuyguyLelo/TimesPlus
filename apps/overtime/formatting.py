from decimal import Decimal, InvalidOperation


def format_montant(value, devise=""):
    """Affiche un montant, par exemple 30875.5 → 30 875,50."""
    if value is None or value == "":
        return "—"
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return "—"
    sign = "-" if amount < 0 else ""
    text = f"{abs(amount):,.2f}".replace(",", " ").replace(".", ",")
    formatted = f"{sign}{text}"
    if devise:
        return f"{formatted} {devise}"
    return formatted


def format_minutes(value):
    """Affiche une durée stockée en minutes, par exemple 210 → 03h30."""
    if value is None:
        return "—"
    total = int(value)
    hours, minutes = divmod(abs(total), 60)
    formatted = f"{hours:02d}h{minutes:02d}"
    if total < 0:
        return f"-{formatted}"
    return formatted
