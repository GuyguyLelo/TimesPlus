"""Liste du personnel regroupée pour l'impression."""

import unicodedata
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import CondPageBreak, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.agents.matricule import format_matricule
from apps.overtime.listes import est_cadre
from apps.reports.services.pdf import (
    FONT,
    FONT_BOLD,
    LINE,
    MUTED,
    _doc_header,
    _p,
    _rich,
    _rule,
    _styled,
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
    """Effectif calé sur les colonnes Nom, Matricule et Grade."""
    cadres, autres = repartition(personnes)
    nom, matricule, grade = _colonnes_tableau(largeur)
    libelle = ParagraphStyle("AnnuaireEffectifLibelle", parent=styles["label"], fontSize=8, leading=10, textColor=_ARDOISE_TEXTE)
    valeur = ParagraphStyle(
        "AnnuaireEffectifValeur",
        parent=styles["value"],
        fontName=FONT,
        fontSize=9,
        leading=11,
        textColor=_MARINE,
    )
    valeur_vide = ParagraphStyle("AnnuaireEffectifVide", parent=valeur, textColor=_ARDOISE)
    total_libelle = ParagraphStyle(
        "AnnuaireEffectifTotal",
        parent=styles["totalLabel"],
        fontName=FONT_BOLD,
        fontSize=9,
        leading=11,
        textColor=_MARINE,
    )
    total_valeur = ParagraphStyle(
        "AnnuaireEffectifTotalValeur",
        parent=styles["totalValue"],
        fontName=FONT_BOLD,
        fontSize=9,
        leading=11,
        textColor=_MARINE,
    )
    lignes = [
        (_rich("Cadres", libelle), _rich(str(cadres), valeur_vide if cadres == 0 else valeur)),
        (_rich("Agents", libelle), _rich(str(autres), valeur_vide if autres == 0 else valeur)),
        (_rich(escape(titre), total_libelle), _rich(str(cadres + autres), total_valeur)),
    ]
    table = Table(
        [[gauche, droite, ""] for gauche, droite in lignes],
        colWidths=[nom, matricule, grade],
    )
    last = len(lignes) - 1
    table.setStyle(TableStyle([
        ("SPAN", (1, 0), (2, 0)),
        ("SPAN", (1, 1), (2, 1)),
        ("SPAN", (1, last), (2, last)),
        ("BACKGROUND", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#F7FAFC")),
        ("BACKGROUND", (0, last), (-1, last), _BLEU_CLAIR),
        ("LINEBEFORE", (0, 0), (0, -1), 2.5, _JAUNE),
        ("LINEABOVE", (0, last), (-1, last), 1.2, _JAUNE),
        ("LINEBELOW", (0, 0), (-1, last - 1), 0.25, LINE),
        ("BOX", (0, 0), (-1, -1), 0.6, _ARDOISE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def _colonnes_tableau(largeur):
    """Largeurs Nom, Matricule et Grade.

    Le nom (nom, postnom et prénom) reste étroit. Le titre de niveau
    suit la même colonne.
    """
    nom = 80 * mm
    matricule = 48 * mm
    grade = 30 * mm
    if nom + matricule + grade > largeur:
        nom = largeur - matricule - grade
    return [nom, matricule, grade]


_MARINE = colors.HexColor("#0C3058")
_BLEU_CLAIR = colors.HexColor("#E8F3FF")
_JAUNE = colors.HexColor("#F7D618")
_OR = colors.HexColor("#C9A227")
_OR_CLAIR = colors.HexColor("#FFF6D0")
_OR_TEXTE = colors.HexColor("#7A5B00")
_ARDOISE = colors.HexColor("#8AA0B8")
_ARDOISE_CLAIR = colors.HexColor("#F4F7FB")
_ARDOISE_TEXTE = colors.HexColor("#3D4A5C")

_STYLE_DIRECTION = ParagraphStyle(
    "AnnuaireDirection",
    fontName=FONT_BOLD,
    fontSize=9,
    leading=11,
    textColor=_MARINE,
)
_STYLE_DIRECTION_EFFECTIF = ParagraphStyle(
    "AnnuaireDirectionEffectif",
    fontName=FONT,
    fontSize=8,
    leading=10,
    alignment=TA_RIGHT,
    textColor=_MARINE,
)
_STYLE_DIVISION = ParagraphStyle(
    "AnnuaireDivision",
    fontName=FONT_BOLD,
    fontSize=8.5,
    leading=11,
    textColor=_OR_TEXTE,
)
_STYLE_BUREAU = ParagraphStyle(
    "AnnuaireBureau",
    fontName=FONT_BOLD,
    fontSize=8,
    leading=10,
    textColor=_ARDOISE_TEXTE,
)
_NIVEAUX = (
    (_STYLE_DIRECTION, _STYLE_DIRECTION_EFFECTIF, _BLEU_CLAIR, _JAUNE),
    (_STYLE_DIVISION, None, _OR_CLAIR, _OR),
    (_STYLE_BUREAU, None, _ARDOISE_CLAIR, _ARDOISE),
)


def _rubrique(styles, largeur, texte, niveau, effectif):
    """Titre aligné sur la colonne Nom, avec une bande propre au niveau."""
    style, effectif_style, fond, barre = _NIVEAUX[niveau]
    if effectif_style is None:
        effectif_style = styles["value"]
    nom, matricule, grade = _colonnes_tableau(largeur)
    ligne = Table(
        [[_rich(escape(texte), style), _rich(escape(effectif), effectif_style), ""]],
        colWidths=[nom, matricule, grade],
    )
    ligne.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("SPAN", (1, 0), (2, 0)),
        ("BACKGROUND", (0, 0), (-1, -1), fond),
        ("LINEBEFORE", (0, 0), (0, -1), 2.5, barre),
        ("LINEBELOW", (0, 0), (-1, -1), 0.8, barre),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3 if niveau == 0 else 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2 if niveau == 0 else 1),
    ]))
    ligne.est_titre = True
    ligne.fond = fond
    return ligne


def _reserve(niveaux):
    """Hauteur minimale d'un titre suivi des premières lignes du tableau."""
    hauteur = 32 * mm
    for niveau in niveaux:
        hauteur += 12 * mm if niveau == 0 else 10 * mm
    return hauteur


def _tableau_agents(fiche, lignes, largeur):
    """Tableau des agents : en-tête bleu clair, matricule à droite, grade en marine."""
    colonnes = _colonnes_tableau(largeur)
    entete = ParagraphStyle(
        "AnnuaireEntete",
        parent=fiche["head"],
        fontName=FONT_BOLD,
        fontSize=8,
        leading=10,
        textColor=_MARINE,
    )
    entete_droit = ParagraphStyle("AnnuaireEnteteDroit", parent=entete, alignment=TA_RIGHT)
    nom = ParagraphStyle(
        "AnnuaireNom",
        parent=fiche["cell"],
        fontName=FONT,
        fontSize=8.5,
        leading=11,
        textColor=_ARDOISE_TEXTE,
    )
    matricule = ParagraphStyle(
        "AnnuaireMatricule",
        parent=fiche["cellRight"],
        fontName=FONT,
        fontSize=8.5,
        leading=11,
        alignment=TA_RIGHT,
        textColor=_MARINE,
    )
    grade = ParagraphStyle(
        "AnnuaireGrade",
        parent=fiche["cell"],
        fontName=FONT_BOLD,
        fontSize=8.5,
        leading=11,
        textColor=_MARINE,
    )
    grade_vide = ParagraphStyle("AnnuaireGradeVide", parent=grade, fontName=FONT, textColor=_ARDOISE)
    donnees = [[_rich("Nom", entete), _rich("Matricule", entete_droit), _rich("Grade", entete)]]
    for nom_agent, matricule_agent, grade_agent in lignes:
        donnees.append([
            _rich(nom_agent, nom),
            _rich(matricule_agent, matricule),
            _rich(grade_agent, grade_vide if grade_agent == "—" else grade),
        ])
    tableau = Table(donnees, colWidths=colonnes, repeatRows=1)
    commandes = [
        ("BACKGROUND", (0, 0), (-1, 0), _BLEU_CLAIR),
        ("LINEBEFORE", (0, 0), (0, -1), 2.5, _JAUNE),
        ("LINEBELOW", (0, 0), (-1, 0), 1.2, _JAUNE),
        ("LINEBEFORE", (2, 0), (2, -1), 0.4, _ARDOISE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (1, 0), (1, -1), 8 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("BOX", (0, 0), (-1, -1), 0.6, _ARDOISE),
    ]
    if len(donnees) > 1:
        commandes.append(("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7FAFC")]))
    if len(donnees) > 2:
        commandes.append(("LINEBELOW", (0, 1), (-1, -2), 0.25, LINE))
    tableau.setStyle(TableStyle(commandes))
    return tableau


def _poser_groupe(story, fiche, largeur, titres, personnes):
    """Pose les titres avec le tableau, jamais seuls en bas de page."""
    if titres:
        story.append(CondPageBreak(_reserve(niveau for _, niveau, _ in titres)))
        for texte, niveau, effectif in titres:
            story.append(_rubrique(fiche, largeur, texte, niveau, effectif))
    lignes = [
        [
            escape(agent.nom_complet),
            escape(format_matricule(agent.matricule)),
            escape(_abreviation_grade(agent)),
        ]
        for agent in personnes
    ]
    story.append(_tableau_agents(fiche, lignes, largeur))
    story.append(Spacer(1, 2 * mm))
    story.append(_bloc_effectif(fiche, largeur, personnes))
    story.append(Spacer(1, 3 * mm))


def lignes_par_grade(agents):
    """Effectif des cadres et des agents, une ligne par grade, sans l'échelon."""
    comptes = {}
    for agent in agents:
        grade = agent.grade if agent.grade_id else None
        cle = None if grade is None else grade.libelle
        ligne = comptes.get(cle)
        if ligne is None:
            ligne = {
                "grade": grade,
                "ordre": grade.ordre if grade is not None else 10**9,
                "cadres": 0,
                "autres": 0,
            }
            comptes[cle] = ligne
        elif grade is not None and grade.ordre < ligne["ordre"]:
            ligne["ordre"] = grade.ordre
        if est_cadre(agent):
            ligne["cadres"] += 1
        else:
            ligne["autres"] += 1
    grades = sorted(
        (item for item in comptes.values() if item["grade"] is not None),
        key=lambda item: (item["ordre"], item["grade"].libelle),
    )
    lignes = [
        (item["grade"].abreviation or item["grade"].code, item["grade"].libelle, item["cadres"], item["autres"])
        for item in grades
    ]
    sans = comptes.get(None)
    if sans is not None:
        lignes.append(("—", "Sans grade", sans["cadres"], sans["autres"]))
    return lignes


def lignes_synthese(agents):
    """Effectif des cadres et des agents par direction, puis par division."""
    lignes = []
    for direction in regrouper(agents):
        milieux = direction["milieux"]
        personnes = _agents_de([bureau for milieu in milieux for bureau in milieu["bureaux"]])
        cadres, autres = repartition(personnes)
        nom = direction["unite"].nom if direction["unite"] is not None else "Sans direction"
        lignes.append((0, nom, cadres, autres))
        details = [milieu for milieu in milieux if milieu["unite"] is not None or len(milieux) > 1]
        for milieu in details:
            groupe = _agents_de(milieu["bureaux"])
            part_cadres, part_autres = repartition(groupe)
            titre = milieu["unite"].nom if milieu["unite"] is not None else "Rattachés à la direction"
            lignes.append((1, titre, part_cadres, part_autres))
    return lignes


def _tableau_comptes(fiche, colonnes, entetes, lignes, valeurs):
    """Tableau d'effectifs : en-tête bleu clair, lignes alternées, total en bas."""
    grade = ParagraphStyle(
        "SyntheseGrade",
        parent=fiche["cell"],
        fontName=FONT_BOLD,
        fontSize=9,
        leading=12,
        textColor=_MARINE,
    )
    nombre = ParagraphStyle(
        "SyntheseNombre",
        parent=fiche["value"],
        fontName=FONT,
        fontSize=9,
        leading=12,
        textColor=_MARINE,
    )
    nombre_vide = ParagraphStyle(
        "SyntheseNombreVide",
        parent=nombre,
        textColor=_ARDOISE,
    )
    nombre_fort = ParagraphStyle(
        "SyntheseNombreFort",
        parent=fiche["totalValue"],
        fontName=FONT_BOLD,
        fontSize=9,
        leading=12,
        textColor=_MARINE,
    )
    unite = ParagraphStyle("SyntheseUnite", parent=fiche["cell"], fontName=FONT, fontSize=9, leading=12, textColor=_ARDOISE_TEXTE)
    total = ParagraphStyle(
        "SyntheseTotal",
        parent=fiche["totalLabel"],
        fontName=FONT_BOLD,
        fontSize=9,
        leading=12,
        textColor=_MARINE,
    )
    entete = ParagraphStyle(
        "SyntheseEntete",
        parent=fiche["head"],
        fontName=FONT_BOLD,
        fontSize=8,
        leading=10,
        textColor=_MARINE,
    )
    entete_droit = ParagraphStyle("SyntheseEnteteDroit", parent=entete, alignment=TA_RIGHT)
    total_cadres = sum(item[-2] for item in lignes)
    total_autres = sum(item[-1] for item in lignes)
    donnees = [[_rich(texte, entete_droit if droit else entete) for texte, droit in entetes]]
    for ligne in lignes:
        donnees.append(valeurs(ligne, grade, unite, nombre, nombre_vide))
    donnees.append([
        _rich("Total", total),
        *([""] * (len(colonnes) - 4)),
        _rich(str(total_cadres), nombre_fort),
        _rich(str(total_autres), nombre_fort),
        _rich(str(total_cadres + total_autres), nombre_fort),
    ])
    tableau = Table(donnees, colWidths=colonnes, repeatRows=1)
    commandes = [
        ("BACKGROUND", (0, 0), (-1, 0), _BLEU_CLAIR),
        ("BACKGROUND", (0, -1), (-1, -1), _BLEU_CLAIR),
        ("LINEBEFORE", (0, 0), (0, -1), 2.5, _JAUNE),
        ("LINEBELOW", (0, 0), (-1, 0), 1.2, _JAUNE),
        ("LINEABOVE", (0, -1), (-1, -1), 1.2, _JAUNE),
        ("LINEBEFORE", (2, 0), (2, -1), 0.4, _ARDOISE),
        ("LINEBEFORE", (-1, 0), (-1, -1), 0.4, _ARDOISE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("BOX", (0, 0), (-1, -1), 0.6, _ARDOISE),
        ("SPAN", (0, -1), (len(colonnes) - 4, -1)),
    ]
    if lignes:
        commandes.append(("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#F7FAFC")]))
        commandes.append(("LINEBELOW", (0, 1), (-1, -2), 0.25, LINE))
    tableau.setStyle(TableStyle(commandes))
    return tableau


def signataire_de(agents):
    """Le directeur de la direction couverte par l'état."""
    from apps.agents.models import Agent

    vus = set()
    directions = []
    for agent in agents:
        if not agent.service_id:
            continue
        direction, _milieu, _bureau = echelon(agent.service)
        if direction is not None and direction.pk not in vus:
            vus.add(direction.pk)
            directions.append(direction)
    if len(directions) != 1:
        actives = list(
            Service.objects.filter(niveau=Service.Niveau.DIRECTION, actif=True).order_by("code")[:2]
        )
        if len(actives) != 1:
            return None
        direction = actives[0]
    else:
        direction = directions[0]
    return (
        Agent.objects.filter(actif=True, fonction__code="DIR", service=direction)
        .order_by("ordre", "nom", "postnom", "prenom")
        .first()
    )


def _nom_signataire(agent):
    """Nom et postnom en capitales, prénom tel qu'il est saisi."""
    identite = " ".join(part.strip().upper() for part in (agent.nom, agent.postnom) if part and part.strip())
    prenom = (agent.prenom or "").strip()
    return " ".join(part for part in (identite, prenom) if part)


def _bloc_signature(largeur, signataire):
    """Nom du directeur, aligné à droite, avec l'espace pour signer."""
    largeur_bloc = 72 * mm
    qualite = ParagraphStyle(
        "AnnuaireSignataireQualite",
        fontName=FONT_BOLD,
        fontSize=9,
        leading=12,
        alignment=TA_CENTER,
        textColor=_MARINE,
    )
    nom = ParagraphStyle(
        "AnnuaireSignataireNom",
        fontName=FONT_BOLD,
        fontSize=10,
        leading=13,
        alignment=TA_CENTER,
        textColor=_MARINE,
    )
    filet = Table([[""]], colWidths=[largeur_bloc], rowHeights=[0.8])
    filet.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _MARINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    contenu = [
        _rich("Le Directeur", qualite),
        Spacer(1, 16 * mm),
        filet,
        Spacer(1, 1.5 * mm),
        _rich(escape(_nom_signataire(signataire)), nom),
    ]
    bloc = Table([[contenu]], colWidths=[largeur_bloc])
    bloc.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    coquille = Table([["", bloc]], colWidths=[largeur - largeur_bloc, largeur_bloc])
    coquille.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return coquille


def _poser_signature(story, largeur, agents):
    signataire = signataire_de(agents)
    if signataire is None:
        return
    story.append(Spacer(1, 12 * mm))
    story.append(_bloc_signature(largeur, signataire))


def build_synthese_pdf(agents, *, site, genere_le):
    """PDF du tableau des cadres et des agents, par grade."""
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=12 * mm,
        bottomMargin=20 * mm,
        title="Tableau synthèse",
    )
    largeur = A4[0] - 28 * mm
    fiche = _styled()
    entetes_comptes = [("Cadres", True), ("Agents", True), ("Total", True)]
    grades = lignes_par_grade(agents)
    colonnes_grades = [22 * mm, largeur - 94 * mm, 24 * mm, 24 * mm, 24 * mm]
    tableau_grades = _tableau_comptes(
        fiche,
        colonnes_grades,
        [("Grade", False), ("Libellé", False), *entetes_comptes],
        grades,
        lambda ligne, style_grade, style_nom, style_nb, style_vide: [
            _rich(escape(ligne[0]), style_grade),
            _rich(escape(ligne[1]), style_nom),
            _rich(str(ligne[2]), style_vide if ligne[2] == 0 else style_nb),
            _rich(str(ligne[3]), style_vide if ligne[3] == 0 else style_nb),
            _rich(str(ligne[2] + ligne[3]), style_vide if ligne[2] + ligne[3] == 0 else style_nb),
        ],
    )
    story = [
        _doc_header(fiche, largeur, title="TABLEAU SYNTHÈSE", genere_le=genere_le),
        Spacer(1, 2.5 * mm),
        _rule(largeur),
        Spacer(1, 4 * mm),
        _p("Effectif par grade.", fiche["subtitle"]),
        Spacer(1, 3 * mm),
        tableau_grades,
    ]
    _poser_signature(story, largeur, agents)

    def _pied(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.4)
        canvas.line(14 * mm, 16 * mm, A4[0] - 14 * mm, 16 * mm)
        canvas.setFillColor(MUTED)
        canvas.setFont(FONT, 8)
        canvas.drawCentredString(A4[0] / 2, 11.5 * mm, f"Page {doc.page}")
        canvas.setFont(FONT, 7)
        canvas.drawCentredString(A4[0] / 2, 7.5 * mm, site.nom_administration)
        canvas.restoreState()

    document.build(story, onFirstPage=_pied, onLaterPages=_pied)
    buffer.seek(0)
    return buffer


def build_annuaire_pdf(agents, *, site, genere_le, trace=None):
    """PDF de la liste du personnel, dans l'ordre déclaré puis par nom."""
    buffer = BytesIO()

    class _Doc(SimpleDocTemplate):
        def afterFlowable(self, flowable):
            if trace is None or not isinstance(flowable, Table):
                return
            trace.append((self.page, getattr(flowable, "est_titre", False)))

    document = _Doc(
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
        titre_direction = (
            _titre_niveau(direction["unite"], "Sans direction"),
            0,
            _effectif_reparti(_agents_de([bureau for milieu in milieux for bureau in milieu["bureaux"]])),
        )
        direction_posee = False
        for milieu in milieux:
            titre_milieu = None
            if milieu["unite"] is not None:
                titre_milieu = (
                    _titre_niveau(milieu["unite"], "Division"),
                    1,
                    _effectif_reparti(_agents_de(milieu["bureaux"])),
                )
            milieu_pose = False
            for bureau in milieu["bureaux"]:
                personnes = bureau["agents"]
                titres = []
                if not direction_posee:
                    titres.append(titre_direction)
                    direction_posee = True
                if titre_milieu is not None and not milieu_pose:
                    titres.append(titre_milieu)
                    milieu_pose = True
                if bureau["unite"] is not None:
                    titres.append((
                        _titre_niveau(bureau["unite"], "Bureau"),
                        2,
                        _effectif_reparti(personnes),
                    ))
                _poser_groupe(story, fiche, largeur, titres, personnes)
    if agents:
        story.append(Spacer(1, 2 * mm))
        story.append(_bloc_effectif(fiche, largeur, agents, "EFFECTIF TOTAL"))
    _poser_signature(story, largeur, agents)

    def _pied(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.4)
        canvas.line(14 * mm, 16 * mm, A4[0] - 14 * mm, 16 * mm)
        canvas.setFillColor(MUTED)
        canvas.setFont(FONT, 8)
        canvas.drawCentredString(A4[0] / 2, 11.5 * mm, f"Page {doc.page}")
        canvas.setFont(FONT, 7)
        canvas.drawCentredString(A4[0] / 2, 7.5 * mm, site.nom_administration)
        canvas.restoreState()

    document.build(story, onFirstPage=_pied, onLaterPages=_pied)
    buffer.seek(0)
    return buffer
