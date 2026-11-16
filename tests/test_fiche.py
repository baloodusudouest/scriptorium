"""0.4.0 : fiche par l'ISBN (BnF puis Open Library), couverture, PDF A5.

Rien ne part sur Internet : la BnF et Open Library sont simulées par un faux serveur httpx.
"""
from __future__ import annotations

import io
import zipfile

import httpx
import pypdfium2 as pdfium
import pytest

from app import main, mistral, notice
from tests.test_livres import client, importer, pdf_livre  # noqa: F401  (fixture)
from tests.test_relecture import lecture_numerotee

BNF_XML = """<?xml version="1.0" encoding="UTF-8"?>
<srw:searchRetrieveResponse xmlns:srw="http://www.loc.gov/zing/srw/">
 <srw:numberOfRecords>1</srw:numberOfRecords>
 <srw:records><srw:record><srw:recordData>
  <oai_dc:dc xmlns:oai_dc="http://www.openarchives.org/OAI/2.0/oai_dc/" xmlns:dc="http://purl.org/dc/elements/1.1/">
   <dc:title>Le grand livre des cocktails [Texte imprimé] / Jeanne Martin ; photographies de Paul Roux</dc:title>
   <dc:creator>Martin, Jeanne (1971-....). Auteur du texte</dc:creator>
   <dc:publisher>Éditions du Comptoir (Bordeaux)</dc:publisher>
   <dc:date>2016</dc:date>
  </oai_dc:dc>
 </srw:recordData></srw:record></srw:records>
</srw:searchRetrieveResponse>"""
BNF_VIDE = """<?xml version="1.0"?><srw:searchRetrieveResponse xmlns:srw="http://www.loc.gov/zing/srw/">
<srw:numberOfRecords>0</srw:numberOfRecords></srw:searchRetrieveResponse>"""
ISBN = "9782070612758"      # clé juste
ISBN10 = "2070612759"       # le même en ISBN-10


def faux_web(bnf=BNF_XML, ol=None, panne=False):
    def repondre(requete: httpx.Request):
        if panne:
            raise httpx.ConnectError("hors ligne", request=requete)
        if requete.url.host == "catalogue.bnf.fr":
            assert "fuzzyISBN" in requete.url.params["query"]
            return httpx.Response(200, text=bnf)
        return httpx.Response(200, json=ol or {})
    return httpx.Client(transport=httpx.MockTransport(repondre))


# ---------------------------------------------------------------- ISBN

def test_isbn_valide_et_converti():
    assert notice.isbn13("978-2-07-061275-8") == ISBN
    assert notice.isbn13(ISBN10) == ISBN
    assert notice.isbn13("978-2-07-061275-7") is None          # mauvaise clé
    assert notice.isbn13("2-07-061275-8") is None


def test_isbn_repere_dans_le_texte():
    texte = "Dépôt légal : mars 2016\n\nISBN : 978-2-07-061275-8\n\nImprimé en France. Prix 25 €. Tél. 05 53 00 00 00"
    assert notice.trouver_isbn(texte) == [ISBN]
    assert notice.trouver_isbn("ISBN 2-07-061275-9 (broché)") == [ISBN]
    assert notice.trouver_isbn("Code 9782070612757 faux") == []


# ---------------------------------------------------------------- recherche

def test_notice_bnf():
    n = notice.chercher(ISBN, faux_web())
    assert n == {"titre": "Le grand livre des cocktails", "auteur": "Jeanne Martin", "editeur": "Éditions du Comptoir",
                 "annee": "2016", "isbn": ISBN, "source": "BnF"}


def test_notice_open_library_si_la_bnf_ne_connait_pas():
    ol = {f"ISBN:{ISBN}": {"title": "Cocktails", "subtitle": "les classiques", "authors": [{"name": "Ann Smith"}, {"name": "Bob Lee"}],
                           "publishers": [{"name": "Bar Press"}], "publish_date": "May 2019"}}
    n = notice.chercher(ISBN, faux_web(bnf=BNF_VIDE, ol=ol))
    assert n["source"] == "Open Library" and n["titre"] == "Cocktails : les classiques"
    assert n["auteur"] == "Ann Smith, Bob Lee" and n["annee"] == "2019"
    assert notice.chercher(ISBN, faux_web(bnf=BNF_VIDE)) is None


def test_notice_injoignable():
    with pytest.raises(notice.ErreurNotice):
        notice.chercher(ISBN, faux_web(panne=True))


# ---------------------------------------------------------------- routes

def livre_lu(client, monkeypatch, n=3, copyright_page=True):  # noqa: F811
    livre_id = importer(client, pdf_livre([None] * n))
    main.ETAT["travail"].tout_faire()
    lire = lecture_numerotee(list(range(10, 10 + n)))

    def avec_isbn(*a, **k):
        page = lire(*a, **k)
        if copyright_page and page.numero == 10 + n - 1:
            page = mistral.PageLue(page.markdown + "\n\nISBN 978-2-07-061275-8", {}, 1, "", page.numero)
        return page
    monkeypatch.setattr(mistral, "lire_page", avec_isbn)
    client.post(f"/api/livres/{livre_id}/lecture")
    main.ETAT["travail"].tout_faire()
    return livre_id


def test_fiche_cherchee_par_l_isbn_du_livre_puis_enregistree(client, monkeypatch):  # noqa: F811
    livre_id = livre_lu(client, monkeypatch)
    monkeypatch.setattr(notice, "chercher", lambda isbn, client=None: notice._bnf(isbn, faux_web()))
    r = client.post(f"/api/livres/{livre_id}/notice", json={}).json()
    assert r["isbn_trouves"] == [ISBN] and r["notice"]["auteur"] == "Jeanne Martin"
    assert client.get(f"/api/livres/{livre_id}").json()["isbn"] == ""       # proposition seulement
    v = client.post(f"/api/livres/{livre_id}/fiche", json={**r["notice"], "isbn": ISBN10}).json()
    assert (v["titre"], v["auteur"], v["editeur"], v["annee"], v["isbn"]) == (
        "Le grand livre des cocktails", "Jeanne Martin", "Éditions du Comptoir", "2016", ISBN)


def test_fiche_refuse_un_isbn_faux_et_une_annee_bizarre(client, monkeypatch):  # noqa: F811
    livre_id = livre_lu(client, monkeypatch, copyright_page=False)
    assert client.post(f"/api/livres/{livre_id}/fiche", json={"isbn": "978-2-07-061275-7"}).status_code == 422
    assert client.post(f"/api/livres/{livre_id}/fiche", json={"annee": "16"}).status_code == 422
    r = client.post(f"/api/livres/{livre_id}/notice", json={}).json()
    assert r["isbn_trouves"] == [] and "Aucun ISBN" in r["message"]


def test_recherche_coupee(client, monkeypatch):  # noqa: F811
    livre_id = livre_lu(client, monkeypatch, n=1)
    assert client.put("/api/reglages", json={"recherche_web": False}).status_code == 200    # 0.6 : écran Réglages
    r = client.post(f"/api/livres/{livre_id}/notice", json={"isbn": ISBN})
    assert r.status_code == 409 and "Réglages" in r.json()["detail"]


def test_epub_avec_fiche_et_couverture_choisie(client, monkeypatch):  # noqa: F811
    livre_id = livre_lu(client, monkeypatch)
    client.post(f"/api/livres/{livre_id}/fiche", json={"titre": "Cocktails", "auteur": "Jeanne Martin, Paul Roux",
                                                      "editeur": "Éditions du Comptoir", "annee": "2016", "isbn": ISBN})
    assert client.post(f"/api/livres/{livre_id}/couverture", json={"rang": 99}).status_code == 404
    assert client.post(f"/api/livres/{livre_id}/couverture", json={"rang": 2}).json()["couverture"] == 2
    r = client.post(f"/api/livres/{livre_id}/fabriquer").json()
    assert r["fabrication"]["couverture"]
    with zipfile.ZipFile(io.BytesIO(client.get(f"/api/livres/{livre_id}/telecharger/epub").content)) as z:
        opf = next(z.read(n).decode() for n in z.namelist() if n.endswith(".opf"))
        assert f"urn:isbn:{ISBN}" in opf and "Éditions du Comptoir" in opf and "<dc:date>2016</dc:date>" in opf
        assert opf.count("<dc:creator") == 2 and 'name="cover"' in opf
        assert any(n.endswith("couverture.jpg") for n in z.namelist())


def test_pdf_a5_fabrique_en_tache_de_fond(client, monkeypatch):  # noqa: F811
    livre_id = livre_lu(client, monkeypatch, n=4)
    client.post(f"/api/livres/{livre_id}/pages/3", json={"rendu": "image"})
    client.post(f"/api/livres/{livre_id}/fiche", json={"titre": "Cocktails", "auteur": "Jeanne Martin", "isbn": ISBN})
    v = client.post(f"/api/livres/{livre_id}/pdf").json()
    assert v["pdf_demande"] == 1
    assert client.get(f"/api/livres/{livre_id}/telecharger/pdf").status_code == 404
    main.ETAT["travail"].tout_faire()
    v = client.get(f"/api/livres/{livre_id}").json()
    assert v["pdf_demande"] == 0 and not v["pdf_erreur"] and v["bilan"]["pdf"]
    contenu = client.get(f"/api/livres/{livre_id}/telecharger/pdf").content
    pdf = pdfium.PdfDocument(contenu)
    largeur, hauteur = pdf[0].get_size()
    assert round(largeur / 72 * 25.4) == 148 and round(hauteur / 72 * 25.4) == 210      # A5
    texte = " ".join(pdf[i].get_textpage().get_text_range() for i in range(len(pdf)))
    assert "Recette 10" in texte and "p. 11" in texte and "Sommaire" in texte and ISBN in texte
    assert "Recette 12" not in texte                                                    # page gardée en image
    assert len(pdf) >= 6                                    # couverture, titre, sommaire, texte, page en image, colophon


def test_ingredients_avec_completez():
    from app.fabrication import lister_ingredients
    texte = "50 ml de rhum\n1/2 citron vert\n8 feuilles de menthe\nComplétez avec de l'eau gazeuse"
    assert lister_ingredients(texte).count("- ") == 4


# ---------------------------------------------------------------- code-barres (0.4.3)

def photo_code_barres(texte="9782070612758", tourne=4) -> bytes:
    import numpy as np
    import zxingcpp
    from PIL import Image, ImageOps
    code = Image.fromarray(np.array(zxingcpp.create_barcode(texte, zxingcpp.BarcodeFormat.EAN13).to_image(scale=4))).convert("RGB")
    code = ImageOps.expand(code, 20, "white").rotate(tourne, expand=True, fillcolor=(180, 150, 120))
    fond = Image.new("RGB", (1600, 1200), (180, 150, 120))
    fond.paste(code, (500, 400))
    t = io.BytesIO()
    fond.save(t, "JPEG", quality=85)
    return t.getvalue()


def test_isbn_lu_sur_la_photo_du_code_barres(client, monkeypatch):  # noqa: F811
    livre_id = livre_lu(client, monkeypatch, n=1)
    r = client.put(f"/api/livres/{livre_id}/isbn/photo", content=photo_code_barres())
    assert r.status_code == 200 and r.json()["isbn"] == ISBN
    assert client.get(f"/api/livres/{livre_id}").json()["isbn"] == ""     # rien n'est enregistré d'office


def test_photo_sans_code_barres_ou_illisible(client, monkeypatch):  # noqa: F811
    from tests.test_relecture import photo_de_page
    livre_id = livre_lu(client, monkeypatch, n=1)
    r = client.put(f"/api/livres/{livre_id}/isbn/photo", content=photo_de_page())
    assert r.status_code == 422 and "Aucun code-barres" in r.json()["detail"]
    assert client.put(f"/api/livres/{livre_id}/isbn/photo", content=b"rien").status_code == 422
    # Un EAN-13 qui n'est pas un ISBN (produit du commerce) est ignoré
    assert client.put(f"/api/livres/{livre_id}/isbn/photo", content=photo_code_barres("3017620422003")).status_code == 422
