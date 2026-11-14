"""Inventaire d'un livre déjà scanné en PDF : quelles pages imprimées manquent, lesquelles sont en double.

Lecture locale, gratuite : Tesseract lit seulement le numéro imprimé en haut ou en bas de chaque page
(bandes de 9 % de la hauteur), sur une image à 150 points par pouce. Rien n'est envoyé en ligne.
Le PDF est lu page par page : un gros fichier (plusieurs centaines de Mo) ne remplit pas la mémoire.

Usage : déposer le PDF dans livre/ puis « docker compose run --rm inventaire ».
Sortie : resultats/inventaire.html (lisible) et resultats/inventaire.csv (une ligne par page du PDF).
"""
from __future__ import annotations

import csv
import html
import io
import os
import re
import subprocess
from collections import Counter
from pathlib import Path

from PIL import Image, ImageOps

RACINE = Path(os.environ.get("SONDE_RACINE", "/sonde"))
LIVRE = RACINE / "livre"
RESULTATS = RACINE / "resultats"
DPI = int(os.environ.get("INVENTAIRE_DPI", "150"))
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
    """Nombres de 1 à 4 chiffres lus dans une bande, du plus sûr au moins sûr.

    Tesseract lit mal un chiffre isolé au milieu du blanc : on repère d'abord les taches d'encre de la bande
    (groupes de colonnes encrées), puis chaque tache est lue seule, agrandie, comme un mot (psm 8).
    """
    gris = ImageOps.autocontrast(img.convert("L"))
    import numpy as np

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
        lus = _tesseract_chiffres(bout, 8) or _tesseract_chiffres(bout, 7)
        trouves += lus
    return [n for _, n in sorted(trouves, reverse=True)]


def lire_numero(page_img: Image.Image) -> int | None:
    h = page_img.height
    candidats = _nombres(page_img.crop((0, h - int(h * BANDE), page_img.width, h)))
    candidats += _nombres(page_img.crop((0, 0, page_img.width, int(h * BANDE))))
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
        accords = sum(1 for j, m in voisins if abs((m - n) - (j - i)) <= 3)
        if accords == 0:
            propres[i] = None
    return propres


def analyser(numeros: list[int | None]) -> dict:
    """Pages manquantes, en double, sans numéro.

    Entre deux numéros lus a (page i du PDF) et b (page j), il devrait y avoir b - a - 1 pages ; le PDF en a
    j - i - 1. Si le PDF en a autant, les pages sans numéro lu comblent le trou : rien ne manque. S'il en a
    moins, il en manque la différence : « sûres » quand aucune page sans numéro n'est dans le trou, sinon
    « à vérifier » (on sait combien manquent, pas lesquelles).
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
                a_verifier.append({"entre": (a, b), "manquent": attendu - present})
    sans_numero = [i + 1 for i, n in enumerate(numeros) if n is None]
    return {"premier": min((n for _, n in lus), default=None), "dernier": max((n for _, n in lus), default=None),
            "manquants": surs, "a_verifier": a_verifier, "doubles": doubles, "sans_numero": sans_numero}


def _plages(nombres: list[int]) -> str:
    if not nombres:
        return "aucune"
    morceaux, debut, prec = [], nombres[0], nombres[0]
    for n in nombres[1:] + [None]:
        if n is not None and n == prec + 1:
            prec = n
            continue
        morceaux.append(f"{debut}" if debut == prec else f"{debut} à {prec}")
        if n is not None:
            debut = prec = n
    return ", ".join(morceaux)


def inventaire() -> dict:
    import pypdfium2 as pdfium

    pdfs = sorted(LIVRE.glob("*.pdf"))
    if not pdfs:
        raise SystemExit("Aucun PDF dans livre/ : y déposer le PDF du livre.")
    RESULTATS.mkdir(exist_ok=True)
    pdf_chemin = pdfs[0]
    pdf = pdfium.PdfDocument(str(pdf_chemin))
    total = len(pdf)
    print(f"{pdf_chemin.name} : {total} pages dans le PDF")
    bruts = []
    for i in range(total):
        img = pdf[i].render(scale=DPI / 72).to_pil()
        n = lire_numero(img)
        bruts.append(n)
        if (i + 1) % 25 == 0 or i + 1 == total:
            print(f"  {i + 1}/{total} pages lues")
    pdf.close()
    numeros = corriger(bruts)
    bilan = analyser(numeros)
    with open(RESULTATS / "inventaire.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["page du PDF", "numéro imprimé lu", "numéro gardé"])
        for i, (b, n) in enumerate(zip(bruts, numeros), start=1):
            w.writerow([i, "" if b is None else b, "" if n is None else n])
    lignes = "".join(
        f"<tr><td>{i}</td><td>{'' if n is None else n}</td><td>{'' if b is None or b == n else f'lu {b}, écarté'}</td></tr>"
        for i, (b, n) in enumerate(zip(bruts, numeros), start=1))
    page = f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8"><title>Inventaire — {html.escape(pdf_chemin.name)}</title>
<style>body{{background:#151311;color:#f2ece2;font:15px/1.5 Inter,system-ui,sans-serif;margin:28px}}h1{{font-weight:300}}
.bloc{{background:#1f1c19;border:1px solid #312c27;border-radius:12px;padding:14px 18px;margin:12px 0;max-width:900px}}
b{{color:#c4a07a}}table{{border-collapse:collapse}}td,th{{padding:3px 12px;border-bottom:1px solid #312c27}}</style></head><body>
<h1>Inventaire de {html.escape(pdf_chemin.name)}</h1>
<div class="bloc">{total} pages dans le PDF ; numéros imprimés lus de <b>{bilan['premier']}</b> à <b>{bilan['dernier']}</b>.</div>
<div class="bloc"><b>Pages manquantes</b> ({len(bilan['manquants'])}) : {_plages(bilan['manquants'])}</div>
<div class="bloc"><b>À vérifier</b> : {'aucun trou douteux' if not bilan['a_verifier'] else '; '.join(f"entre les pages {v['entre'][0]} et {v['entre'][1]}, il manque {v['manquent']} page(s)" for v in bilan['a_verifier'])}</div>
<div class="bloc"><b>Pages en double</b> : {_plages(bilan['doubles'])}</div>
<div class="bloc">Pages du PDF sans numéro lu ({len(bilan['sans_numero'])}) : {_plages(bilan['sans_numero'])}<br>
<small>Normal pour la couverture, les pages de titre, les pages en photo pleine page. Une page manquante annoncée juste à côté
d'une page sans numéro lu est peut-être là : à vérifier dans le PDF.</small></div>
<table><tr><th>Page du PDF</th><th>Numéro imprimé</th><th></th></tr>{lignes}</table></body></html>"""
    (RESULTATS / "inventaire.html").write_text(page, encoding="utf-8")
    print(f"Manquantes : {_plages(bilan['manquants'])}")
    for v in bilan["a_verifier"]:
        print(f"À vérifier : entre {v['entre'][0]} et {v['entre'][1]}, il manque {v['manquent']} page(s)")
    print(f"En double : {_plages(bilan['doubles'])}")
    print("Détail : resultats/inventaire.html")
    return bilan


if __name__ == "__main__":
    inventaire()
