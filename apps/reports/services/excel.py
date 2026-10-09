"""Export Excel en trois feuilles."""

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from apps.agents.matricule import format_matricule
from apps.overtime.formatting import format_minutes, format_montant
from apps.reports.services import by_service, report_totals

NAVY = "1B3A4B"
THIN = Border(
    left=Side(style="thin", color="D0D5DD"),
    right=Side(style="thin", color="D0D5DD"),
    top=Side(style="thin", color="D0D5DD"),
    bottom=Side(style="thin", color="D0D5DD"),
)
HEADER_FILL = PatternFill("solid", fgColor=NAVY)
HEADER_FONT = Font(color="FFFFFF", bold=True, name="Calibri")
TITLE_FONT = Font(bold=True, size=14, color=NAVY, name="Calibri")
TOTAL_FILL = PatternFill("solid", fgColor="E7EEF2")


def _header(ws, titles):
    for index, title in enumerate(titles, start=1):
        cell = ws.cell(1, index, title)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = THIN
    ws.auto_filter.ref = f"A1:{get_column_letter(len(titles))}1"
    ws.freeze_panes = "A2"
    ws.row_dimensions[1].height = 22
    ws.auto_filter.ref = f"A1:{get_column_letter(len(titles))}1"
    ws.sheet_view.showGridLines = False


def _autosize(ws):
    for column in ws.columns:
        letter = get_column_letter(column[0].column)
        width = 12
        for cell in column:
            if cell.value is not None:
                width = max(width, min(len(str(cell.value)) + 2, 42))
        ws.column_dimensions[letter].width = width


def _validator(demande):
    approvals = getattr(demande, "approbations", None) or []
    if not approvals:
        return None, None
    decision = approvals[0]
    user = decision.utilisateur
    label = user.get_full_name() or user.get_username() if user else ""
    return label, decision.created_at


def build_workbook(queryset, *, site, numero, periode, utilisateur):
    totals = report_totals(queryset)
    services = by_service(queryset)
    workbook = Workbook()

    summary = workbook.active
    summary.title = "Synthèse"
    summary["A1"] = site.nom_administration
    summary["A1"].font = TITLE_FONT
    summary["A2"] = "Export des heures supplémentaires"
    rows = [
        ("Numéro", numero),
        ("Période", periode),
        ("Généré par", utilisateur),
        ("Devise", site.devise),
        ("Nombre de demandes", totals["nombre"]),
        ("Total minutes", totals["minutes"]),
        ("Total durée", format_minutes(totals["minutes"])),
        ("Montant estimé", format_montant(totals["montant"], site.devise)),
    ]
    for offset, (label, value) in enumerate(rows, start=4):
        summary.cell(offset, 1, label).font = Font(bold=True, name="Calibri")
        cell = summary.cell(offset, 2, value)
        cell.font = Font(name="Calibri")
        if label == "Total minutes":
            cell.number_format = "#,##0"
    summary.column_dimensions["A"].width = 28
    summary.column_dimensions["B"].width = 42

    detail = workbook.create_sheet("Détails")
    headers = [
        "Matricule",
        "Nom",
        "Postnom",
        "Prénom",
        "Service",
        "Date",
        "Heure début",
        "Heure fin",
        "Durée",
        "Type",
        "Motif",
        "Observation",
        "Statut",
        "Validateur",
        "Date validation",
        "Montant estimé",
    ]
    _header(detail, headers)
    for row_index, demande in enumerate(queryset, start=2):
        validator, validated_at = _validator(demande)
        values = [
            format_matricule(demande.agent.matricule),
            demande.agent.nom,
            demande.agent.postnom,
            demande.agent.prenom,
            demande.agent.service.nom,
            demande.date_travail,
            demande.heure_debut,
            demande.heure_fin,
            demande.duree_minutes / (24 * 60),
            demande.type_heure.libelle,
            demande.motif_libelle,
            demande.observation,
            demande.get_statut_display(),
            validator or "",
            validated_at.replace(tzinfo=None) if validated_at else None,
            float(demande.montant_estime),
        ]
        for column, value in enumerate(values, start=1):
            cell = detail.cell(row_index, column, value)
            cell.border = THIN
            cell.font = Font(name="Calibri", size=10)
        detail.cell(row_index, 6).number_format = "DD/MM/YYYY"
        detail.cell(row_index, 7).number_format = "HH:MM"
        detail.cell(row_index, 8).number_format = "HH:MM"
        detail.cell(row_index, 9).number_format = "[h]:mm"
        detail.cell(row_index, 14).number_format = "DD/MM/YYYY HH:MM"
        detail.cell(row_index, 15).number_format = "#,##0.00"
    last_data = max(detail.max_row, 1)
    total_row = last_data + 1 if last_data > 1 else 2
    if queryset:
        total_row = detail.max_row + 1
        detail.cell(total_row, 1, "TOTAL").font = Font(bold=True, name="Calibri")
        detail.cell(total_row, 9, f"=SUM(I2:I{total_row - 1})")
        detail.cell(total_row, 9).number_format = "[h]:mm"
        detail.cell(total_row, 15, f"=SUM(O2:O{total_row - 1})")
        detail.cell(total_row, 15).number_format = "#,##0.00"
        for column in range(1, 16):
            detail.cell(total_row, column).fill = TOTAL_FILL
            detail.cell(total_row, column).font = Font(bold=True, name="Calibri")
        detail.auto_filter.ref = f"A1:O{total_row - 1}"
    _autosize(detail)

    sheet = workbook.create_sheet("Par service")
    _header(sheet, ["Code", "Service", "Nombre", "Durée", "Montant estimé"])
    for index, item in enumerate(services, start=2):
        sheet.cell(index, 1, item["agent__service__code"] or "")
        sheet.cell(index, 2, item["agent__service__nom"] or "")
        sheet.cell(index, 3, item["nombre"]).number_format = "#,##0"
        duration = sheet.cell(index, 4, (item["minutes"] or 0) / (24 * 60))
        duration.number_format = "[h]:mm"
        amount = sheet.cell(index, 5, float(item["montant"] or 0))
        amount.number_format = "#,##0.00"
        for column in range(1, 6):
            sheet.cell(index, column).border = THIN
            sheet.cell(index, column).font = Font(name="Calibri", size=10)
    if services:
        total_row = len(services) + 2
        sheet.cell(total_row, 1, "TOTAL").font = Font(bold=True)
        sheet.cell(total_row, 3, f"=SUM(C2:C{total_row - 1})").number_format = "#,##0"
        sheet.cell(total_row, 4, f"=SUM(D2:D{total_row - 1})").number_format = "[h]:mm"
        sheet.cell(total_row, 5, f"=SUM(E2:E{total_row - 1})").number_format = "#,##0.00"
        sheet.auto_filter.ref = f"A1:E{total_row - 1}"
    _autosize(sheet)

    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer
