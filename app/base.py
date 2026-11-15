"""Base SQLite de Scriptorium : les livres, leurs pages, le journal des écritures.

Fichiers d'un livre : <data>/livres/<id>/
    source.pdf          le PDF importé (source.pdf.partiel pendant l'envoi)
    pages/0001.jpg      les pages découpées, dans l'ordre du PDF
    lu/0001.md          le texte rendu par Mistral pour la page (ou corrigé à la main)
    lu/0001.marker.md   la contre-lecture faite par Marker sur le PC (0.3.1)
    lu/0001.doutes.json les mots qui diffèrent entre les deux lectures (0.3.1)
    lu/images/…         les illustrations découpées par Mistral
    sortie/             l'EPUB et le PDF d'archive fabriqués
"""
from __future__ import annotations

import sqlite3
import threading
from datetime import datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS livres (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titre TEXT NOT NULL,
    auteur TEXT NOT NULL DEFAULT '',
    langue TEXT NOT NULL DEFAULT 'fr',
    etat TEXT NOT NULL DEFAULT 'envoi',   -- envoi, decoupe, inventaire, lecture, pret, erreur
    source_nom TEXT NOT NULL DEFAULT '',
    source_octets INTEGER NOT NULL DEFAULT 0,
    inventaire_confirme INTEGER NOT NULL DEFAULT 0,
    lecture_demandee INTEGER NOT NULL DEFAULT 0,
    avancement INTEGER NOT NULL DEFAULT 0,
    erreur TEXT NOT NULL DEFAULT '',
    epub TEXT NOT NULL DEFAULT '',
    archive TEXT NOT NULL DEFAULT '',
    depose_le TEXT NOT NULL DEFAULT '',
    cree_le TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    livre_id INTEGER NOT NULL REFERENCES livres(id) ON DELETE CASCADE,
    rang INTEGER NOT NULL,                -- place dans le PDF, à partir de 1
    numero_lu INTEGER,                    -- numéro imprimé lu par Tesseract
    numero INTEGER,                       -- numéro gardé (corrigé à la main au besoin)
    ecartee INTEGER NOT NULL DEFAULT 0,   -- page en double ou inutile : hors du livre
    lecture TEXT NOT NULL DEFAULT 'attente',  -- attente, faite, douteuse, erreur
    lecture_erreur TEXT NOT NULL DEFAULT '',
    pages_facturees INTEGER NOT NULL DEFAULT 0,
    UNIQUE (livre_id, rang)
);
CREATE TABLE IF NOT EXISTS memo (
    cle TEXT PRIMARY KEY,                 -- pc_vu_le, pc_moteur : dernier passage du PC de calcul
    valeur TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS journal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    le TEXT NOT NULL,
    quoi TEXT NOT NULL,                   -- import, lecture_mistral, depot_grimmory, suppression
    livre_id INTEGER,
    detail TEXT NOT NULL DEFAULT ''
);
"""


def maintenant() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class Base:
    def __init__(self, data: Path):
        self.data = data
        self.chemin = data / "scriptorium.db"
        self._verrou = threading.RLock()
        self._cnx = sqlite3.connect(self.chemin, check_same_thread=False)
        self._cnx.row_factory = sqlite3.Row
        self._cnx.execute("PRAGMA foreign_keys = ON")
        self._cnx.execute("PRAGMA journal_mode = WAL")
        self._cnx.executescript(SCHEMA)
        self._migrer()
        self._cnx.commit()

    def _migrer(self) -> None:
        """Colonnes ajoutées après la première version : ajoutées aux bases déjà créées."""
        colonnes = {r[1] for r in self._cnx.execute("PRAGMA table_info(livres)")}
        if "relire" not in colonnes:   # 0.2.1 : relire les numéros de page d'un livre déjà découpé
            self._cnx.execute("ALTER TABLE livres ADD COLUMN relire INTEGER NOT NULL DEFAULT 0")
        colonnes = {r[1] for r in self._cnx.execute("PRAGMA table_info(pages)")}
        if "numero_mistral" not in colonnes:   # 0.2.2 : numéro imprimé repéré par Mistral
            self._cnx.execute("ALTER TABLE pages ADD COLUMN numero_mistral INTEGER")
        if "numero_manuel" not in colonnes:    # 0.2.2 : numéro corrigé à la main, jamais remplacé
            self._cnx.execute("ALTER TABLE pages ADD COLUMN numero_manuel INTEGER NOT NULL DEFAULT 0")
        if "ordre" not in colonnes:            # 0.3.0 : place dans le livre (une page reprise s'insère entre deux)
            self._cnx.execute("ALTER TABLE pages ADD COLUMN ordre REAL")
            self._cnx.execute("UPDATE pages SET ordre = rang")
        if "source" not in colonnes:           # 0.3.0 : « pdf » (découpée) ou « photo » (reprise à l'iPhone)
            self._cnx.execute("ALTER TABLE pages ADD COLUMN source TEXT NOT NULL DEFAULT 'pdf'")
        if "rendu_choisi" not in colonnes:     # 0.3.0 : « auto » (texte si lu) ou « image » (gardée en image)
            self._cnx.execute("ALTER TABLE pages ADD COLUMN rendu_choisi TEXT NOT NULL DEFAULT 'auto'")
        if "texte_main" not in colonnes:       # 0.3.0 : texte corrigé à la relecture (Mistral ne l'écrase plus)
            self._cnx.execute("ALTER TABLE pages ADD COLUMN texte_main INTEGER NOT NULL DEFAULT 0")
        nouvelles = {   # 0.3.1 : contre-lecture par Marker sur le PC
            "contre": "TEXT NOT NULL DEFAULT 'attente'",     # attente, calcul, faite, erreur
            "contre_depuis": "REAL NOT NULL DEFAULT 0",      # heure (epoch) où le PC a pris la page
            "contre_erreur": "TEXT NOT NULL DEFAULT ''",
            "doutes": "INTEGER NOT NULL DEFAULT 0",          # mots qui diffèrent entre les deux lectures
            "accord": "REAL",                                # ressemblance des deux lectures (0 à 1)
            "relue": "INTEGER NOT NULL DEFAULT 0",           # page relue : ses doutes ne sont plus comptés
        }
        for nom, definition in nouvelles.items():
            if nom not in colonnes:
                self._cnx.execute(f"ALTER TABLE pages ADD COLUMN {nom} {definition}")
        colonnes = {r[1] for r in self._cnx.execute("PRAGMA table_info(livres)")}
        nouvelles = {   # 0.4.0 : fiche par l'ISBN, couverture, PDF A5
            "editeur": "TEXT NOT NULL DEFAULT ''",
            "annee": "TEXT NOT NULL DEFAULT ''",
            "isbn": "TEXT NOT NULL DEFAULT ''",
            "couverture": "INTEGER",                         # rang de la page qui sert de couverture
            "pdf": "TEXT NOT NULL DEFAULT ''",               # nom du PDF A5 fabriqué
            "pdf_demande": "INTEGER NOT NULL DEFAULT 0",
            "pdf_erreur": "TEXT NOT NULL DEFAULT ''",
        }
        for nom, definition in nouvelles.items():
            if nom not in colonnes:
                self._cnx.execute(f"ALTER TABLE livres ADD COLUMN {nom} {definition}")

    # ------------------------------------------------------------ accès bas niveau
    def lire(self, sql: str, *args) -> list[dict]:
        with self._verrou:
            return [dict(r) for r in self._cnx.execute(sql, args).fetchall()]

    def un(self, sql: str, *args) -> dict | None:
        r = self.lire(sql, *args)
        return r[0] if r else None

    def ecrire(self, sql: str, *args) -> int:
        with self._verrou:
            c = self._cnx.execute(sql, args)
            self._cnx.commit()
            return c.lastrowid

    def plusieurs(self, sql: str, lignes: list[tuple]) -> None:
        with self._verrou:
            self._cnx.executemany(sql, lignes)
            self._cnx.commit()

    def fermer(self) -> None:
        with self._verrou:
            self._cnx.close()

    def memo(self, cle: str, valeur: str | None = None) -> str:
        """Petite mémoire clé/valeur (dernier passage du PC de calcul)."""
        if valeur is not None:
            self.ecrire("INSERT INTO memo (cle, valeur) VALUES (?, ?) ON CONFLICT(cle) DO UPDATE SET valeur = excluded.valeur",
                        cle, valeur)
            return valeur
        r = self.un("SELECT valeur FROM memo WHERE cle = ?", cle)
        return r["valeur"] if r else ""

    # ------------------------------------------------------------ dossiers
    def dossier(self, livre_id: int) -> Path:
        return self.data / "livres" / str(livre_id)

    # ------------------------------------------------------------ journal
    def noter(self, quoi: str, livre_id: int | None, detail: str = "") -> None:
        self.ecrire("INSERT INTO journal (le, quoi, livre_id, detail) VALUES (?, ?, ?, ?)",
                    maintenant(), quoi, livre_id, detail)
