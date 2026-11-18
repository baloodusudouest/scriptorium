"""0.6.7 (audit du 17/11/2026, M40) : l'EPUB, le PDF des pages et une page tournée ne sont jamais laissés
à moitié écrits sous leur nom final."""
from __future__ import annotations

import os
import zipfile

import pytest
from PIL import Image

from app import capture, fabrication

LIVRE = {"id": 1, "titre": "Essai", "auteur": "", "langue": "fr"}


def preparer(dossier):
    (dossier / "lu").mkdir()
    (dossier / "pages").mkdir()
    (dossier / "lu" / "0001.md").write_text("# Un titre inventé\n\nUn paragraphe.\n\n12")
    Image.new("RGB", (60, 90), "white").save(dossier / "pages" / "0001.jpg", "JPEG")
    return [{"rang": 1, "numero": 12, "lecture": "faite"}]


def restes(dossier):
    return [p.name for p in dossier.rglob("*") if p.name.endswith((".partiel", ".tmp"))]


def test_epub_interrompu_ne_laisse_rien_sous_le_nom_final(tmp_path, monkeypatch):
    pages = preparer(tmp_path)
    sortie = tmp_path / "sortie" / "Livre.epub"

    def panne(*_a, **_k):
        raise OSError("coupure simulée")

    monkeypatch.setattr(fabrication, "ajouter_liste_des_pages", panne)
    with pytest.raises(OSError):
        fabrication.fabriquer_epub(tmp_path, LIVRE, pages, sortie)
    assert not sortie.exists() and restes(tmp_path) == []


def test_epub_remplace_l_ancien_d_un_coup(tmp_path):
    pages = preparer(tmp_path)
    sortie = tmp_path / "sortie" / "Livre.epub"
    sortie.parent.mkdir()
    sortie.write_bytes(b"ancien")
    fabrication.fabriquer_epub(tmp_path, LIVRE, pages, sortie)
    with zipfile.ZipFile(sortie) as z:
        assert z.namelist()[0] == "mimetype" and any(n.endswith("nav.xhtml") for n in z.namelist())
        nav = z.read(next(n for n in z.namelist() if n.endswith("nav.xhtml"))).decode()
    assert "page-list" in nav and restes(tmp_path) == []


def test_pdf_des_pages_interrompu(tmp_path, monkeypatch):
    pages = preparer(tmp_path)
    sortie = tmp_path / "sortie" / "Livre - pages.pdf"

    def panne(*_a, **_k):
        raise OSError("coupure simulée")

    monkeypatch.setattr(os, "replace", panne)
    with pytest.raises(OSError):
        fabrication.fabriquer_archive(tmp_path, pages, sortie)
    assert not sortie.exists() and restes(tmp_path) == []
    monkeypatch.undo()
    fabrication.fabriquer_archive(tmp_path, pages, sortie)
    assert sortie.read_bytes().startswith(b"%PDF")


def test_page_tournee_jamais_tronquee(tmp_path, monkeypatch):
    chemin = tmp_path / "0001.jpg"
    Image.new("RGB", (60, 90), "white").save(chemin, "JPEG")
    avant = chemin.read_bytes()

    def save_tronque(self, fp, *a, **k):
        with open(fp, "wb") as f:
            f.write(b"\xff\xd8 tronqu")
        raise OSError("coupure simulée")

    monkeypatch.setattr(Image.Image, "save", save_tronque)
    with pytest.raises(OSError):
        capture.tourner(chemin, 90)
    assert chemin.read_bytes() == avant and restes(tmp_path) == []
    monkeypatch.undo()
    capture.tourner(chemin, 90)
    with Image.open(chemin) as im:
        assert im.size == (90, 60)
