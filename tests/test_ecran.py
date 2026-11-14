"""Tests d'écran : le serveur de démonstration (tools/demo.py) ouvert dans un vrai navigateur, sur PC et iPhone.

À chaque écran : aucune erreur de page, aucun débordement horizontal. Sautés si Playwright ou l'interface
compilée manquent (la CI les installe : voir .github/workflows/tests.yml).
"""
from __future__ import annotations

import os
import re
import shutil
import socket
import threading
import time
from pathlib import Path

import pytest

pw = pytest.importorskip("playwright.sync_api")
STATIQUE = Path(__file__).resolve().parents[1] / "app" / "static" / "index.html"
pytestmark = pytest.mark.skipif(not STATIQUE.exists(), reason="interface non compilée (cd frontend && npx vite build)")

TAILLES = {"pc": {"width": 1366, "height": 900}, "iphone": {"width": 390, "height": 844}}


@pytest.fixture(scope="module")
def adresse(tmp_path_factory):
    from tools import demo
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    threading.Thread(target=demo.lancer, args=(port, tmp_path_factory.mktemp("demo")), daemon=True).start()
    import httpx
    for _ in range(200):
        try:
            if httpx.get(f"http://127.0.0.1:{port}/health", timeout=1).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.2)
    return f"http://127.0.0.1:{port}"


@pytest.fixture(scope="module")
def navigateur():
    with pw.sync_playwright() as p:
        chrome = os.environ.get("CHROME") or shutil.which("google-chrome")
        b = p.chromium.launch(executable_path=chrome, args=["--no-sandbox"]) if chrome else p.chromium.launch()
        yield b
        b.close()


def ouvrir(navigateur, adresse, taille):
    page = navigateur.new_page(viewport=TAILLES[taille])
    erreurs = []
    page.on("pageerror", lambda e: erreurs.append(str(e)))
    page.goto(adresse + "/")
    page.fill("#mot-de-passe", "demo-demo-demo")
    page.click("button[type=submit]")
    page.locator("ul[aria-label=Livres] li").first.wait_for()
    return page, erreurs


def sans_debordement(page):
    assert not page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")


@pytest.mark.parametrize("taille", TAILLES)
def test_livres_et_inventaire(navigateur, adresse, taille):
    page, erreurs = ouvrir(navigateur, adresse, taille)
    assert page.locator("ul[aria-label=Livres] li").count() == 2
    sans_debordement(page)
    page.get_by_text("Le grand livre des cocktails").click()
    page.get_by_text("1. Les pages").wait_for()
    # Les pages 4 et 5 manquent : la case apparaît à leur place
    page.get_by_text("Pages 4 à 5").wait_for()
    assert page.locator("ul[aria-label='Pages du PDF'] img").count() == 12
    sans_debordement(page)
    # Écarter (ou remettre) une page en double : le bouton change de nom. Puis confirmer l'inventaire.
    # (Le serveur est commun aux deux tailles : le second passage trouve l'état laissé par le premier.)
    case = page.locator("ul[aria-label='Pages du PDF'] li").filter(has=page.locator("img")).nth(7)
    bouton = case.get_by_role("button", name=re.compile("Écarter|Remettre"))
    avant = bouton.inner_text()
    bouton.click()
    case.get_by_role("button", name="Remettre" if avant == "Écarter" else "Écarter").wait_for()
    if page.get_by_role("button", name="Confirmer l'inventaire").count():
        page.get_by_role("button", name="Confirmer l'inventaire").click()
    page.get_by_text("Inventaire confirmé").wait_for()
    assert erreurs == []


@pytest.mark.parametrize("taille", TAILLES)
def test_livre_fabrique_et_services(navigateur, adresse, taille):
    page, erreurs = ouvrir(navigateur, adresse, taille)
    page.get_by_text("Daiquiri et compagnie").click()
    page.get_by_text("3. Le livre").wait_for()
    assert page.get_by_role("link", name="EPUB").get_attribute("href").endswith("/telecharger/epub")
    page.get_by_role("button", name="Déposer dans Grimmory").wait_for()
    sans_debordement(page)
    page.goto(adresse + "/#/connexion")
    page.get_by_text("Mistral OCR").first.wait_for()
    page.get_by_role("button", name="Grimmory").click()
    page.get_by_text("dossier d'import de Grimmory").wait_for()
    sans_debordement(page)
    page.goto(adresse + "/#/reglages")
    page.get_by_text("Journal").wait_for()
    page.get_by_text("Lecture par Mistral").first.wait_for()
    assert erreurs == []
