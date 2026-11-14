"""Prépare les pages déposées dans pages/ : une image PNG par page de livre dans pages_prep/.

Pour chaque fichier :
1. PDF : chaque page rendue à 300 points par pouce. Photo (JPEG, PNG, HEIC, TIFF) : remise droite selon l'EXIF.
2. Sens de lecture : Tesseract lit un extrait de l'image dans les quatre sens ; le sens où il reconnaît
   le plus de mots sûrs l'emporte. Une photo prise téléphone en hauteur, livre ouvert en largeur, est ainsi
   remise à l'endroit.
3. Recadrage sur le papier : la table, les objets autour et les doigts sont retirés autant que possible.
4. Double page : si l'image est nettement plus large que haute, elle est coupée au pli (la bande la plus
   sombre près du milieu), en « -g » (page de gauche) et « -d » (page de droite).
Pas de redressement de la courbure ici.

Réglages (fichier .env) : SONDE_SENS=non (ne pas chercher le sens), SONDE_RECADRER=non, SONDE_COUPER=non.
"""
from __future__ import annotations

import csv
import io
import os
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

try:  # photos HEIC de l'iPhone
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:  # pragma: no cover
    pass

RACINE = Path(os.environ.get("SONDE_RACINE", "/sonde"))
ENTREE = RACINE / "pages"
PREP = RACINE / "pages_prep"
IMAGES = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".tif", ".tiff", ".webp"}
DPI = 300


def _actif(nom: str) -> bool:
    return os.environ.get(nom, "oui").strip().lower() not in ("non", "0", "false", "no")


# ---------------------------------------------------------------- sens de lecture

def _mots_surs(img: Image.Image) -> int:
    """Nombre de mots de 3 lettres ou plus que Tesseract lit avec une confiance d'au moins 70 %."""
    tampon = io.BytesIO()
    img.save(tampon, "PNG")
    r = subprocess.run(["tesseract", "stdin", "stdout", "-l", "fra", "--psm", "3", "tsv"],
                       input=tampon.getvalue(), capture_output=True, timeout=120)
    if r.returncode != 0:
        return 0
    lignes = csv.DictReader(io.StringIO(r.stdout.decode("utf-8", "replace")), delimiter="\t", quoting=csv.QUOTE_NONE)
    n = 0
    for l in lignes:
        try:
            if float(l.get("conf") or -1) >= 70 and sum(c.isalpha() for c in (l.get("text") or "")) >= 3:
                n += 1
        except ValueError:
            continue
    return n


def trouver_sens(img: Image.Image) -> int:
    """Angle (0, 90, 180, 270, sens inverse des aiguilles d'une montre, comme Image.rotate) qui remet le texte droit."""
    if not shutil.which("tesseract"):
        return 0
    petit = img.copy()
    petit.thumbnail((2000, 2000))
    w, h = petit.size
    extrait = petit.crop((int(w * 0.15), int(h * 0.15), int(w * 0.85), int(h * 0.85))).convert("L")
    scores = {a: _mots_surs(extrait.rotate(a, expand=True)) for a in (0, 90, 180, 270)}
    meilleur = max(scores, key=scores.get)
    return meilleur if scores[meilleur] > 0 else 0


# ---------------------------------------------------------------- recadrage sur le papier

def _plus_longue_suite(vrai: np.ndarray) -> tuple[int, int]:
    """Début et fin (exclue) de la plus longue suite de True."""
    meilleur, debut, cur = (0, len(vrai)), None, 0
    longueur_max = 0
    for i, v in enumerate(list(vrai) + [False]):
        if v and debut is None:
            debut = i
        elif not v and debut is not None:
            if i - debut > longueur_max:
                longueur_max, meilleur = i - debut, (debut, i)
            debut = None
    return meilleur if longueur_max else (0, len(vrai))


def _seuil_otsu(gris: np.ndarray) -> float:
    hist = np.bincount(gris.ravel(), minlength=256).astype(float)
    total, somme = hist.sum(), (hist * np.arange(256)).sum()
    meilleur, seuil, w0, s0 = 0.0, 128, 0.0, 0.0
    for t in range(256):
        w0 += hist[t]
        if w0 == 0 or w0 == total:
            continue
        s0 += t * hist[t]
        m0, m1 = s0 / w0, (somme - s0) / (total - w0)
        var = w0 * (total - w0) * (m0 - m1) ** 2
        if var > meilleur:
            meilleur, seuil = var, t
    return seuil


def _boucher(vrai: np.ndarray, trou_max: int) -> np.ndarray:
    """Rebouche les trous courts (le pli d'une double page, une illustration sombre) dans une suite de True."""
    v = vrai.copy()
    idx = np.flatnonzero(v)
    if len(idx) < 2:
        return v
    for a, b in zip(idx[:-1], idx[1:]):
        if 1 < b - a <= trou_max:
            v[a:b] = True
    return v


def _masque_papier(img: Image.Image) -> tuple[np.ndarray, float, float]:
    """Pixels du papier (clairs et peu colorés) sur une réduction de l'image, et le facteur d'échelle."""
    petit = img.convert("RGB")
    petit.thumbnail((800, 800))
    rgb = np.asarray(petit).astype(float)
    gris = rgb.mean(axis=2)
    saturation = (rgb.max(axis=2) - rgb.min(axis=2)) / np.maximum(rgb.max(axis=2), 1)
    papier = (gris > _seuil_otsu(gris.astype(np.uint8))) & (saturation < 0.28)
    return papier, img.width / gris.shape[1], img.height / gris.shape[0]


def _suite(profil: np.ndarray, seuil: float) -> tuple[int, int]:
    k = max(3, len(profil) // 40)
    lisse = np.convolve(profil, np.ones(k) / k, mode="same")
    return _plus_longue_suite(_boucher(lisse > seuil, int(len(profil) * 0.12)))


def _garder(img: Image.Image, boite: tuple[int, int, int, int], part_min: float) -> Image.Image:
    # Garde-fou : un recadrage qui garderait moins que part_min de l'image est sans doute une erreur
    # (une page entièrement en photo sombre n'a presque pas de « papier »).
    if (boite[2] - boite[0]) * (boite[3] - boite[1]) < part_min * img.width * img.height:
        return img
    return img.crop(boite)


def recadrer_hauteur(img: Image.Image) -> Image.Image:
    """Retire le haut et le bas qui ne sont pas du papier (table, objets), sur toute la largeur."""
    papier, _, sy = _masque_papier(img)
    y0, y1 = _suite(papier.mean(axis=1), 0.3)
    m = int(0.01 * img.height)
    return _garder(img, (0, max(0, int(y0 * sy) - m), img.width, min(img.height, int(y1 * sy) + m)), 0.4)


def recadrer_largeur(img: Image.Image) -> Image.Image:
    """Retire les côtés qui ne sont pas du papier, page par page (une page entièrement en photo est gardée)."""
    papier, sx, _ = _masque_papier(img)
    x0, x1 = _suite(papier.mean(axis=0), 0.25)
    m = int(0.01 * img.width)
    return _garder(img, (max(0, int(x0 * sx) - m), 0, min(img.width, int(x1 * sx) + m), img.height), 0.55)


# ---------------------------------------------------------------- double page

def trouver_pli(img: Image.Image) -> int | None:
    """Abscisse du pli d'une double page, ou None si l'image n'en est pas une.

    Le pli est une vallée étroite : une bande verticale plus sombre que ses deux voisinages, à gauche ET à
    droite, entre 30 % et 70 % de la largeur. Un simple bord (photo sombre contre papier clair) n'est sombre que
    d'un côté : il n'attire pas la coupe, pas plus qu'une photo sombre pleine page.
    """
    if img.width < 1.2 * img.height:
        return None
    petit = img.convert("L")
    petit.thumbnail((1000, 1000))
    g = np.asarray(petit).astype(float)
    h, w = g.shape
    profil = g[int(h * 0.1):int(h * 0.9)].mean(axis=0)
    k = max(3, w // 120)                       # largeur du pli
    c = max(4, w // 40)                        # largeur de chaque voisinage
    cumul = np.concatenate([[0.0], np.cumsum(profil)])

    def moyenne(a: int, b: int) -> float:
        a, b = max(0, a), min(w, b)
        return (cumul[b] - cumul[a]) / max(1, b - a)

    meilleur, x_pli = -1e9, None
    for x in range(int(w * 0.30), int(w * 0.70)):
        centre = moyenne(x - k // 2, x + k // 2 + 1)
        gauche = moyenne(x - k - c, x - k)
        droite = moyenne(x + k + 1, x + k + 1 + c)
        profondeur = min(gauche, droite) - centre   # sombre des deux côtés à la fois
        if profondeur > meilleur:
            meilleur, x_pli = profondeur, x
    if x_pli is None:
        return None
    return int(x_pli * img.width / w)


# ---------------------------------------------------------------- ensemble

def preparer_image(img: Image.Image, nom: str) -> list[tuple[str, Image.Image, str]]:
    """Renvoie [(nom de sortie, image, note)] pour une image de départ."""
    notes = []
    if _actif("SONDE_SENS"):
        angle = trouver_sens(img)
        if angle:
            img = img.rotate(angle, expand=True)
            notes.append(f"tournée de {angle}°")
    recadrer = _actif("SONDE_RECADRER")
    if recadrer:
        avant = img.size
        img = recadrer_hauteur(img)
        if img.size != avant:
            notes.append("recadrée")
    pli = trouver_pli(img) if _actif("SONDE_COUPER") else None
    note = ", ".join(notes) or "telle quelle"
    if pli:
        pages = [(f"{nom}-g", img.crop((0, 0, pli, img.height)), note + ", page de gauche"),
                 (f"{nom}-d", img.crop((pli, 0, img.width, img.height)), note + ", page de droite")]
    else:
        pages = [(nom, img, note)]
    return [(n, recadrer_largeur(p) if recadrer else p, t) for n, p, t in pages]


def preparer() -> list[Path]:
    if PREP.exists():
        shutil.rmtree(PREP)
    PREP.mkdir(parents=True)
    fichiers = sorted(p for p in ENTREE.iterdir() if p.is_file() and not p.name.startswith("."))
    if not fichiers:
        raise SystemExit("Le dossier pages/ est vide : y déposer les photos ou le PDF des pages à essayer.")
    sorties: list[Path] = []
    for f in fichiers:
        ext = f.suffix.lower()
        departs: list[tuple[str, Image.Image]] = []
        if ext == ".pdf":
            import pypdfium2 as pdfium

            pdf = pdfium.PdfDocument(str(f))
            for i in range(len(pdf)):
                departs.append((f"{f.stem}-p{i + 1:03d}", pdf[i].render(scale=DPI / 72).to_pil().convert("RGB")))
            pdf.close()
        elif ext in IMAGES:
            departs.append((f.stem, ImageOps.exif_transpose(Image.open(f)).convert("RGB")))
        else:
            print(f"ignoré (format inconnu) : {f.name}")
            continue
        for nom, img in departs:
            for nom_sortie, page, note in preparer_image(img, nom):
                sortie = PREP / f"{nom_sortie}.png"
                page.save(sortie)
                sorties.append(sortie)
                print(f"{sortie.name} : {page.width} × {page.height} px ({note})")
    print(f"{len(sorties)} page(s) prête(s) dans pages_prep/")
    return sorties


if __name__ == "__main__":
    preparer()
