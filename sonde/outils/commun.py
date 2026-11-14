"""Outils communs à tous les moteurs de la sonde.

Chaque moteur lit les pages préparées (pages_prep/*.png) et écrit, pour chaque page :
    resultats/<moteur>/<page>/page.md     le texte recomposé (Markdown)
    resultats/<moteur>/<page>/images/     les illustrations découpées, si le moteur en donne
    resultats/<moteur>/<page>/mesure.json temps de calcul, erreur éventuelle, coût
Un échec sur une page est noté dans mesure.json et n'arrête pas les autres pages.
"""
from __future__ import annotations

import json
import os
import time
import traceback
from pathlib import Path

RACINE = Path(os.environ.get("SONDE_RACINE", "/sonde"))
PREP = RACINE / "pages_prep"
RESULTATS = RACINE / "resultats"


def pages_preparees() -> list[Path]:
    pages = sorted(p for p in PREP.glob("*.png"))
    if not pages:
        raise SystemExit("Aucune page préparée : lancer d'abord « docker compose run --rm preparer ».")
    return pages


def dossier_sortie(moteur: str, page: Path) -> Path:
    d = RESULTATS / moteur / page.stem
    (d / "images").mkdir(parents=True, exist_ok=True)
    return d


def deja_fait(moteur: str, page: Path) -> bool:
    """Une page déjà lue sans erreur n'est pas relue (on peut relancer après une coupure)."""
    m = RESULTATS / moteur / page.stem / "mesure.json"
    if not m.exists() or os.environ.get("SONDE_REFAIRE"):
        return False
    try:
        return not json.loads(m.read_text(encoding="utf-8")).get("erreur")
    except ValueError:
        return False


def traiter(moteur: str, fonction) -> None:
    """Applique fonction(page, dossier) -> dict (infos en plus) à chaque page, en mesurant le temps."""
    pages = pages_preparees()
    print(f"[{moteur}] {len(pages)} page(s)")
    for page in pages:
        if deja_fait(moteur, page):
            print(f"[{moteur}] {page.name} : déjà fait")
            continue
        d = dossier_sortie(moteur, page)
        debut = time.perf_counter()
        mesure: dict = {"moteur": moteur, "page": page.name}
        try:
            mesure.update(fonction(page, d) or {})
            mesure["erreur"] = None
        except Exception as e:  # noqa: BLE001 — on note et on passe à la page suivante
            mesure["erreur"] = f"{type(e).__name__}: {e}"
            (d / "erreur.txt").write_text(traceback.format_exc(), encoding="utf-8")
        mesure["secondes"] = round(time.perf_counter() - debut, 1)
        (d / "mesure.json").write_text(json.dumps(mesure, ensure_ascii=False, indent=2), encoding="utf-8")
        etat = "ERREUR " + mesure["erreur"] if mesure["erreur"] else "ok"
        print(f"[{moteur}] {page.name} : {mesure['secondes']} s, {etat}")
