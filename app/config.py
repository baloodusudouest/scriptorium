"""Réglages lus dans l'environnement du conteneur. Aucune valeur personnelle dans le code."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from . import maison

APPLI = "scriptorium"


@dataclass(frozen=True)
class Config:
    password: str
    data: Path
    static: Path
    attente_connexion: bool = True        # délai anti-essais ; coupé dans les tests
    lecture_seule: bool = False           # rien ne part chez Mistral, rien n'est déposé dans Grimmory
    origine_lecture_seule: str = ""       # 0.5 : « maison » (MAISON_LECTURE_SEULE) ou « appli » (SCRIPTORIUM_LECTURE_SEULE)
    mistral_cle: str = ""                 # clé d'API Mistral ; vide : la lecture n'est pas proposée
    mistral_url: str = "https://api.mistral.ai/v1/ocr"
    mistral_modele: str = "mistral-ocr-latest"
    prix_page: float = 0.002              # estimation affichée (dollars par page), réglable
    bookdrop: Path | None = None          # dossier d'import de Grimmory, monté en écriture
    dpi: int = 200                        # définition des pages découpées dans un PDF
    recherche_web: bool = True            # fiche par l'ISBN : interroger la BnF et Open Library (lecture seule)
    jeton_calcul: str = ""                # jeton du PC de calcul (contre-lecture Marker) ; vide : porte /calcul fermée
    travail_auto: bool = True             # tâche de fond (coupée dans les tests, qui la lancent à la main)


def charger() -> Config:
    mot_de_passe = maison.mot_de_passe("SCRIPTORIUM_PASSWORD")   # 0.5 : MAISON_PASSWORD, repli sur l'ancien nom
    if len(mot_de_passe) < 12:
        raise SystemExit("MAISON_PASSWORD (ou SCRIPTORIUM_PASSWORD) est absent ou trop court (12 caractères au moins) : "
                         "Scriptorium ne démarre pas.")
    bookdrop = os.environ.get("SCRIPTORIUM_BOOKDROP", "/bookdrop").strip()
    return Config(
        password=mot_de_passe,
        data=Path(os.environ.get("SCRIPTORIUM_DATA", "/data")),
        static=Path(__file__).parent / "static",
        # 0.5 : MAISON_LECTURE_SEULE pour toute la maison ; SCRIPTORIUM_LECTURE_SEULE (« oui » ou « non ») l'emporte
        lecture_seule=maison.lecture_seule("SCRIPTORIUM_LECTURE_SEULE"),
        origine_lecture_seule=maison.origine_lecture_seule("SCRIPTORIUM_LECTURE_SEULE"),
        mistral_cle=os.environ.get("SCRIPTORIUM_MISTRAL_CLE", "").strip(),
        mistral_url=os.environ.get("SCRIPTORIUM_MISTRAL_URL", "https://api.mistral.ai/v1/ocr").strip(),
        mistral_modele=os.environ.get("SCRIPTORIUM_MISTRAL_MODELE", "mistral-ocr-latest").strip(),
        prix_page=float(os.environ.get("SCRIPTORIUM_PRIX_PAGE", "0.002") or 0.002),
        bookdrop=Path(bookdrop) if bookdrop else None,
        dpi=int(os.environ.get("SCRIPTORIUM_DPI", "200") or 200),
        recherche_web=os.environ.get("SCRIPTORIUM_RECHERCHE_WEB", "oui").strip().lower() not in ("non", "0", "false", "no"),
        jeton_calcul=os.environ.get("SCRIPTORIUM_JETON_CALCUL", "").strip(),
    )
