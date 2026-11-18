"""Contre-lecture par le PC de calcul (0.3.1), côté NAS.

Le PC (conteneur `pc/calcul.yml`, Marker sur le processeur) vient chercher le travail : il demande une page,
la lit et renvoie son texte. Il ne peut rien faire d'autre. Le PC éteint ne bloque rien : les pages attendent
seulement leur contre-lecture.

Pages proposées au PC : celles des livres découpés, gardées, pas corrigées à la main, sans contre-lecture,
d'abord celles que Mistral a déjà lues (la comparaison peut se faire tout de suite). Une page prise par le PC
et jamais rendue (PC éteint en route) redevient libre au bout de 15 minutes.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from . import comparaison
from .base import Base, maintenant

DELAI_REPRISE = 15 * 60   # secondes


def prochaine_page(base: Base) -> dict | None:
    limite = time.time() - DELAI_REPRISE
    page = base.un(
        "SELECT p.id, p.livre_id, p.rang, l.langue FROM pages p JOIN livres l ON l.id = p.livre_id "
        "WHERE l.etat IN ('inventaire', 'lecture', 'pret') AND l.supprime_le = '' AND p.ecartee = 0 AND p.texte_main = 0 "
        "AND (p.contre = 'attente' OR (p.contre = 'calcul' AND p.contre_depuis < ?)) "
        "ORDER BY (p.lecture = 'faite') DESC, l.id, p.ordre LIMIT 1", limite)
    if page:
        base.ecrire("UPDATE pages SET contre = 'calcul', contre_depuis = ?, contre_erreur = '' WHERE id = ?",
                    time.time(), page["id"])
    return page


def pages_en_attente(base: Base) -> int:
    return base.un(
        "SELECT COUNT(*) AS n FROM pages p JOIN livres l ON l.id = p.livre_id "
        "WHERE l.etat IN ('inventaire', 'lecture', 'pret') AND l.supprime_le = '' AND p.ecartee = 0 AND p.texte_main = 0 "
        "AND p.contre IN ('attente', 'calcul')")["n"]


def signaler_passage(base: Base, moteur: str) -> None:
    base.memo("pc_vu_le", maintenant())
    if moteur:
        base.memo("pc_moteur", moteur[:80])


def enregistrer(base: Base, livre_id: int, rang: int, markdown: str | None, erreur: str = "") -> None:
    page = base.un("SELECT id FROM pages WHERE livre_id = ? AND rang = ?", livre_id, rang)
    if not page:
        return
    if erreur or markdown is None:
        base.ecrire("UPDATE pages SET contre = 'erreur', contre_erreur = ? WHERE id = ?", (erreur or "aucun texte")[:500], page["id"])
        return
    lu = base.dossier(livre_id) / "lu"
    lu.mkdir(parents=True, exist_ok=True)
    (lu / f"{rang:04d}.marker.md").write_text(markdown, encoding="utf-8")
    base.ecrire("UPDATE pages SET contre = 'faite', contre_erreur = '' WHERE id = ?", page["id"])
    comparer_page(base, livre_id, rang)


def comparer_page(base: Base, livre_id: int, rang: int) -> dict | None:
    """Compare le texte gardé de la page (Mistral ou corrigé) à la contre-lecture, s'il y a les deux.
    Écrit lu/NNNN.doutes.json et le nombre de doutes en base ; renvoie le résultat."""
    lu = base.dossier(livre_id) / "lu"
    texte, contre = lu / f"{rang:04d}.md", lu / f"{rang:04d}.marker.md"
    fichier = lu / f"{rang:04d}.doutes.json"
    if not (texte.is_file() and contre.is_file()):
        fichier.unlink(missing_ok=True)
        base.ecrire("UPDATE pages SET doutes = 0, accord = NULL WHERE livre_id = ? AND rang = ?", livre_id, rang)
        return None
    r = comparaison.comparer(texte.read_text(encoding="utf-8"), contre.read_text(encoding="utf-8"))
    fichier.write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
    base.ecrire("UPDATE pages SET doutes = ?, accord = ? WHERE livre_id = ? AND rang = ?",
                len(r["doutes"]), r["accord"], livre_id, rang)
    return r


def lire_doutes(dossier: Path, rang: int) -> dict | None:
    fichier = dossier / "lu" / f"{rang:04d}.doutes.json"
    try:
        return json.loads(fichier.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def a_relire(page: dict) -> bool:
    """Page signalée par la contre-lecture et pas encore relue."""
    if page.get("relue") or page.get("texte_main") or page.get("ecartee") or page.get("contre") != "faite":
        return False
    accord = page.get("accord")
    return bool(page.get("doutes")) or (accord is not None and accord < comparaison.ACCORD_FAIBLE)
