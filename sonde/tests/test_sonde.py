"""Tests de la partie légère de la sonde : préparation, Mistral et vision (faux serveurs), rapport.

Docling et Marker ne sont pas testés ici : leurs modèles se téléchargent sur le PC au premier lancement.
"""
from __future__ import annotations

import base64
import importlib
import io
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

OUTILS = Path(__file__).resolve().parents[1] / "outils"
sys.path.insert(0, str(OUTILS))

PIXEL = base64.b64encode(
    (lambda b: (Image.new("RGB", (8, 8), "red").save(b, "JPEG"), b.getvalue())[1])(io.BytesIO())).decode()


@pytest.fixture()
def sonde(tmp_path, monkeypatch):
    """Un dossier de sonde vide, et les modules rechargés pour qu'ils le voient."""
    monkeypatch.setenv("SONDE_RACINE", str(tmp_path))
    (tmp_path / "pages").mkdir()
    mods = {}
    noms = ("commun", "preparer", "moteur_mistral", "moteur_vision", "rapport", "inventaire")
    for nom in noms:
        sys.modules.pop(nom, None)
    for nom in noms:
        mods[nom] = importlib.import_module(nom)
    return tmp_path, mods


def _page(chemin: Path, taille=(1200, 1700)):
    im = Image.new("RGB", taille, "white")
    ImageDraw.Draw(im).text((100, 100), "Chapitre premier", fill="black")
    im.save(chemin)


class _Serveur:
    """Faux serveur HTTP : renvoie la réponse prévue pour chaque chemin, et garde ce qu'il a reçu."""

    def __init__(self, reponses: dict):
        self.recu: list[tuple[str, str, dict | None]] = []
        reponses_ = reponses
        recu = self.recu

        class H(BaseHTTPRequestHandler):
            def _repondre(self, methode):
                n = int(self.headers.get("Content-Length") or 0)
                corps = json.loads(self.rfile.read(n)) if n else None
                recu.append((methode, self.path, corps, dict(self.headers)))
                code, donnees = reponses_.get(self.path, (404, {"erreur": "inconnu"}))
                brut = json.dumps(donnees).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(brut)))
                self.end_headers()
                self.wfile.write(brut)

            def do_GET(self):
                self._repondre("GET")

            def do_POST(self):
                self._repondre("POST")

            def log_message(self, *a):
                pass

        self.httpd = HTTPServer(("127.0.0.1", 0), H)
        self.adresse = f"http://127.0.0.1:{self.httpd.server_port}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def fermer(self):
        self.httpd.shutdown()


def test_preparer_pdf_et_photos(sonde):
    racine, m = sonde
    _page(racine / "pages" / "double.jpg")
    pdf = Image.new("RGB", (600, 800), "white")
    pdf.save(racine / "pages" / "livre.pdf", "PDF", save_all=True, append_images=[Image.new("RGB", (600, 800), "white")])
    (racine / "pages" / "notes.txt").write_text("rien")
    sorties = m["preparer"].preparer()
    noms = sorted(p.name for p in sorties)
    assert noms == ["double.png", "livre-p001.png", "livre-p002.png"]


def test_double_page_coupee_au_pli_meme_avec_une_photo_sombre(sonde):
    _, m = sonde
    # Double page 2000 × 1400 : à gauche une photo sombre pleine page, pli étroit à 1000, à droite du texte.
    im = Image.new("RGB", (2000, 1400), (235, 232, 225))
    d = ImageDraw.Draw(im)
    d.rectangle((60, 60, 940, 1340), fill=(30, 28, 26))          # photo sombre
    d.rectangle((420, 500, 600, 700), fill=(250, 220, 120))       # flamme claire dans la photo
    d.rectangle((990, 0, 1010, 1400), fill=(120, 115, 108))       # le pli
    for y in range(120, 1300, 40):
        d.rectangle((1100, y, 1900, y + 12), fill=(40, 40, 40))   # lignes de texte
    pli = m["preparer"].trouver_pli(im)
    assert 960 <= pli <= 1040
    pages = m["preparer"].preparer_image(im, "essai")
    assert [n for n, _, _ in pages] == ["essai-g", "essai-d"]
    gauche = pages[0][1]
    assert gauche.width > 0.8 * pli   # la page en photo sombre n'est pas rognée


def test_page_seule_pas_coupee_et_table_retiree(sonde):
    _, m = sonde
    im = Image.new("RGB", (1500, 2000), (120, 80, 40))            # table en bois
    d = ImageDraw.Draw(im)
    d.rectangle((150, 300, 1350, 1800), fill=(240, 238, 232))    # la page
    for y in range(400, 1700, 40):
        d.rectangle((250, y, 1250, y + 12), fill=(40, 40, 40))
    pages = m["preparer"].preparer_image(im, "page")
    assert len(pages) == 1
    page = pages[0][1]
    assert page.width < 1400 and page.height < 1700   # la table a été retirée autour


def test_preparer_dossier_vide(sonde):
    _, m = sonde
    with pytest.raises(SystemExit):
        m["preparer"].preparer()


def test_mistral_ecrit_texte_images_et_mesure(sonde, monkeypatch):
    racine, m = sonde
    (racine / "pages_prep").mkdir()
    _page(racine / "pages_prep" / "p1.png")
    reponse = {"model": "mistral-ocr-2511", "usage_info": {"pages_processed": 1}, "pages": [{
        "index": 0, "markdown": "# Titre\n\nTexte.\n\n![img-0.jpeg](img-0.jpeg)",
        "images": [{"id": "img-0.jpeg", "image_base64": "data:image/jpeg;base64," + PIXEL}]}]}
    srv = _Serveur({"/v1/ocr": (200, reponse)})
    try:
        monkeypatch.setenv("MISTRAL_API_KEY", "cle-de-test")
        monkeypatch.setattr(m["moteur_mistral"], "ADRESSE", srv.adresse + "/v1/ocr")
        m["commun"].traiter("mistral", m["moteur_mistral"].lire)
    finally:
        srv.fermer()
    d = racine / "resultats" / "mistral" / "p1"
    assert "](images/img-0.jpeg)" in (d / "page.md").read_text()
    assert (d / "images" / "img-0.jpeg").stat().st_size > 0
    mesure = json.loads((d / "mesure.json").read_text())
    assert mesure["erreur"] is None and mesure["pages_facturees"] == 1
    methode, chemin, corps, entetes = srv.recu[0]
    assert entetes["Authorization"] == "Bearer cle-de-test"
    assert corps["document"]["image_url"].startswith("data:image/png;base64,")


def test_mistral_sans_cle_note_l_erreur_et_continue(sonde, monkeypatch):
    racine, m = sonde
    (racine / "pages_prep").mkdir()
    for n in ("p1", "p2"):
        _page(racine / "pages_prep" / f"{n}.png")
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    m["commun"].traiter("mistral", m["moteur_mistral"].lire)
    for n in ("p1", "p2"):
        assert "MISTRAL_API_KEY" in json.loads((racine / "resultats/mistral" / n / "mesure.json").read_text())["erreur"]


def test_vision_prend_le_premier_modele_et_retire_le_bloc(sonde, monkeypatch):
    racine, m = sonde
    (racine / "pages_prep").mkdir()
    _page(racine / "pages_prep" / "p1.png", (3000, 4000))
    srv = _Serveur({
        "/v1/models": (200, {"data": [{"id": "qwen-vl-test"}]}),
        "/v1/chat/completions": (200, {"choices": [{"message": {"content": "```markdown\n# Titre\n\nTexte.\n```"}}]}),
    })
    try:
        monkeypatch.setattr(m["moteur_vision"], "ADRESSE", srv.adresse + "/v1")
        monkeypatch.delenv("VISION_MODELE", raising=False)
        m["commun"].traiter("vision", m["moteur_vision"].lire)
    finally:
        srv.fermer()
    d = racine / "resultats" / "vision" / "p1"
    assert (d / "page.md").read_text() == "# Titre\n\nTexte.\n"
    assert json.loads((d / "mesure.json").read_text())["modele"] == "qwen-vl-test"
    corps = [r for r in srv.recu if r[1] == "/v1/chat/completions"][0][2]
    image = corps["messages"][0]["content"][1]["image_url"]["url"]
    with Image.open(io.BytesIO(base64.b64decode(image.split(",", 1)[1]))) as im:
        assert max(im.size) <= 1800   # l'image est réduite avant l'envoi


def test_deja_fait_n_est_pas_relu(sonde, monkeypatch):
    racine, m = sonde
    (racine / "pages_prep").mkdir()
    _page(racine / "pages_prep" / "p1.png")
    appels = []
    m["commun"].traiter("essai", lambda p, d: appels.append(p) or {})
    m["commun"].traiter("essai", lambda p, d: appels.append(p) or {})
    assert len(appels) == 1


def test_rapport_autonome_et_sans_script(sonde):
    racine, m = sonde
    (racine / "pages_prep").mkdir()
    _page(racine / "pages_prep" / "p1.png")
    for moteur, md in (("docling", "# Titre\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n![fig](images/f.png)"),
                       ("mistral", "Texte <script>alert(1)</script>")):
        d = racine / "resultats" / moteur / "p1"
        (d / "images").mkdir(parents=True)
        Image.new("RGB", (10, 10), "blue").save(d / "images" / "f.png")
        (d / "page.md").write_text(md)
        (d / "mesure.json").write_text(json.dumps({"secondes": 3.2, "erreur": None, "pages_facturees": 1}))
    d = racine / "resultats" / "marker" / "p1"
    d.mkdir(parents=True)
    (d / "mesure.json").write_text(json.dumps({"secondes": 1.0, "erreur": "RuntimeError: panne"}))
    sortie = m["rapport"].construire()
    page = sortie.read_text()
    assert "<table>" in page and "data:image/jpeg;base64," in page
    assert "<script>" not in page.lower().split("</style>")[1]
    assert "RuntimeError: panne" in page
    assert "Docling (processeur)" in page and "Mistral OCR (en ligne)" in page


def test_inventaire_trous_surs_douteux_et_doubles(sonde):
    _, m = sonde
    inv = m["inventaire"]
    # Index du PDF :        0     1   2  3  4  5   6     7   8   9  10   11
    numeros = inv.corriger([None, 1, 2, 3, 6, 7, None, 10, 11, 11, 12, 900])
    bilan = inv.analyser(numeros)
    assert numeros[-1] is None                       # 900 ne suit pas ses voisins : écarté
    assert bilan["manquants"] == [4, 5]              # trou sans page sans numéro : sûr
    assert bilan["a_verifier"] == [{"entre": (7, 10), "manquent": 1}]   # 8 et 9 attendus, une page sans numéro
    assert bilan["doubles"] == [11]
    assert inv._plages([4, 5, 9]) == "4 à 5, 9"
