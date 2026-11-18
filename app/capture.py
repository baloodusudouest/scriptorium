"""Photo d'une page reprise à l'iPhone (page manquante d'un livre) : remise droite, recadrée sur le papier,
mise à une taille proche des pages découpées dans un PDF.

Le recadrage vient de la sonde (sonde/outils/preparer.py) : le papier est ce qui est clair et peu coloré ; la
table, les doigts et les couvertures colorées autour sont retirés. Un recadrage qui garderait trop peu de
l'image est refusé (garde-fou), et la photo reste alors entière.
"""
from __future__ import annotations

import io
import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

try:  # photos HEIC de l'iPhone (quand Safari ne les convertit pas lui-même)
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:  # pragma: no cover
    pass

COTE_MAX = 2400


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


def preparer_photo(contenu: bytes) -> bytes:
    """Octets d'une photo (JPEG, PNG, HEIC) → JPEG de la page, droite et recadrée."""
    try:
        img = Image.open(io.BytesIO(contenu))
        img = ImageOps.exif_transpose(img).convert("RGB")
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"image illisible : {e}") from e
    img = recadrer_largeur(recadrer_hauteur(img))
    img.thumbnail((COTE_MAX, COTE_MAX))
    sortie = io.BytesIO()
    img.save(sortie, "JPEG", quality=88)
    return sortie.getvalue()


def tourner(chemin, degres: int = 90) -> None:
    """Tourne l'image d'une page (sens des aiguilles d'une montre).
    0.6.7 (audit, M40) : écrite à côté puis renommée d'un coup : un arrêt laisse l'ancienne page entière, jamais une page tronquée."""
    chemin = Path(chemin)
    tmp = chemin.with_name(f".{chemin.name}.partiel")
    try:
        with Image.open(chemin) as img:
            tournee = img.rotate(-degres, expand=True)
            tournee.save(tmp, "JPEG", quality=90)
        os.replace(tmp, chemin)
    finally:
        tmp.unlink(missing_ok=True)
