"""0.3 : reprise des pages manquantes à l'iPhone et relecture page par page.

Rien n'est envoyé à Mistral : app.mistral.lire_page est remplacée par une fausse lecture.
"""
from __future__ import annotations

import io
import zipfile

from PIL import Image, ImageDraw

from app import capture, main, mistral
from tests.test_livres import client, importer, pdf_livre  # noqa: F401  (fixture)


def photo_de_page(largeur=1500, hauteur=2000, tournee=False) -> bytes:
    """Une page blanche posée sur une table sombre, telle que l'iPhone la prend."""
    im = Image.new("RGB", (largeur, hauteur), (40, 32, 28))
    d = ImageDraw.Draw(im)
    d.rectangle((150, 120, largeur - 150, hauteur - 120), fill="white")
    for y in range(300, hauteur - 300, 50):
        d.line((250, y, largeur - 250, y), fill="black", width=6)
    if tournee:
        im = im.rotate(90, expand=True)
    t = io.BytesIO()
    im.save(t, "JPEG", quality=90)
    return t.getvalue()


def lecture_numerotee(numeros):
    suite = iter(numeros)

    def lire_page(image, cle, url, modele, client=None):
        n = next(suite)
        return mistral.PageLue(f"# Recette {n}\n\nTexte de la page {n}, assez long pour être lu.\n\n{n}", {}, 1, "", n)
    return lire_page


def livre_lu(client, monkeypatch, numeros=(10, 11, 13, 14)):
    livre_id = importer(client, pdf_livre([None] * len(numeros)))
    main.ETAT["travail"].tout_faire()
    monkeypatch.setattr(mistral, "lire_page", lecture_numerotee(numeros))
    assert client.post(f"/api/livres/{livre_id}/lecture").status_code == 200
    main.ETAT["travail"].tout_faire()
    return livre_id


# ---------------------------------------------------------------- photo

def test_photo_recadree_et_reduite():
    jpeg = capture.preparer_photo(photo_de_page(3000, 4000))
    with Image.open(io.BytesIO(jpeg)) as im:
        assert im.format == "JPEG" and max(im.size) <= 2400
        assert im.size[0] < 1780                                   # sans recadrage : 1800
        assert min(im.convert("L").getpixel((40, 40)), im.convert("L").getpixel((im.size[0] - 40, 40))) > 120   # plus de table (marge de 1 %)


def test_photo_illisible_refusee():
    try:
        capture.preparer_photo(b"pas une image")
    except ValueError:
        return
    raise AssertionError("une photo illisible doit être refusée")


# ---------------------------------------------------------------- page reprise insérée à sa place

def test_page_reprise_inseree_a_sa_place_puis_lue(client, monkeypatch):
    livre_id = livre_lu(client, monkeypatch)
    v = client.get(f"/api/livres/{livre_id}").json()
    assert v["bilan"]["inventaire"]["manquantes"] == [12]
    r = client.put(f"/api/livres/{livre_id}/pages/ajouter?numero=12", content=photo_de_page())
    assert r.status_code == 200, r.text
    v = r.json()
    assert [p["numero"] for p in v["liste_pages"]] == [10, 11, 12, 13, 14]
    reprise = v["liste_pages"][2]
    assert reprise["source"] == "photo" and reprise["lecture"] == "attente" and reprise["rang"] == r.json()["ajoutee"]
    assert v["bilan"]["inventaire"]["manquantes"] == []
    assert v["etat"] == "lecture"            # le livre n'est plus prêt : une page attend sa lecture
    # Mistral la lit comme les autres ; son numéro (posé à la main) n'est pas remplacé
    monkeypatch.setattr(mistral, "lire_page", lecture_numerotee([99]))
    client.post(f"/api/livres/{livre_id}/lecture")
    main.ETAT["travail"].tout_faire()
    v = client.get(f"/api/livres/{livre_id}").json()
    assert v["etat"] == "pret" and [p["numero"] for p in v["liste_pages"]] == [10, 11, 12, 13, 14]
    assert client.get(f"/api/livres/{livre_id}/pages/{reprise['rang']}.jpg").status_code == 200


def test_page_reprise_avant_la_premiere_et_apres_la_derniere(client, monkeypatch):
    livre_id = livre_lu(client, monkeypatch)
    client.put(f"/api/livres/{livre_id}/pages/ajouter?numero=9", content=photo_de_page())
    v = client.put(f"/api/livres/{livre_id}/pages/ajouter?numero=15", content=photo_de_page()).json()
    assert [p["numero"] for p in v["liste_pages"]] == [9, 10, 11, 13, 14, 15]


def test_page_reprise_refusee_si_photo_illisible_ou_numero_absurde(client, monkeypatch):
    livre_id = livre_lu(client, monkeypatch)
    assert client.put(f"/api/livres/{livre_id}/pages/ajouter?numero=12", content=b"rien").status_code == 422
    assert client.put(f"/api/livres/{livre_id}/pages/ajouter?numero=0", content=photo_de_page()).status_code == 422


def test_page_tournee(client, monkeypatch):
    livre_id = livre_lu(client, monkeypatch)
    rang = client.put(f"/api/livres/{livre_id}/pages/ajouter?numero=12", content=photo_de_page()).json()["ajoutee"]
    avant = Image.open(io.BytesIO(client.get(f"/api/livres/{livre_id}/pages/{rang}.jpg").content)).size
    assert client.post(f"/api/livres/{livre_id}/pages/{rang}/tourner").status_code == 200
    apres = Image.open(io.BytesIO(client.get(f"/api/livres/{livre_id}/pages/{rang}.jpg").content)).size
    assert apres == (avant[1], avant[0])


# ---------------------------------------------------------------- relecture

def test_texte_corrige_a_la_main_garde_et_pas_ecrase(client, monkeypatch):
    livre_id = livre_lu(client, monkeypatch)
    r = client.post(f"/api/livres/{livre_id}/pages/2/texte", json={"markdown": "# Recette corrigée\n\nGin, citron.\n\n11"})
    assert r.status_code == 200
    page = next(p for p in r.json()["liste_pages"] if p["rang"] == 2)
    assert page["texte_main"] == 1 and page["lecture"] == "faite"
    assert "corrigée" in client.get(f"/api/livres/{livre_id}/pages/2/texte").json()["markdown"]
    # Une nouvelle lecture du livre ne touche pas à la page corrigée
    monkeypatch.setattr(mistral, "lire_page", lambda *a, **k: (_ for _ in ()).throw(AssertionError("relue")))
    client.post(f"/api/livres/{livre_id}/lecture")
    main.ETAT["travail"].tout_faire()
    assert "corrigée" in client.get(f"/api/livres/{livre_id}/pages/2/texte").json()["markdown"]


def test_relire_une_seule_page(client, monkeypatch):
    livre_id = livre_lu(client, monkeypatch)
    client.post(f"/api/livres/{livre_id}/pages/2/texte", json={"markdown": "texte à la main"})
    assert client.post(f"/api/livres/{livre_id}/pages/2/relire").status_code == 200
    appels = []

    def lire_page(*a, **k):
        appels.append(1)
        return mistral.PageLue("# Relue\n\nTexte relu par Mistral, assez long.\n\n11", {}, 1, "", 11)
    monkeypatch.setattr(mistral, "lire_page", lire_page)
    main.ETAT["travail"].tout_faire()
    assert len(appels) == 1                  # seule cette page est repartie chez Mistral
    assert "Relue" in client.get(f"/api/livres/{livre_id}/pages/2/texte").json()["markdown"]
    v = client.get(f"/api/livres/{livre_id}").json()
    assert v["etat"] == "pret" and next(p for p in v["liste_pages"] if p["rang"] == 2)["texte_main"] == 0


def test_page_gardee_en_image_dans_l_epub(client, monkeypatch):
    livre_id = livre_lu(client, monkeypatch)
    assert client.post(f"/api/livres/{livre_id}/pages/3", json={"rendu": "photo"}).status_code == 422
    v = client.post(f"/api/livres/{livre_id}/pages/3", json={"rendu": "image"}).json()
    assert next(p for p in v["liste_pages"] if p["rang"] == 3)["rendu_choisi"] == "image"
    client.post(f"/api/livres/{livre_id}/inventaire/confirmer")
    r = client.post(f"/api/livres/{livre_id}/fabriquer").json()
    assert r["fabrication"]["pages_en_image"] == 1
    with zipfile.ZipFile(io.BytesIO(client.get(f"/api/livres/{livre_id}/telecharger/epub").content)) as z:
        textes = " ".join(z.read(n).decode() for n in z.namelist() if n.endswith(".xhtml"))
    assert "Recette 13" not in textes and "Recette 11" in textes   # la page 3 (n° 13) est entrée en image


# ---------------------------------------------------------------- 0.6.1 : une panne inattendue arrête la lecture

def test_panne_inattendue_arrete_la_lecture_sans_relancer(client, monkeypatch):
    livre_id = importer(client, pdf_livre([None, None]))
    main.ETAT["travail"].tout_faire()
    appels = []

    def lire_page(image, cle, url, modele, client=None):
        appels.append(1)
        raise OSError("disque plein")
    monkeypatch.setattr(mistral, "lire_page", lire_page)
    assert client.post(f"/api/livres/{livre_id}/lecture").status_code == 200
    for _ in range(3):                       # la boucle de fond repasse plusieurs fois
        main.ETAT["travail"].tout_faire()
    assert appels == [1]                     # une seule page payée, pas une relance toutes les 3 s
    v = client.get(f"/api/livres/{livre_id}").json()
    assert "disque plein" in v["erreur"]


def test_reponse_illisible_de_mistral():
    import httpx

    def repondre(requete):
        return httpx.Response(200, text="<html>portail</html>")
    with httpx.Client(transport=httpx.MockTransport(repondre)) as c:
        try:
            mistral.lire_page(b"x", "cle", "https://mistral.exemple/ocr", "m", client=c)
        except mistral.ErreurMistral as e:
            assert "illisible" in str(e)
            return
    raise AssertionError("une réponse illisible doit lever ErreurMistral")
