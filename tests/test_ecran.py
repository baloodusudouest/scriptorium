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
    # 0.8.0 : fiches communes ; trois services, donc trois cartes dépliées (pas de tuiles)
    page.get_by_text("Mistral OCR").first.wait_for()
    page.get_by_text("PC de calcul").first.wait_for()
    page.get_by_text("dossier d'import de Grimmory").first.wait_for()
    assert page.get_by_role("button", name="Vérifier").count() >= 1
    sans_debordement(page)
    page.goto(adresse + "/#/reglages")
    page.get_by_text("Dossier de données").wait_for()
    page.get_by_text("Go libres sur").wait_for()
    page.get_by_text("Journal").wait_for()
    page.get_by_text("Lecture par Mistral").first.wait_for()
    assert erreurs == []


def test_tuiles_du_bilan_filtrent_les_pages(navigateur, adresse):
    """0.4.1 : un clic sur une tuile du bilan ne montre que les pages en question ; un second clic montre tout."""
    page, erreurs = ouvrir(navigateur, adresse, "pc")
    page.get_by_text("Le grand livre des cocktails").click()
    page.get_by_text("Pages 4 à 5").wait_for()
    toutes = page.locator("ul[aria-label='Pages du PDF'] img").count()
    page.get_by_role("button", name=re.compile("^Manquantes")).click()
    page.get_by_text("Seulement les pages manquantes").wait_for()
    assert page.locator("ul[aria-label='Pages du PDF'] img").count() == 0
    assert page.get_by_role("button", name="Prendre la page 4 en photo").is_visible()
    page.get_by_role("button", name="Tout montrer").click()
    assert page.locator("ul[aria-label='Pages du PDF'] img").count() == toutes
    assert page.get_by_role("button", name=re.compile("^Mots à relire")).is_visible()
    assert erreurs == []


def test_page_manquante_prise_en_photo(navigateur, adresse, tmp_path):
    """0.3 : « Prendre » sur la case des pages 4 à 5 envoie une photo ; la page 4 prend sa place."""
    from tests.test_relecture import photo_de_page
    photo = tmp_path / "page4.jpg"
    photo.write_bytes(photo_de_page())
    page, erreurs = ouvrir(navigateur, adresse, "pc")
    page.get_by_text("Le grand livre des cocktails").click()
    page.get_by_text("Pages 4 à 5").wait_for()
    with page.expect_file_chooser() as choix:
        page.get_by_role("button", name="Prendre la page 4 en photo").click()
    choix.value.set_files(str(photo))
    page.get_by_role("button", name="Prendre la page 5 en photo").wait_for()   # il ne manque plus que la 5
    assert page.locator("ul[aria-label='Pages du PDF'] img").count() == 13
    assert page.get_by_label("Reprise à l'iPhone").count() == 1
    assert erreurs == []


@pytest.mark.parametrize("taille", TAILLES)
def test_relecture_d_une_page(navigateur, adresse, taille):
    """0.3 : un clic sur une page ouvre l'image et le texte ; on corrige, on enregistre, on garde en image."""
    page, erreurs = ouvrir(navigateur, adresse, taille)
    page.get_by_text("Daiquiri et compagnie").click()
    page.get_by_text("1. Les pages").wait_for()
    rang = 2 if taille == "pc" else 4             # serveur commun aux deux tailles : une page chacune
    page.locator("ul[aria-label='Pages du PDF'] a").nth(rang - 1).click()
    zone = page.get_by_label(re.compile("Texte de la page"))
    zone.wait_for()
    assert "gin" in zone.input_value()
    sans_debordement(page)
    zone.fill(f"# Daiquiri corrigé ({taille})\n\n- 60 ml de rhum\n- 25 ml de citron vert")
    page.get_by_role("button", name="Enregistrer le texte").click()
    page.get_by_text("texte corrigé à la main").wait_for()
    page.get_by_role("button", name="Garder en image").click()
    page.get_by_text("gardée en image").wait_for()
    page.get_by_role("button", name="Recomposer (texte)").click()
    page.get_by_role("button", name="Page suivante", exact=True).click()
    page.wait_for_url(re.compile(rf"/page/{rang + 1}$"))
    page.get_by_role("link", name="Daiquiri et compagnie").click()
    page.get_by_text("corrigée").first.wait_for()
    assert erreurs == []


@pytest.mark.parametrize("taille", TAILLES)
def test_mots_a_relire_de_la_contre_lecture(navigateur, adresse, taille):
    """0.3.1 : la page signalée par la contre-lecture montre le mot douteux ; « Prendre » met la lecture de Marker."""
    page, erreurs = ouvrir(navigateur, adresse, taille)
    page.get_by_text("Daiquiri et compagnie").click()
    page.get_by_text(re.compile(r"pages? à relire")).wait_for()
    rang = 5 if taille == "pc" else 6             # serveur commun aux deux tailles : une page chacune
    page.locator("ul[aria-label='Pages du PDF'] a").nth(rang - 1).click()
    page.get_by_role("heading", name="1 mot à relire").wait_for()
    sans_debordement(page)
    page.get_by_role("button", name="Remplacer « vermouth » par « vermout »").click()
    zone = page.get_by_label(re.compile("Texte de la page"))
    assert "vermout." in zone.input_value()
    page.get_by_role("button", name="Enregistrer le texte").click()
    page.get_by_text(re.compile("^Page relue")).wait_for()
    assert erreurs == []


def test_fiche_par_l_isbn_et_pdf_a5(navigateur, adresse):
    """0.4 : chercher la fiche par l'ISBN, la reprendre, l'enregistrer ; demander le PDF A5 ; choisir la couverture."""
    page, erreurs = ouvrir(navigateur, adresse, "pc")
    page.get_by_text("Daiquiri et compagnie").click()
    page.get_by_role("button", name="Modifier la fiche").click()
    page.get_by_label("ISBN").fill("978-2-07-061275-8")
    page.get_by_role("button", name="Chercher la fiche par l'ISBN").click()
    page.get_by_text("BnF propose").wait_for()
    page.get_by_role("button", name="Reprendre dans la fiche").click()
    assert page.get_by_label("Éditeur").input_value() == "Éditions Imaginaires"
    page.get_by_role("button", name="Enregistrer la fiche").click()
    page.get_by_text("ISBN 9782070612758").wait_for()
    page.get_by_text("Éditions Imaginaires, 2012").wait_for()
    page.get_by_role("button", name="Mettre en page un PDF A5").click()
    page.get_by_text("Mise en page du PDF A5").wait_for()
    page.locator("ul[aria-label='Pages du PDF'] a").nth(2).click()
    page.get_by_role("button", name="Prendre comme couverture").click()
    page.get_by_text("couverture du livre").wait_for()
    assert erreurs == []


def test_numero_change_depuis_la_page(navigateur, adresse):
    """0.4.2 : le numéro imprimé se corrige dans l'écran de la page."""
    page, erreurs = ouvrir(navigateur, adresse, "pc")
    page.get_by_text("Daiquiri et compagnie").click()
    page.get_by_text("1. Les pages").wait_for()
    page.locator("ul[aria-label='Pages du PDF'] a").nth(0).click()
    champ = page.get_by_label("Numéro imprimé")
    champ.wait_for()
    champ.fill("1")
    page.get_by_role("button", name="Enregistrer le numéro").click()
    page.get_by_role("heading", name="Page 1").wait_for()
    page.get_by_text("posé à la main").wait_for()
    assert erreurs == []


def test_isbn_par_la_photo_du_code_barres(navigateur, adresse, tmp_path):
    """0.4.3 : photographier le code-barres remplit l'ISBN et cherche aussitôt la fiche."""
    from tests.test_fiche import photo_code_barres
    photo = tmp_path / "code.jpg"
    photo.write_bytes(photo_code_barres())
    page, erreurs = ouvrir(navigateur, adresse, "iphone")
    page.get_by_text("Daiquiri et compagnie").click()
    page.get_by_role("button", name="Modifier la fiche").click()
    page.get_by_label("ISBN").fill("")
    with page.expect_file_chooser() as choix:
        page.get_by_role("button", name="Photographier le code-barres").click()
    choix.value.set_files(str(photo))
    page.get_by_text("BnF propose").wait_for()
    assert page.get_by_label("ISBN").input_value() == "9782070612758"
    sans_debordement(page)
    assert erreurs == []


@pytest.mark.parametrize("taille", TAILLES)
def test_reglages_et_restaurer(navigateur, adresse, taille):
    """0.6 : la tuile Usage change un réglage ; la tuile Restaurer montre les différences d'une sauvegarde (faux Anneau)."""
    page, erreurs = ouvrir(navigateur, adresse, taille)
    page.goto(adresse + "/#/reglages")
    form = page.get_by_role("form", name="Réglages d'usage")
    form.wait_for()
    sans_debordement(page)
    champ = page.get_by_label("Définition des pages découpées")
    assert champ.input_value() == "120"
    champ.fill("130" if taille == "pc" else "120")
    if taille == "pc":
        page.get_by_role("button", name="Enregistrer les réglages").click()
        page.get_by_text("Réglages enregistrés.").wait_for()
    page.get_by_role("button", name="Voir les sauvegardes").click()
    differences = page.get_by_role("list", name="Différences avec la sauvegarde")
    # Serveur commun aux deux tailles : le passage PC restaure le 14 ; le passage iPhone regarde alors le 15
    page.get_by_label("Sauvegarde du").select_option("2026-11-14" if taille == "pc" else "2026-11-15")
    differences.wait_for()
    assert "Recherche en ligne de la fiche" in differences.inner_text()
    sans_debordement(page)
    if taille == "pc":
        page.get_by_role("button", name="Restaurer ces réglages").click()
        page.get_by_text(re.compile("^Restauré :")).wait_for()
        assert not page.get_by_label("Recherche en ligne de la fiche").is_checked()
        page.get_by_text("Restauration des réglages").first.wait_for()      # ligne au journal
    assert erreurs == []
