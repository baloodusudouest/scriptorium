"""Voie B : un modèle de vision servi sur le PC par LM Studio (ou Ollama), sur la carte graphique.

Le conteneur l'appelle par l'adresse compatible OpenAI (VISION_URL, par défaut LM Studio sur le PC hôte).
VISION_MODELE vide : le premier modèle chargé est pris.
"""
from __future__ import annotations

import base64
import io
import os
from pathlib import Path

import httpx
from PIL import Image

from commun import traiter

ADRESSE = os.environ.get("VISION_URL", "http://host.docker.internal:1234/v1").rstrip("/")
COTE_MAX = int(os.environ.get("VISION_COTE_MAX", "1800"))

CONSIGNE = """Tu transcris une page de livre scannée, en français.
Rends le contenu en Markdown, fidèlement, sans rien inventer ni résumer :
- titres en #, ## ; paragraphes séparés par une ligne vide ; italique *…* et gras **…** comme sur la page ;
- recolle les mots coupés en fin de ligne ;
- tableaux en tableaux Markdown ;
- encadrés en citation (> …) ;
- notes de bas de page en [^1] ;
- pour chaque photo ou illustration, une ligne ![courte description](illustration) à sa place dans le fil du texte ;
- ignore l'en-tête courant et le numéro de page ;
- si la page a plusieurs colonnes, suis l'ordre de lecture (colonne de gauche entière, puis la suivante).
Réponds uniquement par le Markdown de la page."""


def _modele(client: httpx.Client) -> str:
    choisi = os.environ.get("VISION_MODELE", "").strip()
    if choisi:
        return choisi
    r = client.get(f"{ADRESSE}/models", timeout=20)
    r.raise_for_status()
    modeles = [m["id"] for m in r.json().get("data", [])]
    if not modeles:
        raise RuntimeError("aucun modèle chargé dans LM Studio")
    return modeles[0]


def _image(page: Path) -> str:
    with Image.open(page) as im:
        im = im.convert("RGB")
        im.thumbnail((COTE_MAX, COTE_MAX))
        tampon = io.BytesIO()
        im.save(tampon, "JPEG", quality=90)
    return "data:image/jpeg;base64," + base64.b64encode(tampon.getvalue()).decode()


def lire(page: Path, sortie: Path) -> dict:
    with httpx.Client() as client:
        modele = _modele(client)
        corps = {
            "model": modele,
            "temperature": 0,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": CONSIGNE},
                {"type": "image_url", "image_url": {"url": _image(page)}},
            ]}],
        }
        r = client.post(f"{ADRESSE}/chat/completions", json=corps, timeout=900)
        if r.status_code >= 400:
            raise RuntimeError(f"HTTP {r.status_code} : {r.text[:300]}")
        texte = r.json()["choices"][0]["message"]["content"] or ""
    # Certains modèles entourent leur réponse d'un bloc ```markdown … ```
    texte = texte.strip()
    if texte.startswith("```"):
        texte = texte.split("\n", 1)[1] if "\n" in texte else ""
        texte = texte.rsplit("```", 1)[0]
    (sortie / "page.md").write_text(texte.strip() + "\n", encoding="utf-8")
    return {"modele": modele}


if __name__ == "__main__":
    traiter("vision", lire)
