"""Liste du personnel regroupée pour l'impression."""

import unicodedata
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Spacer, Table, TableStyle

from apps.overtime.listes import est_cadre
from apps.reports.services.pdf import (
    FONT,
    LINE,
    MUTED,
    _data_table,
    _doc_header,
    _p,
    _rich,
    _rule,
    _styled,
    _total_block,
)
from apps.services.models import Service


def _clef(texte):
    decomposed = unicodedata.normalize("NFD", texte or "")
    lettres = "".join(car for car in decomposed if unicodedata.category(car) != "Mn")
    return lettres.casefold()


def _dernier(service, niveau):
    trouve = None
    for unite in service.filiation():
        if unite.niveau == niveau:
            trouve = unite
    return trouve


def echelon(service):
    """Direction, division (ou secrétariat, ou poste) et bureau de l'agent."""
    direction = _dernier(service, Service.Niveau.DIRECTION)
    division = _dernier(service, Service.Niveau.DIVISION)
    bureau = _dernier(service, Service.Niveau.BUREAU)
    milieu = division
    if milieu is None and service.niveau == Service.Niveau.SECRETARIAT:
        milieu = service
    parent = bureau.service_parent if bureau is not None else None
    if milieu is None and parent is not None and parent.niveau == Service.Niveau.SECRETARIAT:
        milieu = parent
    if service.niveau == Service.Niveau.POSTE:
        return direction, service, None
    return direction, milieu, bureau


def _tri_agent(agent):
    rang = agent.ordre if agent.ordre is not None else 10**9
    return (rang, _clef(agent.nom), _clef(agent.postnom), _clef(agent.prenom), _clef(agent.matricule))


def _tri_unite(unite):
    return _clef(unite.nom) if unite is not None else ""


def _rang_feuille(feuille):
    valeurs = [agent.ordre for agent in feuille["agents"] if agent.ordre is not None]
    return min(valeurs) if valeurs else 10**9


def regrouper(agents):
    """Regroupe les agents par direction, division et bureau.

    L'ordre déclaré sur l'agent prime. Sans ordre, le tri reste alphabétique.
    """
    feuilles = {}
    for agent in agents:
        direction, milieu, bureau = echelon(agent.service)
        cle = (
            direction.pk if direction is not None else 0,
            milieu.pk if milieu is not None else 0,
            bureau.pk if bureau is not None else 0,
        )
        feuille = feuilles.setdefault(
            cle,
            {"direction": direction, "milieu": milieu, "bureau": bureau, "agents": []},
        )
        feuille["agents"].append(agent)
    for feuille in feuilles.values():
        feuille["agents"].sort(key=_tri_agent)
    ordre = sorted(
        feuilles.values(),
        key=lambda item: (
            _rang_feuille(item),
            _tri_unite(item["direction"]),
            _tri_unite(item["milieu"]),
            _tri_unite(item["bureau"]),
        ),
    )
    directions = []
    par_direction = {}
    for feuille in ordre:
        dkey = feuille["direction"].pk if feuille["direction"] is not None else 0
        direction = par_direction.get(dkey)
        if direction is None:
            direction = {"unite": feuille["direction"], "milieux": [], "index": {}}
            par_direction[dkey] = direction
            directions.append(direction)
        mkey = feuille["milieu"].pk if feuille["milieu"] is not None else 0
        milieu = direction["index"].get(mkey)
        if milieu is None:
            milieu = {"unite": feuille["milieu"], "bureaux": []}
            direction["index"][mkey] = milieu
            direction["milieux"].append(milieu)
        milieu["bureaux"].append({"unite": feuille["bureau"], "agents": feuille["agents"]})
    return directions


def _titre_niveau(unite, defaut):
    if unite is None:
        return defaut
    return f"{unite.get_niveau_display()} — {unite.nom}"


def _agents_de(bureaux):
    personnes = []
    for bureau in bureaux:
        personnes.extend(bureau["agents"])
    return personnes


def repartition(personnes):
    """Nombre de cadres et d'agents dans un groupe."""
    cadres = sum(1 for agent in personnes if est_cadre(agent))
    return cadres, len(personnes) - cadres


def _nombre(nombre, singulier, pluriel):
    return f"{nombre} {singulier if nombre == 1 else pluriel}"


def _abreviation_grade(agent):
    if not agent.grade_id:
        return "—"
    return agent.grade.abreviation or str(agent.grade)


def _effectif_reparti(personnes):
    cadres, autres = repartition(personnes)
    return f"{_nombre(cadres, 'cadre', 'cadres')}, {_nombre(autres, 'agent', 'agents')}"


def _bloc_effectif(styles, largeur, personnes, titre="EFFECTIF"):
    cadres, autres = repartition(personnes)
    return _total_block(
        styles,
        largeur,
        [("Cadres", str(cadres)), ("Agents", str(autres))],
        titre,
        str(cadres + autres),
    )


def _rubrique(styles, largeur, texte, niveau, effectif):
    """Titre de liste, décalé selon l'emboîtement, avec l'effectif à droite."""
    style = styles["section"] if niveau == 0 else styles["label"]
    retrait = niveau * 6 * mm
    ligne = Table(
        [[_rich(escape(texte), style), _rich(escape(effectif), styles["value"])]],
        colWidths=[largeur - 48 * mm, 48 * mm],
    )
    commandes = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (0, 0), retrait),
        ("LEFTPADDING", (1, 0), (1, 0), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]
    if niveau == 0:
        commandes.append(("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE))
        commandes.append(("TOPPADDING", (0, 0), (-1, -1), 8))
    ligne.setStyle(TableStyle(commandes))
    return ligne


def build_annuaire_pdf(agents, *, site, genere_le):
    """PDF de la liste du personnel, dans l'ordre déclaré puis par nom."""
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=12 * mm,
        bottomMargin=20 * mm,
        title="Liste déclarative par emboîtement",
    )
    largeur = A4[0] - 28 * mm
    fiche = _styled()
    story = [
        _doc_header(
            fiche,
            largeur,
            title="LISTE DÉCLARATIVE PAR EMBOÎTEMENT",
            genere_le=genere_le,
        ),
        Spacer(1, 2.5 * mm),
        _rule(largeur),
        Spacer(1, 4 * mm),
    ]
    if not agents:
        story.append(_p("Aucun agent.", fiche["empty"]))
    for direction in regrouper(agents):
        milieux = direction["milieux"]
        story.append(
            _rubrique(
                fiche,
                largeur,
                _titre_niveau(direction["unite"], "Sans direction"),
                0,
                _effectif_reparti(_agents_de([bureau for milieu in milieux for bureau in milieu["bureaux"]])),
            )
        )
        for milieu in milieux:
            if milieu["unite"] is not None:
                story.append(
                    _rubrique(
                        fiche,
                        largeur,
                        _titre_niveau(milieu["unite"], "Division"),
                        1,
                        _effectif_reparti(_agents_de(milieu["bureaux"])),
                    )
                )
            for bureau in milieu["bureaux"]:
                personnes = bureau["agents"]
                if bureau["unite"] is not None:
                    story.append(
                        _rubrique(
                            fiche,
                            largeur,
                            _titre_niveau(bureau["unite"], "Bureau"),
                            2,
                            _effectif_reparti(personnes),
                        )
                    )
                lignes = [
                    [
                        escape(agent.nom_complet),
                        escape(agent.matricule),
                        escape(_abreviation_grade(agent)),
                    ]
                    for agent in personnes
                ]
                story.append(Spacer(1, 1.5 * mm))
                story.append(
                    _data_table(
                        fiche,
                        ["Nom", "Matricule", "Grade"],
                        lignes,
                        [largeur - 58 * mm, 32 * mm, 26 * mm],
                    )
                )
                story.append(Spacer(1, 2 * mm))
                story.append(_bloc_effectif(fiche, largeur, personnes))
                story.append(Spacer(1, 3 * mm))
    if agents:
        story.append(Spacer(1, 2 * mm))
        story.append(_bloc_effectif(fiche, largeur, agents, "EFFECTIF TOTAL"))

    def _pied(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.4)
        canvas.line(14 * mm, 16 * mm, A4[0] - 14 * mm, 16 * mm)
        canvas.setFillColor(MUTED)
        canvas.setFont(FONT, 8)
        canvas.drawCentredString(A4[0] / 2, 11.5 * mm, f"Généré le {genere_le} — page {doc.page}")
        canvas.setFont(FONT, 7)
        canvas.drawCentredString(A4[0] / 2, 7.5 * mm, site.nom_administration)
        canvas.restoreState()

    document.build(story, onFirstPage=_pied, onLaterPages=_pied)
    buffer.seek(0)
    return buffer
