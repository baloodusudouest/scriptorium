"""Mistral OCR : chaque page est envoyée à l'API (clé MISTRAL_API_KEY), qui renvoie du Markdown et les images.

La clé ne sort jamais du PC : elle est lue dans le fichier .env, à côté de docker-compose.yml.
"""
from __future__ import annotations

import base64
import os
import re
from pathlib import Path

import httpx

from commun import traiter

ADRESSE = os.environ.get("MISTRAL_URL", "https://api.mistral.ai/v1/ocr")
MODELE = os.environ.get("MISTRAL_MODELE", "mistral-ocr-latest")


def _donnees(chemin: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(chemin.read_bytes()).decode()


def _decoder(image_base64: str) -> bytes:
    # L'API renvoie soit « data:image/jpeg;base64,… », soit le base64 seul.
    return base64.b64decode(re.sub(r"^data:[^,]*,", "", image_base64))


def lire(page: Path, sortie: Path) -> dict:
    cle = os.environ.get("MISTRAL_API_KEY", "").strip()
    if not cle:
        raise RuntimeError("MISTRAL_API_KEY vide dans .env")
    corps = {
        "model": MODELE,
        "document": {"type": "image_url", "image_url": _donnees(page)},
        "include_image_base64": True,
    }
    r = httpx.post(ADRESSE, json=corps, headers={"Authorization": f"Bearer {cle}"}, timeout=180)
    if r.status_code >= 400:
        raise RuntimeError(f"HTTP {r.status_code} : {r.text[:300]}")
    donnees = r.json()
    textes, nb_images = [], 0
    for p in donnees.get("pages", []):
        md = p.get("markdown", "")
        for img in p.get("images", []) or []:
            nom = img.get("id") or f"img-{nb_images}.jpeg"
            if img.get("image_base64"):
                (sortie / "images" / nom).write_bytes(_decoder(img["image_base64"]))
                md = md.replace(f"]({nom})", f"](images/{nom})")
                nb_images += 1
        textes.append(md)
    (sortie / "page.md").write_text("\n\n".join(textes), encoding="utf-8")
    pages_lues = (donnees.get("usage_info") or {}).get("pages_processed", len(donnees.get("pages", [])))
    return {"images": nb_images, "pages_facturees": pages_lues, "modele": donnees.get("model", MODELE)}


if __name__ == "__main__":
    traiter("mistral", lire)
