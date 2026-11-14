"""Prépare les pages déposées dans pages/ : une image PNG par page dans pages_prep/.

- PDF : chaque page rendue à 300 points par pouce.
- Photos (JPEG, PNG, HEIC de l'iPhone, TIFF) : remises droites selon l'EXIF et converties en PNG.
Aucun redressement de courbure ici : la sonde juge les moteurs sur les pages telles qu'elles sont prises.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

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
        if ext == ".pdf":
            import pypdfium2 as pdfium

            pdf = pdfium.PdfDocument(str(f))
            for i in range(len(pdf)):
                img = pdf[i].render(scale=DPI / 72).to_pil()
                sortie = PREP / f"{f.stem}-p{i + 1:03d}.png"
                img.save(sortie)
                sorties.append(sortie)
            pdf.close()
        elif ext in IMAGES:
            img = ImageOps.exif_transpose(Image.open(f)).convert("RGB")
            sortie = PREP / f"{f.stem}.png"
            img.save(sortie)
            sorties.append(sortie)
        else:
            print(f"ignoré (format inconnu) : {f.name}")
    for s in sorties:
        with Image.open(s) as im:
            print(f"{s.name} : {im.width} × {im.height} px")
    print(f"{len(sorties)} page(s) prête(s) dans pages_prep/")
    return sorties


if __name__ == "__main__":
    preparer()
