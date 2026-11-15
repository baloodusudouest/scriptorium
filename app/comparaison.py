"""Contre-lecture (0.3.1) : comparer le texte lu par Mistral à celui lu par Marker sur le PC.

Constat de la sonde : là où Mistral se trompe de façon plausible (« mari » pour « marc »), Marker lit juste,
et inversement. Un mot qui diffère entre les deux lectures devient un mot à relire, sans relire toute la page.

Seules les substitutions courtes comptent (1 à 4 mots de chaque côté) : la mise en forme, l'ordre des blocs,
les lettres de marge et les numéros de page diffèrent beaucoup d'un moteur à l'autre et ne disent rien
de la justesse des mots. Si les deux lectures se ressemblent trop peu (accord < 0,5), la page entière
est signalée : l'un des deux moteurs a sans doute mal lu la page.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

# Un mot : lettres et chiffres, avec apostrophes et traits d'union intérieurs (« aujourd'hui », « porte-avions »),
# ou un nombre décimal (« 2,5 »). La ponctuation est ignorée.
_MOT = re.compile(r"\d+(?:[.,]\d+)?|[^\W\d_]+(?:['’\-][^\W\d_]+)*", re.UNICODE)
# Ce qui n'est pas du texte lu : images Markdown, balises HTML, liens (on garde le texte du lien)
_HORS_TEXTE = re.compile(r"!\[[^\]]*\]\([^)]*\)|<[^>]+>|\]\([^)]*\)")
# Ligne qui n'est qu'un numéro de page ou une lettre de marge (index alphabétique) : ignorée
_LIGNE_PARASITE = re.compile(r"^[ \t]*(?:\d{1,4}|[A-Z])[ \t]*$", re.MULTILINE)
_CESURE = re.compile(r"(\w)-[ \t]*\n[ \t]*(\w)")

MAX_MOTS = 4          # longueur maximale d'une substitution retenue (de chaque côté)
ACCORD_FAIBLE = 0.5   # en dessous : la page entière est à relire
MAX_DOUTES = 80       # au-delà, la liste n'aide plus : la page est de toute façon à relire


def _masquer(texte: str) -> str:
    """Remplace ce qui n'est pas du texte lu par des espaces : les positions dans le texte restent justes."""
    blanc = lambda m: " " * len(m.group(0))  # noqa: E731
    return _LIGNE_PARASITE.sub(blanc, _HORS_TEXTE.sub(blanc, texte))


def _norme(mot: str) -> str:
    return mot.lower().replace("’", "'").replace("œ", "oe").replace("æ", "ae").replace(",", ".")


def mots_positionnes(texte: str) -> list[tuple[str, int, int]]:
    """Les mots du texte avec leur début et leur fin (positions dans le texte d'origine)."""
    return [(m.group(0), m.start(), m.end()) for m in _MOT.finditer(_masquer(texte))]


def mots(texte: str) -> list[str]:
    texte = _CESURE.sub(r"\1\2", texte)
    return [m.group(0) for m in _MOT.finditer(_masquer(texte))]


def comparer(texte_mistral: str, texte_marker: str) -> dict:
    """Renvoie {"accord": 0..1, "doutes": [{"lu", "propose", "debut", "fin"}], "page_entiere": bool}.

    « debut » et « fin » sont des positions dans texte_mistral : l'écran de relecture s'en sert pour
    sélectionner le mot dans la zone de texte. « lu » est le texte de Mistral, « propose » celui de Marker.
    """
    a = mots_positionnes(texte_mistral)
    b = mots(texte_marker)
    na, nb = [_norme(m[0]) for m in a], [_norme(m) for m in b]
    if not na and not nb:
        return {"accord": 1.0, "doutes": [], "page_entiere": False}
    sm = SequenceMatcher(None, na, nb, autojunk=False)
    accord = round(sm.ratio(), 3)
    doutes = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op != "replace" or not (0 < i2 - i1 <= MAX_MOTS and 0 < j2 - j1 <= MAX_MOTS):
            continue
        debut, fin = a[i1][1], a[i2 - 1][2]
        doutes.append({"lu": texte_mistral[debut:fin], "propose": " ".join(b[j1:j2]), "debut": debut, "fin": fin})
        if len(doutes) >= MAX_DOUTES:
            break
    return {"accord": accord, "doutes": doutes, "page_entiere": accord < ACCORD_FAIBLE}
