"""Lecture des numéros imprimés et inventaire des pages (manquantes, à vérifier, en double, sans numéro).

Lecture locale, gratuite : Tesseract lit seulement la dernière ligne d'encre du bas de la page (sinon la première
du haut). Chaque tache d'encre de cette ligne est lue seule, agrandie, et un nombre n'est gardé que si une
lecture libre (sans liste blanche de chiffres) le confirme. Repris de la sonde (sonde/outils/inventaire.py).
"""
from __future__ import annotations

import io
import re
import shutil
import subprocess
from collections import Counter

import numpy as np
from PIL import Image, ImageOps

BANDE = 0.12
# Lettres que Tesseract confond avec des chiffres quand on le laisse lire librement
_SOSIES = str.maketrans({"l": "1", "I": "1", "|": "1", "O": "0", "o": "0"})


def _tesseract(img: Image.Image, psm: int, chiffres: bool) -> list[tuple[float, str]]:
    tampon = io.BytesIO()
    img.save(tampon, "PNG")
    commande = ["tesseract", "stdin", "stdout", "--psm", str(psm)]
    if chiffres:
        commande += ["-c", "tessedit_char_whitelist=0123456789"]
    r = subprocess.run(commande + ["tsv"], input=tampon.getvalue(), capture_output=True, timeout=60)
    lus = []
    for ligne in r.stdout.decode("utf-8", "replace").splitlines()[1:]:
        champs = ligne.split("\t")
        if len(champs) < 12 or not champs[11].strip():
            continue
        try:
            lus.append((float(champs[10] or -1), champs[11].strip()))
        except ValueError:
            continue
    return lus


def _lire_tache(bout: Image.Image) -> int | None:
    """Un numéro, seulement si la lecture libre le confirme : avec la liste blanche de chiffres, Tesseract
    transforme n'importe quelle lettre en chiffre (le « Z » d'un index de marge devenait « 2 »)."""
    libre = "".join(t for _, t in _tesseract(bout, 8, False)).translate(_SOSIES).strip(".,-–—()[]· ")
    if not re.fullmatch(r"\d{1,4}", libre):
        return None
    force = [t for _, t in _tesseract(bout, 8, True) if re.fullmatch(r"\d{1,4}", t)]
    return int(libre) if not force or force[0] == libre else None


def _lignes(encre: np.ndarray) -> list[tuple[int, int]]:
    """Lignes d'encre (début, fin) d'une bande, de haut en bas."""
    rangs = encre.any(axis=1)
    lignes, debut, vide = [], None, 0
    for y, r in enumerate(list(rangs) + [False] * 4):
        if r:
            if debut is None:
                debut = y
            vide = 0
        elif debut is not None:
            vide += 1
            if vide > 3:
                lignes.append((debut, y - vide + 1))
                debut, vide = None, 0
    return [(a, b) for a, b in lignes if b - a >= 4]   # poussières écartées


def _nombre_de_bande(bande: Image.Image, du_bas: bool) -> int | None:
    """Le numéro de page est la ligne d'encre la plus basse (bande du bas) ou la plus haute (bande du haut).
    Dans cette ligne, chaque tache d'encre est lue seule, agrandie, puis confirmée par une lecture libre."""
    gris = ImageOps.autocontrast(bande.convert("L"))
    g = np.asarray(gris)
    encre = g < 128
    # Bords noirs du scan (au-delà de la page) : ce n'est pas de l'encre
    encre[:, encre.mean(axis=0) > 0.5] = False
    lignes = _lignes(encre)
    if not lignes:
        return None
    y0, y1 = lignes[-1] if du_bas else lignes[0]
    colonnes = encre[y0:y1].any(axis=0)
    ecart = max(4, g.shape[1] // 40)
    taches, debut, vide = [], None, 0
    for x, c in enumerate(list(colonnes) + [False] * (ecart + 1)):
        if c:
            if debut is None:
                debut = x
            vide = 0
        elif debut is not None:
            vide += 1
            if vide > ecart:
                taches.append((debut, x - vide + 1))
                debut, vide = None, 0
    hauteur = y1 - y0
    courtes = [(a, b) for a, b in taches if (b - a) <= 3.5 * hauteur]   # plus large : un mot, pas un nombre
    # Une ligne de texte (plusieurs mots, ou un bloc large de 30 % de la page) n'est pas une ligne de numéro : la lettre « Z » d'un index de marge,
    # posée à côté de la dernière ligne du texte, se lit « 2 » même sans liste blanche.
    if len(courtes) > 3 or any(b - a > 0.3 * g.shape[1] for a, b in taches):
        return None
    for a, b in courtes:
        m = max(6, hauteur // 2)
        bout = gris.crop((max(0, a - m), max(0, y0 - m), min(gris.width, b + m), min(gris.height, y1 + m)))
        bout = bout.resize((bout.width * 3, bout.height * 3))
        n = _lire_tache(bout)
        if n is not None:
            return n
    return None


def lire_numero(page: Image.Image) -> int | None:
    """Numéro imprimé en bas, sinon en haut de la page ; None si rien de lisible (ou Tesseract absent)."""
    if not shutil.which("tesseract"):
        return None
    h = page.height
    n = _nombre_de_bande(page.crop((0, h - int(h * BANDE), page.width, h)), du_bas=True)
    if n is None:
        n = _nombre_de_bande(page.crop((0, 0, page.width, int(h * BANDE))), du_bas=False)
    return n


def corriger(numeros: list[int | None]) -> list[int | None]:
    """Écarte les lectures aberrantes : un numéro doit suivre la pente de ses voisins (± 3)."""
    propres = list(numeros)
    for i, n in enumerate(numeros):
        if n is None:
            continue
        voisins = [(j, numeros[j]) for j in range(max(0, i - 4), min(len(numeros), i + 5)) if j != i and numeros[j] is not None]
        if len(voisins) < 2:
            continue
        if not any(abs((m - n) - (j - i)) <= 3 for j, m in voisins):
            propres[i] = None
    return propres


def analyser(numeros: list[int | None]) -> dict:
    """Entre deux numéros lus a (place i) et b (place j), il devrait y avoir b - a - 1 pages ; il y en a j - i - 1.

    Moins de pages qu'attendu : il en manque la différence, « sûres » si aucune page sans numéro n'est dans le
    trou, sinon « à vérifier » (on sait combien manquent, pas lesquelles). Les places sont celles de la liste
    reçue (pages écartées déjà retirées).
    """
    lus = [(i, n) for i, n in enumerate(numeros) if n is not None]
    doubles = sorted(n for n, c in Counter(n for _, n in lus).items() if c > 1)
    surs: list[int] = []
    a_verifier: list[dict] = []
    for (i, a), (j, b) in zip(lus, lus[1:]):
        if b <= a:
            continue
        attendu, present = b - a - 1, j - i - 1
        if attendu > present:
            if present == 0:
                surs.extend(range(a + 1, b))
            else:
                a_verifier.append({"entre": [a, b], "manquent": attendu - present})
    return {"premier": min((n for _, n in lus), default=None), "dernier": max((n for _, n in lus), default=None),
            "manquantes": surs, "a_verifier": a_verifier, "doubles": doubles,
            "sans_numero": [i for i, n in enumerate(numeros) if n is None]}
