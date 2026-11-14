"""Base SQLite de Scriptorium : les livres, leurs pages, le journal des écritures.

Fichiers d'un livre : <data>/livres/<id>/
    source.pdf          le PDF importé (source.pdf.partiel pendant l'envoi)
    pages/0001.jpg      les pages découpées, dans l'ordre du PDF
    lu/0001.md          le texte rendu par Mistral pour la page
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
        self._cnx.commit()

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

    # ------------------------------------------------------------ dossiers
    def dossier(self, livre_id: int) -> Path:
        return self.data / "livres" / str(livre_id)

    # ------------------------------------------------------------ journal
    def noter(self, quoi: str, livre_id: int | None, detail: str = "") -> None:
        self.ecrire("INSERT INTO journal (le, quoi, livre_id, detail) VALUES (?, ?, ?, ?)",
                    maintenant(), quoi, livre_id, detail)
