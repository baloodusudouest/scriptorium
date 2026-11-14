"""Lecture d'une page par Mistral OCR. Tout l'appel au service tient dans ce fichier : si Mistral change
ou ferme, c'est la seule fonction à remplacer (avis du conseil, 14/11/2026).

La clé ne quitte jamais le serveur : le navigateur parle à Scriptorium, Scriptorium parle à Mistral.
"""
from __future__ import annotations

import base64
import re
from dataclasses import dataclass, field

import httpx


@dataclass
class PageLue:
    markdown: str
    images: dict[str, bytes] = field(default_factory=dict)   # nom renvoyé par Mistral → contenu
    pages_facturees: int = 1
    douteuse: str = ""                                        # raison, si la sortie n'a pas l'air d'un texte


class ErreurMistral(RuntimeError):
    pass


def _decoder(image_base64: str) -> bytes:
    # L'API renvoie soit « data:image/jpeg;base64,… », soit le base64 seul.
    return base64.b64decode(re.sub(r"^data:[^,]*,", "", image_base64))


def _douteuse(md: str) -> str:
    """Repère une sortie qui n'est pas du texte de livre (vu dans la sonde : une page rendue en liste JSON)."""
    debut = md.lstrip()[:20]
    if debut.startswith("[{") or debut.startswith("{\"") or '"box_2d"' in md[:500]:
        return "sortie de Mistral illisible (données au lieu du texte)"
    if len(md.strip()) < 20:
        return "presque aucun texte rendu"
    return ""


def lire_page(image_jpeg: bytes, cle: str, url: str, modele: str, client: httpx.Client | None = None) -> PageLue:
    if not cle:
        raise ErreurMistral("aucune clé Mistral (SCRIPTORIUM_MISTRAL_CLE)")
    corps = {
        "model": modele,
        "document": {"type": "image_url", "image_url": "data:image/jpeg;base64," + base64.b64encode(image_jpeg).decode()},
        "include_image_base64": True,
    }
    propre = client is None
    client = client or httpx.Client(timeout=180)
    try:
        r = client.post(url, json=corps, headers={"Authorization": f"Bearer {cle}"})
    except httpx.HTTPError as e:
        raise ErreurMistral(f"Mistral injoignable : {e}") from e
    finally:
        if propre:
            client.close()
    if r.status_code == 401:
        raise ErreurMistral("clé Mistral refusée (401)")
    if r.status_code == 429:
        raise ErreurMistral("trop de demandes ou crédit épuisé chez Mistral (429)")
    if r.status_code >= 400:
        raise ErreurMistral(f"Mistral a répondu {r.status_code} : {r.text[:200]}")
    donnees = r.json()
    textes, images = [], {}
    for p in donnees.get("pages", []):
        textes.append(p.get("markdown", ""))
        for img in p.get("images", []) or []:
            if img.get("id") and img.get("image_base64"):
                images[img["id"]] = _decoder(img["image_base64"])
    md = "\n\n".join(textes)
    facturees = (donnees.get("usage_info") or {}).get("pages_processed") or max(1, len(donnees.get("pages", [])))
    return PageLue(markdown=md, images=images, pages_facturees=int(facturees), douteuse=_douteuse(md))


def verifier(cle: str, url: str) -> dict:
    """Vérifie la clé sans rien envoyer à lire : liste des modèles (GET …/v1/models)."""
    if not cle:
        return {"ok": False, "message": "Aucune clé Mistral dans la stack (SCRIPTORIUM_MISTRAL_CLE)."}
    base = url.split("/v1/")[0]
    try:
        r = httpx.get(f"{base}/v1/models", headers={"Authorization": f"Bearer {cle}"}, timeout=20)
    except httpx.HTTPError as e:
        return {"ok": False, "message": f"Mistral injoignable : {e}"}
    if r.status_code == 401:
        return {"ok": False, "message": "Clé refusée par Mistral."}
    if r.status_code >= 400:
        return {"ok": False, "message": f"Mistral a répondu {r.status_code}."}
    return {"ok": True, "message": "Clé acceptée par Mistral."}
