"""Rapports PDF. La police Unicode est choisie selon le système."""

from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    PageTemplate,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from apps.overtime.formatting import format_minutes, format_montant
from apps.reports.services import by_agent, by_service, by_type, historique_par_mois, report_totals

NAVY = colors.HexColor("#1B3A4B")
ROW = colors.HexColor("#F4F7F8")


def _register_fonts():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    candidates = [
        (Path(r"C:\Windows\Fonts\arial.ttf"), Path(r"C:\Windows\Fonts\arialbd.ttf")),
        (
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ),
        (
            Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
            Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
        ),
    ]
    for regular, bold in candidates:
        if regular.exists() and bold.exists():
            pdfmetrics.registerFont(TTFont("AppSans", str(regular)))
            pdfmetrics.registerFont(TTFont("AppSans-Bold", str(bold)))
            return "AppSans", "AppSans-Bold"
    return "Helvetica", "Helvetica-Bold"


FONT, FONT_BOLD = _register_fonts()


def _styles():
    base = getSampleStyleSheet()
    base.add(ParagraphStyle(name="CoverTitle", fontName=FONT_BOLD, fontSize=11, leading=13, textColor=NAVY, alignment=TA_LEFT, spaceAfter=4))
    base.add(ParagraphStyle(name="Meta", fontName=FONT, fontSize=9, leading=12, textColor=colors.HexColor("#334155")))
    base.add(ParagraphStyle(name="Section", fontName=FONT_BOLD, fontSize=11, leading=13, textColor=NAVY, spaceBefore=8, spaceAfter=4))
    base.add(ParagraphStyle(name="Cell", fontName=FONT, fontSize=8, leading=10))
    base.add(ParagraphStyle(name="CellBold", fontName=FONT_BOLD, fontSize=8, leading=10))
    return base


def _table(headers, rows, col_widths):
    styles = _styles()
    head = [Paragraph(str(item), styles["CellBold"]) for item in headers]
    body = [[Paragraph(str(cell), styles["Cell"]) for cell in row] for row in rows]
    table = Table([head] + body, colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROW]),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D0D5DD")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def _header_story(story, styles, *, titre, periode, utilisateur, numero, genere_le, service=""):
    story.append(Paragraph(titre, styles["Section"]))
    meta = [
        f"<b>Numéro :</b> {numero}",
        f"<b>Service :</b> {service or 'Ensemble de l’administration'}",
        f"<b>Période :</b> {periode}",
        f"<b>Date de génération :</b> {genere_le}",
        f"<b>Généré par :</b> {utilisateur}",
    ]
    for line in meta:
        story.append(Paragraph(line, styles["Meta"]))
    story.append(Spacer(1, 4 * mm))


def _money(value, devise):
    return format_montant(value, devise)


BLUE = colors.HexColor("#1D4ED8")
INK = colors.HexColor("#111827")
MUTED = colors.HexColor("#6B7280")
LINE = colors.HexColor("#E5E7EB")
BAND = colors.HexColor("#F3F4F6")
GREEN = colors.HexColor("#059669")
GREEN_BG = colors.HexColor("#ECFDF5")
RED = colors.HexColor("#DC2626")
HEADER_BG = colors.HexColor("#F9FAFB")


def _logo_flowable():
    path = Path(__file__).resolve().parents[3] / "static" / "img" / "logo-dgtcp.png"
    if not path.exists():
        return None
    reader = ImageReader(str(path))
    width, height = reader.getSize()
    target_h = 16 * mm
    target_w = target_h * width / height
    if target_w > 62 * mm:
        target_w = 62 * mm
        target_h = target_w * height / width
    return Image(str(path), width=target_w, height=target_h, mask="auto")


def _p(text, style):
    return Paragraph(escape(str(text if text not in (None, "") else "—")), style)


def _rich(html, style):
    return Paragraph(html, style)


def _styled():
    cached = getattr(_styled, "cache", None)
    if cached is not None:
        return cached
    cached = {
        "title": ParagraphStyle("RecuTitle", fontName=FONT_BOLD, fontSize=11, leading=13, alignment=TA_RIGHT, textColor=INK),
        "subtitle": ParagraphStyle("RecuSub", fontName=FONT, fontSize=8, leading=11, alignment=TA_RIGHT, textColor=MUTED),
        "ref": ParagraphStyle("RecuRef", fontName=FONT_BOLD, fontSize=13, leading=16, alignment=TA_CENTER, textColor=BLUE),
        "caption": ParagraphStyle("RecuCap", fontName=FONT, fontSize=7, leading=9, alignment=TA_CENTER, textColor=MUTED),
        "ok": ParagraphStyle("RecuOk", fontName=FONT, fontSize=8.5, leading=11, textColor=colors.HexColor("#065F46")),
        "section": ParagraphStyle("RecuSection", fontName=FONT_BOLD, fontSize=9, leading=12, textColor=INK),
        "label": ParagraphStyle("RecuLabel", fontName=FONT, fontSize=8, leading=10, textColor=MUTED),
        "value": ParagraphStyle("RecuValue", fontName=FONT, fontSize=8, leading=10, alignment=TA_RIGHT, textColor=INK),
        "head": ParagraphStyle("RecuHead", fontName=FONT_BOLD, fontSize=7.5, leading=9, textColor=INK),
        "cell": ParagraphStyle("RecuCell", fontName=FONT, fontSize=7.5, leading=9.5, textColor=INK),
        "cellRight": ParagraphStyle("RecuCellRight", fontName=FONT, fontSize=7.5, leading=9.5, alignment=TA_RIGHT, textColor=INK),
        "totalLabel": ParagraphStyle("RecuTotalLabel", fontName=FONT_BOLD, fontSize=9, leading=12, textColor=INK),
        "totalValue": ParagraphStyle("RecuTotalValue", fontName=FONT_BOLD, fontSize=10, leading=12, alignment=TA_RIGHT, textColor=RED),
        "empty": ParagraphStyle("RecuEmpty", fontName=FONT, fontSize=9, leading=12, alignment=TA_CENTER, textColor=MUTED),
    }
    _styled.cache = cached
    return cached


def _rule(width):
    rule = Table([[""]], colWidths=[width], rowHeights=[1.6])
    rule.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BLUE),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return rule


def _doc_header(styles, width, *, title, genere_le):
    logo = _logo_flowable()
    text = [
        _rich(escape(title), styles["title"]),
        _rich(f"Émis le : {escape(genere_le)}", styles["subtitle"]),
    ]
    block = text
    if logo is None:
        data = [[block]]
        cols = [width]
    else:
        data = [[logo, block]]
        cols = [64 * mm, width - 64 * mm]
    header = Table(data, colWidths=cols)
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (-1, 0), (-1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return header


def _reference_band(styles, width, numero, caption):
    band = Table(
        [[_rich(escape(numero), styles["ref"])], [_rich(escape(caption), styles["caption"])]],
        colWidths=[width],
    )
    band.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BAND),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 8),
        ("TOPPADDING", (0, 1), (-1, 1), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return band


def _notice(styles, width, message):
    notice = Table(
        [["", _rich(escape(message), styles["ok"])]],
        colWidths=[2.2 * mm, width - 2.2 * mm],
    )
    notice.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), GREEN),
        ("BACKGROUND", (1, 0), (1, 0), GREEN_BG),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (1, 0), (1, 0), 8),
        ("RIGHTPADDING", (1, 0), (1, 0), 8),
        ("LEFTPADDING", (0, 0), (0, 0), 0),
        ("RIGHTPADDING", (0, 0), (0, 0), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return notice


def _info_card(styles, title, pairs, width):
    rows = [[_rich(escape(title), styles["section"])]]
    inner = width - 16
    label_w = inner * 0.46
    value_w = inner - label_w
    for label, value in pairs:
        line = Table(
            [[_p(label, styles["label"]), _p(value, styles["value"])]],
            colWidths=[label_w, value_w],
        )
        line.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LINEBELOW", (0, 0), (-1, -1), 0.3, LINE),
        ]))
        rows.append([line])
    card = Table(rows, colWidths=[width])
    card.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("LINEBELOW", (0, 0), (-1, 0), 0.4, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, 0), 7),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 1), (-1, -1), 1),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 4),
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return card


def _data_table(styles, headers, rows, widths, right_columns=()):
    head = [_rich(escape(item), styles["head"]) for item in headers]
    body = []
    for row in rows:
        body.append([
            _rich(cell, styles["cellRight"] if index in right_columns else styles["cell"])
            for index, cell in enumerate(row)
        ])
    table = Table([head] + body, colWidths=widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, LINE),
        ("LINEBELOW", (0, 1), (-1, -2), 0.25, LINE),
        ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
    ]))
    return table


def _total_block(styles, width, lines, total_label, total_value):
    rows = []
    for label, value in lines:
        rows.append([_p(label, styles["label"]), _p(value, styles["value"])])
    rows.append([_rich(escape(total_label), styles["totalLabel"]), _rich(escape(total_value), styles["totalValue"])])
    table = Table(rows, colWidths=[width * 0.62, width * 0.38])
    last = len(rows) - 1
    table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("LINEABOVE", (0, last), (-1, last), 0.8, LINE),
        ("BACKGROUND", (0, last), (-1, last), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, last - 1), 0.25, LINE),
    ]))
    return table


def _paint_page(canvas, doc, *, pagesize):
    canvas.saveState()
    canvas.setFillColor(colors.Color(0.05, 0.55, 0.35, alpha=0.08))
    canvas.setFont(FONT_BOLD, 78)
    canvas.translate(pagesize[0] / 2, pagesize[1] / 2)
    canvas.rotate(28)
    canvas.drawCentredString(0, 0, "VALIDÉ")
    canvas.restoreState()


def _paint_footer(canvas, doc, *, site, numero, genere_le, pagesize):
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.4)
    canvas.line(14 * mm, 16 * mm, pagesize[0] - 14 * mm, 16 * mm)
    canvas.setFillColor(MUTED)
    canvas.setFont(FONT, 8)
    canvas.drawCentredString(pagesize[0] / 2, 11.5 * mm, f"Généré le {genere_le} — {numero} — page {doc.page}")
    canvas.setFont(FONT, 7)
    canvas.drawCentredString(
        pagesize[0] / 2,
        7.5 * mm,
        f"{site.nom_administration} — document établi à partir de la saisie validée",
    )
    canvas.restoreState()


class _SheetPage(PageTemplate):
    def __init__(self, frame, site, numero, genere_le, pagesize):
        super().__init__(id="fiche", frames=[frame], pagesize=pagesize)
        self._site = site
        self._numero = numero
        self._genere_le = genere_le
        self._pagesize = pagesize

    def beforeDrawPage(self, canv, doc):
        _paint_page(canv, doc, pagesize=self._pagesize)

    def afterDrawPage(self, canv, doc):
        _paint_footer(
            canv,
            doc,
            site=self._site,
            numero=self._numero,
            genere_le=self._genere_le,
            pagesize=self._pagesize,
        )


def _build_sheet(story, *, site, numero, genere_le, pagesize):
    buffer = BytesIO()
    document = BaseDocTemplate(
        buffer,
        pagesize=pagesize,
        title=numero,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=12 * mm,
        bottomMargin=20 * mm,
    )
    frame = Frame(
        14 * mm,
        20 * mm,
        pagesize[0] - 28 * mm,
        pagesize[1] - 32 * mm,
        id="corps",
        showBoundary=0,
    )
    document.addPageTemplates([_SheetPage(frame, site, numero, genere_le, pagesize)])
    document.build(story)
    buffer.seek(0)
    return buffer


def _opening(styles, width, *, title, caption, notice, site, numero, genere_le):
    return [
        _doc_header(styles, width, title=title, genere_le=genere_le),
        Spacer(1, 2.5 * mm),
        _rule(width),
        Spacer(1, 4 * mm),
        _reference_band(styles, width, numero, caption),
        Spacer(1, 4 * mm),
        _notice(styles, width, notice),
        Spacer(1, 4 * mm),
    ]


def _fiche_individuelle(queryset, *, site, numero, periode, genere_le, agent=None):
    styles = _styled()
    width = A4[0] - 28 * mm
    demandes = list(queryset)
    if agent is None and demandes:
        agent = demandes[0].agent
    story = _opening(
        styles,
        width,
        title="FICHE INDIVIDUELLE",
        caption="NUMÉRO DE LA FICHE",
        notice="Saisie validée. Cette fiche reprend les heures supplémentaires enregistrées pour l'agent.",
        site=site,
        numero=numero,
        genere_le=genere_le,
    )
    half = (width - 4 * mm) / 2
    identite = [
        ("Matricule", agent.matricule if agent else "—"),
        ("Nom", agent.nom_complet if agent else "—"),
        ("Grade", agent.grade if agent and agent.grade_id else "—"),
        ("Fonction", agent.fonction if agent and agent.fonction_id else "—"),
    ]
    periode_pairs = [
        ("Période", periode),
        ("Service", agent.service.nom if agent else "—"),
        ("Lignes", str(len(demandes))),
        ("Durée", format_minutes(sum(item.duree_minutes for item in demandes))),
    ]
    cards = Table(
        [[
            _info_card(styles, "AGENT", identite, half),
            _info_card(styles, "AFFECTATION", periode_pairs, half),
        ]],
        colWidths=[half, half],
    )
    cards.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (0, 0), 2 * mm),
        ("LEFTPADDING", (1, 0), (1, 0), 2 * mm),
        ("RIGHTPADDING", (1, 0), (1, 0), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(cards)
    story.append(Spacer(1, 4 * mm))
    if demandes:
        rows = []
        for demande in demandes:
            motif = escape(demande.motif_libelle)
            if demande.observation:
                motif += f"<br/><font color='#6B7280'>{escape(demande.observation)}</font>"
            rows.append([
                escape(demande.date_travail.strftime("%d/%m/%Y")),
                escape(demande.heure_debut.strftime("%H:%M")),
                escape(demande.heure_fin.strftime("%H:%M")),
                escape(format_minutes(demande.duree_minutes)),
                motif,
                escape(_money(demande.montant_estime, site.devise)),
            ])
        story.append(_data_table(
            styles,
            ["Date", "Début", "Fin", "Durée", "Motif", "Montant"],
            rows,
            [24 * mm, 16 * mm, 16 * mm, 18 * mm, width - 106 * mm, 32 * mm],
            right_columns={5},
        ))
    else:
        story.append(_rich("Aucune heure supplémentaire pour cette période.", styles["empty"]))
    story.append(Spacer(1, 4 * mm))
    total = sum((item.montant_estime for item in demandes), 0)
    story.append(_total_block(
        styles,
        width,
        [("Durée totale", format_minutes(sum(item.duree_minutes for item in demandes)))],
        "MONTANT TOTAL",
        _money(total, site.devise),
    ))
    return _build_sheet(story, site=site, numero=numero, genere_le=genere_le, pagesize=A4)


def _liste_collective(queryset, *, site, numero, periode, genere_le):
    styles = _styled()
    page = landscape(A4)
    width = page[0] - 28 * mm
    demandes = list(queryset)
    agents = {item.agent_id for item in demandes}
    duree = sum(item.duree_minutes for item in demandes)
    total = sum((item.montant_estime for item in demandes), 0)
    story = _opening(
        styles,
        width,
        title="SITUATION MENSUELLE DES HEURES SUPPLÉMENTAIRES",
        caption="NUMÉRO DE LA LISTE",
        notice="Liste validée. Ce document reprend le cumul des heures supplémentaires de chaque agent.",
        site=site,
        numero=numero,
        genere_le=genere_le,
    )
    quarter = width / 4
    pad = 1.5 * mm
    metrics = [
        ("Période", periode),
        ("Agents", str(len(agents))),
        ("Durée", format_minutes(duree)),
        ("Montant", _money(total, site.devise)),
    ]
    metric_row = []
    for label, value in metrics:
        box = Table(
            [[_rich(escape(label.upper()), styles["caption"])], [_rich(escape(value), styles["ref"])]],
            colWidths=[quarter - 2 * pad],
        )
        box.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.6, LINE),
            ("BACKGROUND", (0, 0), (-1, -1), colors.white),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, 0), 6),
            ("BOTTOMPADDING", (0, -1), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ]))
        metric_row.append(box)
    metrics_table = Table([metric_row], colWidths=[quarter] * 4)
    metrics_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), pad),
        ("RIGHTPADDING", (0, 0), (-1, -1), pad),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(metrics_table)
    story.append(Spacer(1, 4 * mm))
    cumuls = by_agent(queryset)
    if cumuls:
        rows = []
        for item in cumuls:
            service = item["agent__service__code"] or "—"
            if item["agent__service__nom"]:
                service = f"{service} — {item['agent__service__nom']}"
            rows.append([
                escape(item["agent__matricule"] or "—"),
                escape(item["nom"] or "—"),
                escape(service),
                escape(str(item["nombre"])),
                escape(format_minutes(item["minutes"] or 0)),
                escape(_money(item["montant"] or 0, site.devise)),
            ])
        story.append(_data_table(
            styles,
            ["Matricule", "Agent", "Service", "Saisies", "Durée", "Montant"],
            rows,
            [32 * mm, 62 * mm, width - 176 * mm, 22 * mm, 24 * mm, 36 * mm],
            right_columns={3, 4, 5},
        ))
    else:
        story.append(_rich("Aucune heure supplémentaire pour cette période.", styles["empty"]))
    story.append(Spacer(1, 4 * mm))
    story.append(_total_block(
        styles,
        width,
        [
            ("Saisies cumulées", str(len(demandes))),
            ("Durée totale", format_minutes(duree)),
        ],
        "MONTANT TOTAL",
        _money(total, site.devise),
    ))
    return _build_sheet(story, site=site, numero=numero, genere_le=genere_le, pagesize=page)


def _rapport_historique(queryset, *, site, numero, periode, genere_le):
    styles = _styled()
    page = landscape(A4)
    width = page[0] - 28 * mm
    from apps.overtime.forms import ANNEE_MOIS

    annee = ANNEE_MOIS
    story = _opening(
        styles,
        width,
        title="RAPPORT HISTORIQUE DES HEURES SUPPLÉMENTAIRES",
        caption="NUMÉRO DU RAPPORT",
        notice="Historique des mois antérieurs déjà payés.",
        site=site,
        numero=numero,
        genere_le=genere_le,
    )
    mois_rows = historique_par_mois(queryset, annee)
    if mois_rows:
        story.append(_data_table(
            styles,
            ["Mois", "Agents", "Saisies", "Durée", "Montant"],
            [
                [
                    escape(item["label"]),
                    escape(str(item["agents"])),
                    escape(str(item["nombre"])),
                    escape(format_minutes(item["minutes"] or 0)),
                    escape(_money(item["montant"] or 0, site.devise)),
                ]
                for item in mois_rows
            ],
            [55 * mm, 28 * mm, 28 * mm, 32 * mm, width - 143 * mm],
            right_columns={1, 2, 3, 4},
        ))
    story.append(Spacer(1, 4 * mm))
    cumuls = by_agent(queryset)
    if cumuls:
        rows = []
        for item in cumuls:
            service = item["agent__service__code"] or "—"
            if item["agent__service__nom"]:
                service = f"{service} — {item['agent__service__nom']}"
            rows.append([
                escape(item["agent__matricule"] or "—"),
                escape(item["nom"] or "—"),
                escape(service),
                escape(str(item["nombre"])),
                escape(format_minutes(item["minutes"] or 0)),
                escape(_money(item["montant"] or 0, site.devise)),
            ])
        story.append(_data_table(
            styles,
            ["Matricule", "Agent", "Service", "Saisies", "Durée", "Montant"],
            rows,
            [32 * mm, 62 * mm, width - 176 * mm, 22 * mm, 24 * mm, 36 * mm],
            right_columns={3, 4, 5},
        ))
    else:
        story.append(_rich("Aucun mois antérieur déjà payé.", styles["empty"]))
    total = sum((item.montant_estime for item in queryset), 0)
    duree = sum(item.duree_minutes for item in queryset)
    story.append(Spacer(1, 4 * mm))
    story.append(_total_block(
        styles,
        width,
        [
            ("Saisies cumulées", str(queryset.count())),
            ("Durée totale", format_minutes(duree)),
        ],
        "MONTANT TOTAL",
        _money(total, site.devise),
    ))
    return _build_sheet(story, site=site, numero=numero, genere_le=genere_le, pagesize=page)


def build_pdf(kind, queryset, *, site, numero, periode, utilisateur, genere_le, service_label="", agent=None):
    """Construit un PDF individuel, de service, mensuel, historique ou administratif."""
    if kind == "HISTORIQUE":
        return _rapport_historique(queryset, site=site, numero=numero, periode=periode, genere_le=genere_le)
    if kind == "MENSUEL" and agent is not None:
        kind = "INDIVIDUEL"
    if kind == "INDIVIDUEL":
        return _fiche_individuelle(
            queryset,
            site=site,
            numero=numero,
            periode=periode,
            genere_le=genere_le,
            agent=agent,
        )
    if kind == "MENSUEL":
        return _liste_collective(queryset, site=site, numero=numero, periode=periode, genere_le=genere_le)
    buffer = BytesIO()
    page = landscape(A4)
    document = SimpleDocTemplate(
        buffer,
        pagesize=page,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=14 * mm,
        title=numero,
    )
    styles = _styles()
    story = []
    titles = {
        "INDIVIDUEL": "Rapport individuel des heures supplémentaires",
        "SERVICE": "Rapport des heures supplémentaires par service",
        "MENSUEL": "Rapport mensuel des heures supplémentaires",
        "ADMINISTRATIF": "Rapport administratif — synthèse des heures supplémentaires",
    }
    _header_story(
        story,
        styles,
        titre=titles.get(kind, "Rapport"),
        periode=periode,
        utilisateur=utilisateur,
        numero=numero,
        genere_le=genere_le,
        service=service_label,
    )
    totals = report_totals(queryset)
    story.append(
        Paragraph(
            f"Demandes : {totals['nombre']} — Durée : {format_minutes(totals['minutes'])} "
            f"— Montant estimé : {_money(totals['montant'], site.devise)}",
            styles["Meta"],
        )
    )
    story.append(Spacer(1, 3 * mm))

    if kind == "ADMINISTRATIF":
        story.append(Paragraph("Répartition par service", styles["Section"]))
        service_rows = [
            [
                item["agent__service__code"] or "",
                item["agent__service__nom"] or "",
                item["nombre"],
                format_minutes(item["minutes"] or 0),
                _money(item["montant"] or 0, site.devise),
            ]
            for item in by_service(queryset)
        ] or [["—", "Aucune donnée", "", "", ""]]
        story.append(_table(
            ["Code", "Service", "Demandes", "Durée", "Montant"],
            service_rows,
            [25 * mm, 80 * mm, 30 * mm, 30 * mm, 45 * mm],
        ))
        story.append(Paragraph("Répartition par type", styles["Section"]))
        type_rows = [
            [
                item["type_heure__code"] or "",
                item["type_heure__libelle"] or "",
                item["nombre"],
                format_minutes(item["minutes"] or 0),
                _money(item["montant"] or 0, site.devise),
            ]
            for item in by_type(queryset)
        ] or [["—", "Aucune donnée", "", "", ""]]
        story.append(_table(
            ["Code", "Type", "Demandes", "Durée", "Montant"],
            type_rows,
            [40 * mm, 70 * mm, 30 * mm, 30 * mm, 45 * mm],
        ))
    elif kind == "SERVICE":
        agent_rows = [
            [
                item["agent__matricule"],
                " ".join(part for part in (item["agent__nom"], item["agent__postnom"], item["agent__prenom"]) if part),
                item["nombre"],
                format_minutes(item["minutes"] or 0),
                _money(item["montant"] or 0, site.devise),
            ]
            for item in by_agent(queryset)
        ] or [["—", "Aucune donnée", "", "", ""]]
        story.append(_table(
            ["Matricule", "Agent", "Demandes", "Durée", "Montant"],
            agent_rows,
            [35 * mm, 90 * mm, 30 * mm, 30 * mm, 45 * mm],
        ))
    else:
        detail_rows = []
        for demande in queryset:
            detail_rows.append([
                demande.agent.matricule,
                demande.agent.nom_complet,
                demande.agent.service.code,
                demande.date_travail.strftime("%d/%m/%Y"),
                demande.heure_debut.strftime("%H:%M"),
                demande.heure_fin.strftime("%H:%M"),
                format_minutes(demande.duree_minutes),
                demande.type_heure.code,
                demande.get_statut_display(),
                _money(demande.montant_estime, site.devise),
            ])
        if not detail_rows:
            detail_rows = [["—", "Aucune donnée", "", "", "", "", "", "", "", ""]]
        story.append(_table(
            ["Matricule", "Agent", "Service", "Date", "Début", "Fin", "Durée", "Type", "Statut", "Montant"],
            detail_rows,
            [28 * mm, 42 * mm, 22 * mm, 22 * mm, 16 * mm, 16 * mm, 18 * mm, 32 * mm, 24 * mm, 28 * mm],
        ))

    def _footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(FONT, 8)
        canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.drawString(12 * mm, 8 * mm, f"{site.nom_administration} — {numero}")
        canvas.drawRightString(page[0] - 12 * mm, 8 * mm, f"Page {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=_footer, onLaterPages=_footer)
    buffer.seek(0)
    return buffer
