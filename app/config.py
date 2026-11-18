"""Réglages lus dans l'environnement du conteneur. Aucune valeur personnelle dans le code.

0.6 : les réglages d'usage (recherche en ligne, estimation du prix, définition des pages) ne sont plus lus ici :
ils vivent dans <données>/reglages.json et se changent dans l'écran Réglages (voir REGLAGES ci-dessous et
app/maison.py, classe Reglages). Leur ancienne variable de la stack n'est lue qu'une fois, au premier démarrage.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from . import maison

APPLI = "scriptorium"

# Réglages d'usage (contrat de sauvegarde 1) : clé → valeur par défaut (son type fixe le type du réglage)
REGLAGES = {
    "recherche_web": True,     # fiche par l'ISBN : interroger la BnF et Open Library (lecture seule)
    "prix_page": 0.002,        # estimation affichée avant une lecture par Mistral, en dollars par page
    "dpi": 200,                # définition des pages découpées dans un PDF importé
    "plafond_livre": 2.0,      # 0.6.6 : euros de lecture Mistral par livre au-delà desquels on s'arrête et on demande ; 0 : pas de plafond
}
# 0.6.6 : le prix par page est en dollars (tarif de Mistral) ; le plafond, en euros. Conversion approximative.
EUROS_PAR_DOLLAR = 0.9
# 0.6.7 (audit, M38) : un livre supprimé reste ce nombre de jours dans la corbeille avant d'être effacé pour de bon
CORBEILLE_JOURS = 30
# Anciennes variables de la stack, reprises une seule fois (premier démarrage de la 0.6), puis plus jamais lues
VARIABLES_REPRISES = {
    "recherche_web": "SCRIPTORIUM_RECHERCHE_WEB",
    "prix_page": "SCRIPTORIUM_PRIX_PAGE",
    "dpi": "SCRIPTORIUM_DPI",
}
# Bornes vérifiées à l'enregistrement (écran Réglages, restauration)
BORNES = {"prix_page": (0.0, 1.0), "dpi": (72, 600), "plafond_livre": (0.0, 100.0)}
# Clés à ne jamais sortir dans une sauvegarde (aucune aujourd'hui : les trois réglages sont sans secret)
EXCLUS: tuple[str, ...] = ()


@dataclass(frozen=True)
class Config:
    password: str
    data: Path
    static: Path
    attente_connexion: bool = True        # délai anti-essais ; coupé dans les tests
    lecture_seule: bool = False           # rien ne part chez Mistral, rien n'est déposé dans Grimmory
    origine_lecture_seule: str = ""       # « maison » (MAISON_LECTURE_SEULE) ou « appli » (SCRIPTORIUM_LECTURE_SEULE)
    mistral_cle: str = ""                 # clé d'API Mistral ; vide : la lecture n'est pas proposée
    mistral_url: str = "https://api.mistral.ai/v1/ocr"
    mistral_modele: str = "mistral-ocr-latest"
    bookdrop: Path | None = None          # dossier d'import de Grimmory, monté en écriture
    jeton_calcul: str = ""                # jeton du PC de calcul (contre-lecture Marker) ; vide : porte /calcul fermée
    travail_auto: bool = True             # tâche de fond (coupée dans les tests, qui la lancent à la main)


def charger() -> Config:
    mot_de_passe = maison.mot_de_passe()          # 0.6 : MAISON_PASSWORD seul (l'ancien nom n'est plus lu)
    if len(mot_de_passe) < 12:
        raise SystemExit("MAISON_PASSWORD est absent ou trop court (12 caractères au moins) : Scriptorium ne démarre pas.")
    bookdrop = os.environ.get("SCRIPTORIUM_BOOKDROP", "/bookdrop").strip()
    return Config(
        password=mot_de_passe,
        data=Path(os.environ.get("SCRIPTORIUM_DATA", "/data")),
        static=Path(__file__).parent / "static",
        # MAISON_LECTURE_SEULE pour toute la maison ; SCRIPTORIUM_LECTURE_SEULE (« oui » ou « non ») l'emporte
        lecture_seule=maison.lecture_seule("SCRIPTORIUM_LECTURE_SEULE"),
        origine_lecture_seule=maison.origine_lecture_seule("SCRIPTORIUM_LECTURE_SEULE"),
        mistral_cle=os.environ.get("SCRIPTORIUM_MISTRAL_CLE", "").strip(),
        mistral_url=os.environ.get("SCRIPTORIUM_MISTRAL_URL", "https://api.mistral.ai/v1/ocr").strip(),
        mistral_modele=os.environ.get("SCRIPTORIUM_MISTRAL_MODELE", "mistral-ocr-latest").strip(),
        bookdrop=Path(bookdrop) if bookdrop else None,
        jeton_calcul=os.environ.get("SCRIPTORIUM_JETON_CALCUL", "").strip(),
    )
