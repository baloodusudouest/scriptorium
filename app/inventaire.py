"""Lecture des numéros imprimés et inventaire des pages (manquantes, à vérifier, en double, sans numéro).

Lecture locale, gratuite : Tesseract lit seulement le bas et le haut de chaque page (bandes de 9 % de la
hauteur). Tesseract lit mal un chiffre isolé au milieu du blanc : on repère d'abord les taches d'encre de la
bande, puis chaque tache est lue seule, agrandie. Repris de la sonde (sonde/outils/inventaire.py).
"""
from __future__ import annotations

import io
import re
import shutil
import subprocess
from collections import Counter

import numpy as np
from PIL import Image, ImageOps

BANDE = 0.09


def _tesseract_chiffres(img: Image.Image, psm: int) -> list[tuple[float, int]]:
    tampon = io.BytesIO()
    img.save(tampon, "PNG")
    r = subprocess.run(["tesseract", "stdin", "stdout", "--psm", str(psm), "-c", "tessedit_char_whitelist=0123456789", "tsv"],
                       input=tampon.getvalue(), capture_output=True, timeout=60)
    trouves = []
    for ligne in r.stdout.decode("utf-8", "replace").splitlines()[1:]:
        champs = ligne.split("\t")
        if len(champs) < 12:
            continue
        texte = champs[11].strip()
        try:
            conf = float(champs[10] or -1)
        except ValueError:
            continue
        if re.fullmatch(r"\d{1,4}", texte) and conf >= 0:
            trouves.append((conf, int(texte)))
    return trouves


def _nombres(img: Image.Image) -> list[int]:
    gris = ImageOps.autocontrast(img.convert("L"))
    g = np.asarray(gris)
    encre = g < 128
    colonnes = encre.any(axis=0)
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
    trouves: list[tuple[float, int]] = []
    for a, b in taches:
        if b - a > g.shape[1] * 0.25:      # une ligne de texte entière : pas un numéro de page
            continue
        lignes = np.flatnonzero(encre[:, a:b].any(axis=1))
        if not len(lignes):
            continue
        y0, y1 = lignes[0], lignes[-1] + 1
        if (b - a) > 3.5 * (y1 - y0):      # plus large qu'un nombre de 4 chiffres : un mot (titre courant)
            continue
        m = max(6, (y1 - y0) // 2)
        bout = gris.crop((max(0, a - m), max(0, y0 - m), min(gris.width, b + m), min(gris.height, y1 + m)))
        bout = bout.resize((bout.width * 3, bout.height * 3))
        trouves += _tesseract_chiffres(bout, 8) or _tesseract_chiffres(bout, 7)
    return [n for _, n in sorted(trouves, reverse=True)]


def lire_numero(page: Image.Image) -> int | None:
    """Numéro imprimé en bas, sinon en haut de la page ; None si rien de lisible (ou Tesseract absent)."""
    if not shutil.which("tesseract"):
        return None
    h = page.height
    candidats = _nombres(page.crop((0, h - int(h * BANDE), page.width, h)))
    candidats += _nombres(page.crop((0, 0, page.width, int(h * BANDE))))
    return candidats[0] if candidats else None


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
