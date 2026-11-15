"""Contre-lecture de Scriptorium sur le PC de calcul (0.3.1).

Tourne dans Docker Desktop (pc/calcul.yml). Toutes les 30 secondes, il demande au NAS une page à relire,
la lit avec Marker sur le processeur et renvoie le texte. Le NAS compare cette lecture à celle de Mistral :
les mots qui diffèrent deviennent les mots à relire.

Il ne parle qu'à Scriptorium, par la porte /calcul, avec le jeton SCRIPTORIUM_JETON_CALCUL. Il ne garde rien :
la page est lue dans un fichier temporaire, effacé aussitôt.

Variables :
    SCRIPTORIUM_URL            adresse de Scriptorium vue du PC, par ex. http://192.168.1.20:8091
    SCRIPTORIUM_JETON_CALCUL   même valeur que dans la stack du NAS
    CALCUL_ATTENTE             secondes entre deux demandes quand il n'y a rien (30)
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

log = logging.getLogger("calcul")
VERSION = "0.3.1"


class LecteurMarker:
    """Marker (moteur Indra, mode « fast », le seul raisonnable sans carte NVIDIA). Les modèles sont chargés
    une fois, au premier appel ; si l'API de Marker a changé, on retombe sur la commande marker_single."""

    def __init__(self):
        self._convertir = None
        self.nom = "marker"

    def _charger(self):
        try:
            from marker.config.parser import ConfigParser
            from marker.models import create_model_dict
            from marker.output import text_from_rendered

            options = {"output_format": "markdown", "mode": "fast", "disable_image_extraction": True, "disable_tqdm": True}
            parseur = ConfigParser(options)
            convertisseur = parseur.get_converter_cls()(
                config=parseur.generate_config_dict(), artifact_dict=create_model_dict(load_indra=True, no_server=True),
                processor_list=parseur.get_processors(), renderer=parseur.get_renderer(), llm_service=None)
            self._convertir = lambda chemin: text_from_rendered(convertisseur(str(chemin)))[0]
            self.nom = f"marker {_version('marker-pdf')} (fast)"
        except Exception as e:  # noqa: BLE001
            log.warning("API de Marker indisponible (%s) : commande marker_single à chaque page (plus lent)", e)
            self._convertir = self._commande
            self.nom = f"marker_single {_version('marker-pdf')}"

    @staticmethod
    def _commande(chemin: Path) -> str:
        r = subprocess.run(["marker_single", str(chemin), "--stdout", "--mode", "fast", "--disable_image_extraction"],
                           capture_output=True, text=True, timeout=1800)
        if r.returncode != 0:
            raise RuntimeError((r.stderr or r.stdout)[-500:])
        return r.stdout

    def lire(self, chemin: Path) -> str:
        if self._convertir is None:
            self._charger()
        return self._convertir(chemin)


def _version(paquet: str) -> str:
    try:
        from importlib.metadata import version
        return version(paquet)
    except Exception:  # noqa: BLE001
        return "?"


def une_page(client: httpx.Client, lecteur) -> bool:
    """Demande une page, la lit, rend le texte. Renvoie False s'il n'y avait rien à faire."""
    entetes = {"X-Moteur": getattr(lecteur, "nom", "?")}
    r = client.get("/calcul/travail", headers=entetes)
    if r.status_code == 204:
        return False
    r.raise_for_status()
    t = r.json()
    image = client.get(t["image"], headers=entetes)
    image.raise_for_status()
    debut = time.monotonic()
    with tempfile.TemporaryDirectory() as dossier:
        chemin = Path(dossier) / f"page-{t['livre_id']}-{t['rang']}.jpg"
        chemin.write_bytes(image.content)
        try:
            texte = lecteur.lire(chemin)
            corps = {"markdown": texte}
        except Exception as e:  # noqa: BLE001 — une page illisible ne doit pas arrêter le PC
            log.exception("page %s du livre %s illisible", t["rang"], t["livre_id"])
            corps = {"erreur": f"{type(e).__name__} : {e}"[:500]}
    client.post(f"/calcul/pages/{t['livre_id']}/{t['rang']}", json=corps, headers=entetes).raise_for_status()
    log.info("livre %s, page %s : %s en %.0f s", t["livre_id"], t["rang"], "lue" if "markdown" in corps else "erreur",
             time.monotonic() - debut)
    return True


def boucle(client: httpx.Client, lecteur, attente: float = 30, arret=lambda: False) -> None:
    while not arret():
        try:
            fait = une_page(client, lecteur)
        except httpx.HTTPStatusError as e:
            code = e.response.status_code
            if code == 401:
                log.error("Jeton refusé par Scriptorium : vérifier SCRIPTORIUM_JETON_CALCUL des deux côtés.")
                time.sleep(300)
            elif code == 404 and e.request.url.path == "/calcul/travail":
                log.error("Porte /calcul fermée : SCRIPTORIUM_JETON_CALCUL est vide dans la stack du NAS.")
                time.sleep(300)
            else:
                log.warning("Scriptorium a répondu %s", code)
                time.sleep(attente)
            continue
        except httpx.HTTPError as e:
            log.warning("Scriptorium injoignable (%s) : nouvel essai dans %s s", e, attente)
            time.sleep(attente)
            continue
        if not fait:
            time.sleep(attente)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%d/%m %H:%M:%S")
    url = os.environ.get("SCRIPTORIUM_URL", "").rstrip("/")
    jeton = os.environ.get("SCRIPTORIUM_JETON_CALCUL", "").strip()
    if not url or not jeton:
        sys.exit("SCRIPTORIUM_URL et SCRIPTORIUM_JETON_CALCUL sont nécessaires (voir pc/.env.exemple).")
    attente = float(os.environ.get("CALCUL_ATTENTE", "30") or 30)
    log.info("Contre-lecture Scriptorium %s : %s, une demande toutes les %.0f s quand rien n'attend", VERSION, url, attente)
    with httpx.Client(base_url=url, headers={"Authorization": f"Bearer {jeton}"}, timeout=60) as client:
        boucle(client, LecteurMarker(), attente)


if __name__ == "__main__":
    main()
