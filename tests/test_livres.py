"""Le chemin d'un livre en 0.1 : import par morceaux, découpe, inventaire, lecture (faux Mistral), EPUB, dépôt.

Rien n'est envoyé à Mistral : app.mistral.lire_page est remplacée par une fausse lecture. Le vrai client
(lire_page) est testé à part, avec un faux serveur httpx.
"""
from __future__ import annotations

import base64
import dataclasses
import glob
import io
import json
import re
import shutil
import zipfile

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

from app import fabrication, inventaire, main, mistral
from app.config import Config

MDP = "mot-de-passe-de-test"
TESSERACT = shutil.which("tesseract") is not None
MORCEAU = 64 * 1024


def _police(taille):
    polices = glob.glob("/usr/share/fonts/**/DejaVuSerif.ttf", recursive=True) + glob.glob("/usr/share/fonts/**/*.ttf", recursive=True)
    return ImageFont.truetype(polices[0], taille) if polices else ImageFont.load_default()


def pdf_livre(numeros: list[int | None]) -> bytes:
    """Un faux livre : du texte, et le numéro imprimé en bas de chaque page (None : page sans numéro)."""
    corps, chiffres = _police(20), _police(28)
    pages = []
    for n in numeros:
        im = Image.new("RGB", (1240, 1754), "white")
        d = ImageDraw.Draw(im)
        for y in range(200, 1400, 40):
            d.text((150, y), "Le blanc d'oeuf ajoute de la viscosite au cocktail.", font=corps, fill="black")
        if n is not None:
            d.text((600 if n % 2 else 1050, 1680), str(n), font=chiffres, fill="black")
        pages.append(im)
    t = io.BytesIO()
    pages[0].save(t, "PDF", save_all=True, append_images=pages[1:], resolution=150)
    return t.getvalue()


@pytest.fixture()
def client(tmp_path):
    (tmp_path / "bookdrop").mkdir()
    main.ETAT.clear()
    main.ETAT["cfg"] = Config(password=MDP, data=tmp_path / "data", static=tmp_path / "static", attente_connexion=False,
                              travail_auto=False, mistral_cle="cle-de-test", bookdrop=tmp_path / "bookdrop")
    with TestClient(main.app) as c:
        assert c.post("/api/connexion", json={"mot_de_passe": MDP}).status_code == 200
        assert c.put("/api/reglages", json={"dpi": 100}).status_code == 200      # 0.6 : réglage de l'écran Réglages
        yield c
    main.ETAT.clear()


def importer(client, contenu: bytes, titre="Cocktails", couper_a: int | None = None) -> int:
    r = client.post("/api/livres", json={"titre": titre, "auteur": "Auteur Inventé", "nom_fichier": "livre.pdf", "octets": len(contenu)})
    assert r.status_code == 200, r.text
    livre_id = r.json()["id"]
    debut = 0
    while debut < len(contenu):
        fin = min(len(contenu), debut + MORCEAU)
        if couper_a is not None and debut <= couper_a < fin:
            # Coupure : le même morceau est renvoyé deux fois ; le second envoi doit être refusé (409) puis reprendre.
            client.put(f"/api/livres/{livre_id}/envoi?debut={debut}", content=contenu[debut:fin])
            r = client.put(f"/api/livres/{livre_id}/envoi?debut={debut}", content=contenu[debut:fin])
            assert r.status_code == 409
            debut = r.json()["recus"]
            couper_a = None
            continue
        r = client.put(f"/api/livres/{livre_id}/envoi?debut={debut}", content=contenu[debut:fin])
        assert r.status_code == 200, r.text
        debut = r.json()["recus"]
    r = client.post(f"/api/livres/{livre_id}/envoi/fin")
    assert r.status_code == 200, r.text
    return livre_id


def fausse_lecture(douteuses=()):
    pixel = io.BytesIO()
    Image.new("RGB", (20, 20), "red").save(pixel, "JPEG")

    def lire_page(image, cle, url, modele, client=None):
        assert cle == "cle-de-test"
        with Image.open(io.BytesIO(image)) as im:   # c'est bien une page
            lue = im.size
        n = lire_page.appels = getattr(lire_page, "appels", 0) + 1
        if n in douteuses:
            return mistral.PageLue('[{"box_2d": [0, 0, 999, 999]}]', {}, 1, "sortie de Mistral illisible")
        md = f"# Recette {n}\n\nB\n\n45 ml de *gin* ({lue[0]} px)\n\n![img-0.jpeg](img-0.jpeg)\n\n{n + 1}"
        return mistral.PageLue(md, {"img-0.jpeg": pixel.getvalue()}, 1, "")
    return lire_page


# ---------------------------------------------------------------- import et découpe

def test_import_par_morceaux_avec_reprise_puis_decoupe(client):
    contenu = pdf_livre([1, 2, 3])
    livre_id = importer(client, contenu, couper_a=MORCEAU + 10)
    source = main.ETAT["base"].dossier(livre_id) / "source.pdf"
    assert source.read_bytes() == contenu          # aucun morceau en double, aucun trou
    assert client.get(f"/api/livres/{livre_id}").json()["etat"] == "decoupe"
    main.ETAT["travail"].tout_faire()
    v = client.get(f"/api/livres/{livre_id}").json()
    assert v["etat"] == "inventaire" and v["bilan"]["pages"] == 3
    assert client.get(f"/api/livres/{livre_id}/pages/1.jpg").headers["content-type"] == "image/jpeg"
    vignette = client.get(f"/api/livres/{livre_id}/pages/1.jpg?cote=200")
    with Image.open(io.BytesIO(vignette.content)) as im:
        assert max(im.size) <= 200


def test_import_refuse_autre_chose_qu_un_pdf(client):
    r = client.post("/api/livres", json={"titre": "x", "nom_fichier": "x.pdf", "octets": 10})
    livre_id = r.json()["id"]
    client.put(f"/api/livres/{livre_id}/envoi?debut=0", content=b"pas un pdf")
    assert client.post(f"/api/livres/{livre_id}/envoi/fin").status_code == 422
    assert client.post("/api/livres", json={"titre": "x", "nom_fichier": "x.epub", "octets": 10}).status_code == 422
    assert client.post("/api/livres", json={"titre": "", "nom_fichier": "x.pdf", "octets": 10}).status_code == 422


def test_morceau_trop_gros_refuse(client):
    r = client.post("/api/livres", json={"titre": "x", "nom_fichier": "x.pdf", "octets": 5})
    livre_id = r.json()["id"]
    assert client.put(f"/api/livres/{livre_id}/envoi?debut=0", content=b"%PDF-123456").status_code == 413


@pytest.mark.skipif(not TESSERACT, reason="Tesseract absent")
def test_inventaire_trouve_les_pages_manquantes_et_doubles(client):
    livre_id = importer(client, pdf_livre([None, 1, 2, 3, 4, 7, 8, 9, 9, 10]))
    main.ETAT["travail"].tout_faire()
    v = client.get(f"/api/livres/{livre_id}").json()
    inv = v["bilan"]["inventaire"]
    assert inv["manquantes"] == [5, 6]
    assert inv["doubles"] == [9]
    assert 1 in inv["sans_numero"]
    # La page en double est écartée : elle sort du livre et de l'inventaire.
    rang_double = [p["rang"] for p in v["liste_pages"] if p["numero"] == 9][1]
    v = client.post(f"/api/livres/{livre_id}/pages/{rang_double}", json={"ecartee": True}).json()
    assert v["bilan"]["inventaire"]["doubles"] == [] and v["bilan"]["ecartees"] == 1


def test_inventaire_analyse_et_correction():
    numeros = inventaire.corriger([None, 1, 2, 3, 6, 7, None, 10, 11, 11, 12, 900])
    assert numeros[-1] is None
    bilan = inventaire.analyser(numeros)
    assert bilan["manquantes"] == [4, 5]
    assert bilan["a_verifier"] == [{"entre": [7, 10], "manquent": 1}]
    assert bilan["doubles"] == [11]


def test_numero_corrige_a_la_main(client):
    livre_id = importer(client, pdf_livre([1, 2, 3]))
    main.ETAT["travail"].tout_faire()
    v = client.post(f"/api/livres/{livre_id}/pages/2", json={"numero": 41}).json()
    assert [p["numero"] for p in v["liste_pages"]][1] == 41
    assert client.post(f"/api/livres/{livre_id}/pages/2", json={"numero": 0}).status_code == 422
    assert client.post(f"/api/livres/{livre_id}/pages/2", json={"numero": "douze"}).status_code == 422


# ---------------------------------------------------------------- lecture, fabrication, dépôt

def test_chemin_complet_jusqu_a_grimmory(client, monkeypatch, tmp_path):
    livre_id = importer(client, pdf_livre([1, 2, 3, 4]))
    main.ETAT["travail"].tout_faire()
    v = client.get(f"/api/livres/{livre_id}").json()
    assert v["bilan"]["estimation"]["pages"] == 4

    monkeypatch.setattr(mistral, "lire_page", fausse_lecture(douteuses={3}))
    assert client.post(f"/api/livres/{livre_id}/lecture").status_code == 200
    main.ETAT["travail"].tout_faire()
    v = client.get(f"/api/livres/{livre_id}").json()
    assert v["etat"] == "pret"
    assert v["bilan"]["lecture"] == {"attente": 0, "faite": 3, "douteuse": 1, "erreur": 0}
    assert v["bilan"]["facturees"] == 4

    r = client.post(f"/api/livres/{livre_id}/fabriquer").json()
    assert client.post(f"/api/livres/{livre_id}/deposer").status_code == 409      # inventaire pas confirmé
    client.post(f"/api/livres/{livre_id}/inventaire/confirmer")
    # La page 3 (douteuse, en image) ne commence pas par un titre : elle rejoint le fichier de la page 2
    assert r["fabrication"]["pages"] == 4 and r["fabrication"]["sections"] == 3 and r["fabrication"]["pages_en_image"] == 1
    epub = client.get(f"/api/livres/{livre_id}/telecharger/epub")
    assert epub.headers["content-type"] == "application/epub+zip"
    with zipfile.ZipFile(io.BytesIO(epub.content)) as z:
        noms = z.namelist()
        p1 = z.read(next(n for n in noms if n.endswith("p0001.xhtml"))).decode()
        assert "<em>gin</em>" in p1 and "Recette 1" in p1
        assert ">B<" not in p1 and ">2<" not in p1                      # lettre de marge et numéro de page retirés
        assert 'src="images/p0001-img-0.jpeg"' in p1                    # illustration replacée
        assert any(n.endswith("images/page-0003.jpg") for n in noms)   # page douteuse : en image
        assert any(n.endswith("images/p0001-img-0.jpeg") for n in noms)
        nav = z.read(next(n for n in noms if n.endswith("nav.xhtml"))).decode()
        assert "Recette 1" in nav                                       # table des matières par les titres
        # Page du livre papier : repère dans le texte et liste des pages pour la liseuse
        assert 'epub:type="pagebreak"' in p1 and 'class="page-originale">p. 1<' in p1
        assert 'epub:type="page-list"' in nav and '>4</a>' in nav
        # Archive valide : « mimetype » en tête et non compressé, chaque page XHTML bien formée
        assert noms[0] == "mimetype" and z.getinfo("mimetype").compress_type == zipfile.ZIP_STORED
        import xml.dom.minidom
        for n in noms:
            if n.endswith(".xhtml"):
                xml.dom.minidom.parseString(z.read(n))
    archive = client.get(f"/api/livres/{livre_id}/telecharger/archive")
    assert archive.content.startswith(b"%PDF-")

    v = client.post(f"/api/livres/{livre_id}/deposer").json()
    deposes = list((tmp_path / "bookdrop").iterdir())
    assert [p.name for p in deposes] == ["Auteur Inventé - Cocktails.epub"]   # l'EPUB seul, sans PDF en double
    assert v["depose_le"]
    # Jamais par-dessus un fichier existant
    r = client.post(f"/api/livres/{livre_id}/deposer")
    assert r.status_code == 409 and "rien n'a été remplacé" in r.json()["detail"]
    quoi = [j["quoi"] for j in client.get("/api/journal").json()]
    assert {"import", "lecture_mistral", "depot_grimmory"} <= set(quoi)


def test_lecture_seule_n_envoie_rien_et_ne_depose_rien(client, monkeypatch, tmp_path):
    livre_id = importer(client, pdf_livre([1, 2]))
    main.ETAT["travail"].tout_faire()
    client.post(f"/api/livres/{livre_id}/inventaire/confirmer")
    client.post(f"/api/livres/{livre_id}/fabriquer")                 # fabriquer reste possible : tout reste chez soi
    appels = []
    monkeypatch.setattr(mistral, "lire_page", lambda *a, **k: appels.append(a))
    main.ETAT["cfg"] = dataclasses.replace(main.ETAT["cfg"], lecture_seule=True)
    main.ETAT["travail"].cfg = main.ETAT["cfg"]
    assert client.post(f"/api/livres/{livre_id}/lecture").status_code == 409
    assert client.post(f"/api/livres/{livre_id}/deposer").status_code == 409
    # Même si la demande était déjà en base, la tâche de fond n'envoie rien.
    main.ETAT["base"].ecrire("UPDATE livres SET lecture_demandee = 1, etat = 'lecture' WHERE id = ?", livre_id)
    main.ETAT["travail"].tout_faire()
    assert appels == [] and list((tmp_path / "bookdrop").iterdir()) == []
    assert not [j for j in client.get("/api/journal").json() if j["quoi"] in ("lecture_mistral", "depot_grimmory")]


def test_cle_refusee_arrete_la_lecture(client, monkeypatch):
    livre_id = importer(client, pdf_livre([1, 2, 3]))
    main.ETAT["travail"].tout_faire()
    client.post(f"/api/livres/{livre_id}/inventaire/confirmer")
    appels = []

    def refuse(*a, **k):
        appels.append(1)
        raise mistral.ErreurMistral("clé Mistral refusée (401)")
    monkeypatch.setattr(mistral, "lire_page", refuse)
    client.post(f"/api/livres/{livre_id}/lecture")
    main.ETAT["travail"].tout_faire()
    v = client.get(f"/api/livres/{livre_id}").json()
    assert len(appels) == 1 and "401" in v["erreur"] and v["etat"] == "lecture"
    assert v["bilan"]["lecture"]["erreur"] == 1 and v["bilan"]["lecture"]["attente"] == 2


def test_supprimer_met_le_livre_dans_la_corbeille(client):
    """0.6.7 (audit, M38) : supprimer ne détruit rien tout de suite ; restaurer rend le livre tel quel ;
    la tâche de fond l'efface pour de bon après 30 jours."""
    from datetime import datetime, timedelta

    livre_id = importer(client, pdf_livre([1]))
    dossier = main.ETAT["base"].dossier(livre_id)
    assert dossier.exists()
    assert client.post(f"/api/livres/{livre_id}/supprimer").json() == {"ok": True, "jours": 30}
    assert dossier.exists() and (dossier / "source.pdf").exists()                  # rien d'effacé
    assert client.get(f"/api/livres/{livre_id}").status_code == 404                  # masqué
    assert all(l["id"] != livre_id for l in client.get("/api/livres").json())
    (dans,) = client.get("/api/corbeille").json()
    assert dans["id"] == livre_id and dans["titre"] == "Cocktails" and dans["efface_le"]
    assert client.post(f"/api/livres/{livre_id}/supprimer").status_code == 404       # déjà dans la corbeille
    # Restauration
    r = client.post(f"/api/livres/{livre_id}/restaurer")
    assert r.status_code == 200 and r.json()["id"] == livre_id
    assert client.get("/api/corbeille").json() == [] and client.get(f"/api/livres/{livre_id}").status_code == 200
    assert client.post(f"/api/livres/{livre_id}/restaurer").status_code == 404       # plus dans la corbeille
    # Effacement définitif par la tâche de fond, après 30 jours seulement
    client.post(f"/api/livres/{livre_id}/supprimer")
    travail = main.ETAT["travail"]
    maintenant = datetime.now().astimezone()
    assert travail.purger_corbeille(maintenant + timedelta(days=29)) == 0 and dossier.exists()
    assert travail.purger_corbeille(maintenant + timedelta(days=31)) == 1
    assert not dossier.exists() and client.get("/api/corbeille").json() == []
    assert main.ETAT["base"].un("SELECT id FROM livres WHERE id = ?", livre_id) is None
    quoi = [e["quoi"] for e in client.get("/api/journal").json()]
    assert {"suppression", "restauration_livre", "effacement"} <= set(quoi)


def test_livre_dans_la_corbeille_n_est_plus_travaille(client, monkeypatch):
    """Une lecture demandée s'arrête à la suppression : rien n'est envoyé à Mistral pour un livre de la corbeille."""
    appels = []
    monkeypatch.setattr(mistral, "lire_page", lambda *a, **k: appels.append(a))
    livre_id = importer(client, pdf_livre([1, 2]))
    main.ETAT["travail"].tout_faire()
    main.ETAT["base"].ecrire("UPDATE livres SET etat = 'lecture', lecture_demandee = 1, pdf_demande = 1 WHERE id = ?", livre_id)
    client.post(f"/api/livres/{livre_id}/supprimer")
    main.ETAT["base"].ecrire("UPDATE livres SET lecture_demandee = 1, pdf_demande = 1 WHERE id = ?", livre_id)   # au pire
    assert main.ETAT["travail"].une_tache() is False and appels == []


# ---------------------------------------------------------------- client Mistral

def test_client_mistral_lit_texte_et_images():
    pixel = base64.b64encode(b"\xff\xd8image").decode()
    recu = {}

    def serveur(requete: httpx.Request):
        recu["corps"] = json.loads(requete.content)
        recu["auth"] = requete.headers["authorization"]
        return httpx.Response(200, json={"usage_info": {"pages_processed": 1}, "pages": [
            {"markdown": "# Titre\n\nTexte de la page, assez long.", "images": [{"id": "img-0.jpeg", "image_base64": "data:image/jpeg;base64," + pixel}]}]})
    with httpx.Client(transport=httpx.MockTransport(serveur)) as c:
        lue = mistral.lire_page(b"jpeg", "cle", "https://exemple.invalid/v1/ocr", "mistral-ocr-latest", client=c)
    assert lue.markdown.startswith("# Titre") and lue.images == {"img-0.jpeg": b"\xff\xd8image"} and lue.douteuse == ""
    assert recu["auth"] == "Bearer cle" and recu["corps"]["document"]["image_url"].startswith("data:image/jpeg;base64,")


def test_client_mistral_signale_une_sortie_douteuse_et_les_refus():
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"pages": [{"markdown": '[{"box_2d": [1, 2]}]'}]}))) as c:
        assert mistral.lire_page(b"x", "cle", "https://e.invalid/v1/ocr", "m", client=c).douteuse
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(401, json={}))) as c:
        with pytest.raises(mistral.ErreurMistral, match="401"):
            mistral.lire_page(b"x", "cle", "https://e.invalid/v1/ocr", "m", client=c)
    with pytest.raises(mistral.ErreurMistral, match="aucune clé"):
        mistral.lire_page(b"x", "", "https://e.invalid/v1/ocr", "m")


def test_nom_de_fichier_sans_caracteres_interdits():
    assert fabrication.nom_fichier("A/B", 'Titre: "deux"?') == "AB - Titre deux"
    assert fabrication.nom_fichier("", "Seul") == "Seul"


# ---------------------------------------------------------------- numéros de page (livre à index de marge)

def page_a_index(numero, cote="g", derniere="saveur et profondeur."):
    """Une page comme celles du livre de cocktails : index de lettres A à Z dans la marge, le « Z » à côté de
    la dernière ligne du texte, petit numéro dans le coin en dessous, bords noirs du scan sur les côtés."""
    W, H = 1662, 2342
    im = Image.new("RGB", (W, H), (245, 243, 238))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 40, H), fill=(10, 10, 10))
    d.rectangle((W - 40, 0, W, H), fill=(10, 10, 10))
    polices = glob.glob("/usr/share/fonts/**/DejaVuSans.ttf", recursive=True)
    sans = ImageFont.truetype(polices[0], 20) if polices else ImageFont.load_default()
    corps, chiffres = _police(22), _police(24)
    for i, lettre in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
        d.text((60 if cote == "g" else W - 80, 150 + i * 81), lettre, font=sans, fill=(60, 60, 60))
    for y in range(150, 2160, 34):
        d.text((150, y), "45 ml de whiskey irlandais, 15 ml de Kirsch vieux, xérès oloroso.", font=corps, fill=(30, 30, 30))
    d.text((150, 2170), derniere, font=corps, fill=(30, 30, 30))
    if numero is not None:
        d.text((70 if cote == "g" else W - 110, 2265), str(numero), font=chiffres, fill=(20, 20, 20))
    return im


@pytest.mark.skipif(not TESSERACT, reason="Tesseract absent")
def test_numero_dans_le_coin_et_lettre_d_index_ignoree():
    assert inventaire.lire_numero(page_a_index(72, "g")) == 72
    assert inventaire.lire_numero(page_a_index(118, "d")) == 118
    # Sans numéro : le « Z » de l'index ne doit pas devenir « 2 », ni le « 5 ml » de la dernière ligne « 5 »
    assert inventaire.lire_numero(page_a_index(None, "g")) is None
    assert inventaire.lire_numero(page_a_index(None, "d", "5 ml de sirop de groseille")) is None


def test_relire_les_numeros(client, monkeypatch):
    livre_id = importer(client, pdf_livre([1, 2, 3]))
    main.ETAT["travail"].tout_faire()
    client.post(f"/api/livres/{livre_id}/pages/2", json={"ecartee": True})
    monkeypatch.setattr(inventaire, "lire_numero", lambda img: 40)
    v = client.post(f"/api/livres/{livre_id}/numeros/relire").json()
    assert v["etat"] == "decoupe" and v["relire"] == 1
    main.ETAT["travail"].tout_faire()
    v = client.get(f"/api/livres/{livre_id}").json()
    assert v["etat"] == "inventaire" and v["relire"] == 0
    assert [p["numero_lu"] for p in v["liste_pages"]] == [40, 40, 40]
    assert [p["ecartee"] for p in v["liste_pages"]] == [0, 1, 0]       # la mise à l'écart est gardée
    # Après la lecture par Mistral, plus de relecture des numéros
    client.post(f"/api/livres/{livre_id}/inventaire/confirmer")
    monkeypatch.setattr(mistral, "lire_page", fausse_lecture())
    client.post(f"/api/livres/{livre_id}/lecture")
    main.ETAT["travail"].tout_faire()
    assert client.post(f"/api/livres/{livre_id}/numeros/relire").status_code == 409



# ---------------------------------------------------------------- 0.3 : numéros par Mistral, EPUB d'essai

def test_numero_page_dans_le_texte_de_mistral():
    assert mistral.numero_page("# Titre\n\nB\n\n45 ml de gin\n\nZ\n\n72") == 72
    assert mistral.numero_page("— 118 —\n\nTexte") == 118
    assert mistral.numero_page("Page 9\n\nTexte") == 9
    assert mistral.numero_page("45 ml de gin\n\n2,5 ml de sirop") is None
    assert mistral.numero_page("") is None


def test_numeros_de_mistral_et_pages_manquantes(client, monkeypatch):
    """Mistral lit les pages sans attendre l'inventaire ; ses numéros remplacent ceux de Tesseract,
    sauf un numéro corrigé à la main ; l'inventaire en déduit les pages manquantes."""
    livre_id = importer(client, pdf_livre([None, None, None, None]))
    monkeypatch.setattr(inventaire, "lire_numero", lambda img: 2)   # Tesseract se trompe partout
    main.ETAT["travail"].tout_faire()
    client.post(f"/api/livres/{livre_id}/pages/4", json={"numero": 76})   # corrigé à la main
    numeros = iter([70, 71, 74, 75])

    def lire_page(image, cle, url, modele, client=None):
        n = next(numeros)
        return mistral.PageLue(f"# Recette\n\nTexte de la page {n}, assez long.\n\n{n}", {}, 1, "", n)
    monkeypatch.setattr(mistral, "lire_page", lire_page)
    assert client.post(f"/api/livres/{livre_id}/lecture").status_code == 200
    main.ETAT["travail"].tout_faire()
    v = client.get(f"/api/livres/{livre_id}").json()
    assert [p["numero"] for p in v["liste_pages"]] == [70, 71, 74, 76]
    assert v["liste_pages"][3]["numero_mistral"] == 75 and v["liste_pages"][3]["numero_manuel"] == 1
    assert v["bilan"]["inventaire"]["manquantes"] == [72, 73, 75]


def test_epub_d_essai_avec_les_seules_pages_lues(client, monkeypatch):
    livre_id = importer(client, pdf_livre([1, 2, 3, 4]))
    main.ETAT["travail"].tout_faire()
    assert client.post(f"/api/livres/{livre_id}/fabriquer?partiel=true").status_code == 409   # rien de lu
    lecture = fausse_lecture()
    appels = {"n": 0}

    def deux_pages(*a, **k):        # la lecture s'arrête après deux pages (crédit épuisé)
        appels["n"] += 1
        if appels["n"] > 2:
            raise mistral.ErreurMistral("trop de demandes ou crédit épuisé chez Mistral (429)")
        return lecture(*a, **k)
    monkeypatch.setattr(mistral, "lire_page", deux_pages)
    client.post(f"/api/livres/{livre_id}/lecture")
    main.ETAT["travail"].tout_faire()
    r = client.post(f"/api/livres/{livre_id}/fabriquer?partiel=true").json()
    assert r["fabrication"]["sections"] == 2 and r["fabrication"]["pages_en_image"] == 0
    assert r["essai"].endswith("(essai).epub") and not r["epub"]            # l'essai n'est pas le livre
    epub = client.get(f"/api/livres/{livre_id}/telecharger/essai")
    assert epub.headers["content-type"] == "application/epub+zip"
    with zipfile.ZipFile(io.BytesIO(epub.content)) as z:
        noms = z.namelist()
        assert any(n.endswith("p0001.xhtml") for n in noms) and not any(n.endswith("p0003.xhtml") for n in noms)



# ---------------------------------------------------------------- EPUB lisible par Comptoir

def test_epub_pour_comptoir_recette_entiere_ingredients_en_liste(tmp_path):
    """Une recette qui passe d'une page à l'autre reste dans un seul fichier ; les ingrédients forment une
    liste ; chaque page garde son repère du livre papier ; les identifiants ne se répètent pas."""
    (tmp_path / "lu").mkdir()
    (tmp_path / "pages").mkdir()
    (tmp_path / "lu" / "0001.md").write_text(
        "# TWO GUNS MILLER\n\nVERRE : coupe\n\n45 ml de tequila (100 % agave reposado)\n\n45 ml de vermouth Martini Rosso\n\n"
        "2,5 ml de sirop à la cannelle Monin\n\n1 trait de Xocolatl Mole bitters\n\nB\n\nORIGINE : adapté d'une recette\n\n72")
    (tmp_path / "lu" / "0002.md").write_text("découverte en 2015 au Pouring Ribbons.\n\nC\n\n73")
    (tmp_path / "lu" / "0003.md").write_text("# 18TH CENTURY COCKTAIL\n\n22,5 ml d'eau-de-vie d'abricot\n\nCompléter avec du champagne brut\n\n74")
    pages = [{"rang": i, "numero": 71 + i, "lecture": "faite"} for i in (1, 2, 3)]
    sortie = tmp_path / "livre.epub"
    bilan = fabrication.fabriquer_epub(tmp_path, {"id": 1, "titre": "Essai", "auteur": "", "langue": "fr"}, pages, sortie)
    assert bilan["sections"] == 2 and bilan["pages"] == 3
    with zipfile.ZipFile(sortie) as z:
        p1 = z.read(next(n for n in z.namelist() if n.endswith("p0001.xhtml"))).decode()
        p3 = z.read(next(n for n in z.namelist() if n.endswith("p0003.xhtml"))).decode()
    assert "Pouring Ribbons" in p1 and "ORIGINE" in p1                   # la recette entière dans un fichier
    assert 'title="72"' in p1 and 'title="73"' in p1                     # deux repères de page dans le fil
    assert p1.count("<li>") == 4 and "<li>1 trait de Xocolatl Mole bitters</li>" in p1
    assert "<li>Compléter avec du champagne brut</li>" in p3
    assert "VERRE : coupe" in p1 and "<li>VERRE" not in p1
    ids = re.findall(r'id="([^"]+)"', p1)
    assert len(ids) == len(set(ids))


# ---------------------------------------------------------------- 0.6.6 : plafond de dépense par livre

def test_plafond_de_depense_par_livre(client, monkeypatch):
    """Décision du 18/11/2026 : 2 € de lecture Mistral par livre ; au-delà, arrêt et question."""
    livre_id = importer(client, pdf_livre([1, 2, 3, 4]))
    main.ETAT["travail"].tout_faire()
    monkeypatch.setattr(mistral, "lire_page", fausse_lecture())
    # À 1 $ la page (≈ 0,90 €), 4 pages font environ 3,60 € : refus avec le montant
    assert client.put("/api/reglages", json={"prix_page": 1.0}).status_code == 200
    v = client.get(f"/api/livres/{livre_id}").json()
    assert v["bilan"]["estimation"]["depasse"] is True and v["bilan"]["estimation"]["plafond"] == 2.0
    r = client.post(f"/api/livres/{livre_id}/lecture")
    assert r.status_code == 402 and "Plafond de 2,00 €" in r.json()["detail"]
    # Le travail de fond s'arrête aussi de lui-même s'il est lancé sans confirmation
    main.ETAT["base"].ecrire("UPDATE livres SET etat = 'lecture', lecture_demandee = 1 WHERE id = ?", livre_id)
    main.ETAT["travail"].tout_faire()
    v = client.get(f"/api/livres/{livre_id}").json()
    assert v["bilan"]["facturees"] == 2 and "Plafond" in v["erreur"]          # 2 pages lues (1,80 €), la 3e dépasserait
    # Confirmé : le plafond est levé pour ce livre, la lecture va au bout
    assert client.post(f"/api/livres/{livre_id}/lecture", json={"depasser": True}).status_code == 200
    main.ETAT["travail"].tout_faire()
    v = client.get(f"/api/livres/{livre_id}").json()
    assert v["etat"] == "pret" and v["bilan"]["facturees"] == 4 and v["bilan"]["estimation"]["leve"] is True
    # Plafond à 0 : pas de plafond
    autre = importer(client, pdf_livre([1, 2]))
    main.ETAT["travail"].tout_faire()
    assert client.put("/api/reglages", json={"plafond_livre": 0.0}).status_code == 200
    assert client.post(f"/api/livres/{autre}/lecture").status_code == 200
