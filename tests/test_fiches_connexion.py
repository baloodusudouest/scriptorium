"""Fiches « Connexion » communes (contrat 3, socle 0.11.0) : forme de /api/maison/services, accès par session ou
ANNEAU_CLE seulement (jamais MAISON_JETON), « Vérifier » d'un service pas relié n'essaie rien, copies non retouchées
du module commun et de l'interface commune."""
import dataclasses
from pathlib import Path

from app import maison
from app.config import APPLI
from tests.test_api import client, connecter  # noqa: F401  (fixture)

RACINE = Path(__file__).resolve().parent.parent
CLE = "cle-anneau-de-test-1234567890"
IDS = ["mistral", "pc-calcul", "grimmory"]
CHAMPS = {"id", "nom", "genre", "cible", "etat", "lit", "ecrit", "reglage", "detail", "verifie_le", "guide",
          "derniere_ecriture", "gestes"}


def test_forme_du_contrat_3(client):
    connecter(client)
    r = client.get("/api/maison/services")
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    corps = r.json()
    assert corps["contrat"] == 3 and corps["appli"] == APPLI and corps["simule"] is False
    assert [s["id"] for s in corps["services"]] == IDS
    for s in corps["services"]:
        assert set(s) == CHAMPS and s["lit"] and s["ecrit"] and s["etat"] in maison.ETATS_SERVICE
        assert len(s["gestes"]) <= 1
        if s["etat"] == "pas_relie":
            assert s["reglage"]


def test_acces_session_ou_cle_anneau(client, monkeypatch):
    assert client.get("/api/maison/services").status_code == 401
    monkeypatch.setenv("MAISON_JETON", "jeton-commun-de-test-12345")
    entete = {"Authorization": "Bearer jeton-commun-de-test-12345"}
    assert client.get("/api/maison/services", headers=entete).status_code == 401
    monkeypatch.setenv("ANNEAU_CLE", CLE)
    assert client.get("/api/maison/services", headers={"Authorization": f"Bearer {CLE}"}).status_code == 200
    assert client.get("/api/maison/services", headers={"Authorization": "Bearer mauvaise"}).status_code == 401


def test_verifier_inconnu_et_pas_relie(client):
    connecter(client)
    assert client.post("/api/maison/services/inconnu/verifier").status_code == 404
    for s in client.get("/api/maison/services").json()["services"]:
        if s["etat"] == "pas_relie":
            apres = client.post(f"/api/maison/services/{s['id']}/verifier").json()
            assert apres["etat"] == "pas_relie" and apres["verifie_le"] is None


def test_copies_communes_non_retouchees():
    assert maison.CONTRAT == 3 and maison.VERSION_SOCLE == "0.11.0"
    assert maison.empreinte_calculee() == maison.empreinte_ecrite()
    for nom in maison.FICHIERS_INTERFACE:
        ecrite, calculee = maison.empreinte_interface(RACINE / "frontend" / "src" / "lib" / "services" / nom)
        assert ecrite and ecrite == calculee, nom


# ---------------------------------------------------------------- propres à Scriptorium

def test_pas_relies_sans_cle_ni_jeton(client):
    """Sans clé Mistral ni jeton du PC : « Pas relié » avec le nom de la variable ; Grimmory, réglé, n'est pas essayé."""
    connecter(client)
    fiches = {s["id"]: s for s in client.get("/api/maison/services").json()["services"]}
    assert fiches["mistral"]["etat"] == "pas_relie" and fiches["mistral"]["reglage"] == "SCRIPTORIUM_MISTRAL_CLE"
    assert fiches["pc-calcul"]["etat"] == "pas_relie" and fiches["pc-calcul"]["reglage"] == "SCRIPTORIUM_JETON_CALCUL"
    assert fiches["grimmory"]["etat"] == "relie" and fiches["grimmory"]["gestes"] == []


def test_mistral_ne_lit_que_la_liste_des_modeles(client, monkeypatch):
    """Vérifier ne coûte rien : une seule lecture, GET …/v1/models ; jamais l'OCR (payant)."""
    import httpx
    from app import main, mistral
    appels = []

    def faux_get(url, **k):
        appels.append(("GET", url))
        return httpx.Response(200, json={"data": []}, request=httpx.Request("GET", url))

    monkeypatch.setattr(mistral.httpx, "get", faux_get)
    monkeypatch.setattr(mistral.httpx, "post", lambda *a, **k: appels.append(("POST", a)) or 1 / 0)
    monkeypatch.setattr(mistral, "lire_page", lambda *a, **k: appels.append(("OCR", a)) or 1 / 0)
    main.ETAT["cfg"] = dataclasses.replace(main.ETAT["cfg"], mistral_cle="cle-de-test")
    connecter(client)
    f = client.post("/api/maison/services/mistral/verifier").json()
    assert f["etat"] == "repond" and f["detail"] == "Clé acceptée par Mistral."
    assert appels == [("GET", "https://api.mistral.ai/v1/models")]
    assert any(r["nom"] == "Modèle" for r in f["guide"]["reglages"])


def test_pc_jamais_appele_et_guide_complet(client, monkeypatch):
    """Le PC n'est jamais appelé (aucune requête réseau) : Vérifier lit la date de son dernier passage."""
    import urllib.request

    import httpx
    from app import main
    monkeypatch.setattr(httpx, "get", lambda *a, **k: 1 / 0)
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: 1 / 0)
    main.ETAT["cfg"] = dataclasses.replace(main.ETAT["cfg"], jeton_calcul="jeton-du-pc-de-test")
    connecter(client)
    f = client.post("/api/maison/services/pc-calcul/verifier").json()
    assert f["etat"] == "ne_repond_pas" and "jamais passé" in f["detail"]
    g = f["guide"]
    assert {"reglages", "allumer", "pannes", "une_fois", "terminal", "note"} <= set(g)
    assert g["allumer"] and g["pannes"] and g["une_fois"] and "PowerShell" in g["terminal"]
    assert any("docker compose -f calcul.yml up -d" in c for p in g["pannes"] for c in p["commandes"])
    assert "jeton-du-pc-de-test" not in str(g)
    # le PC passe (porte /calcul) : la fiche répond, sans délai de 30 s pour ce test
    assert client.get("/calcul/travail", headers={"Authorization": "Bearer jeton-du-pc-de-test",
                                                  "X-Moteur": "marker 2.2.0 (fast)"}).status_code == 204
    main.SERVICES._dernier.pop("pc-calcul", None)
    f = client.post("/api/maison/services/pc-calcul/verifier").json()
    assert f["etat"] == "repond" and "marker 2.2.0" in f["detail"] and "0 page en attente" in f["detail"]


def test_grimmory_verifie_sans_ecrire(client, tmp_path):
    from app import main
    main.SERVICES._dernier.pop("grimmory", None)
    connecter(client)
    assert client.post("/api/maison/services/grimmory/verifier").json()["etat"] == "ne_repond_pas"   # dossier absent
    (tmp_path / "bookdrop").mkdir()
    main.SERVICES._dernier.pop("grimmory", None)
    assert client.post("/api/maison/services/grimmory/verifier").json()["etat"] == "repond"
    assert list((tmp_path / "bookdrop").iterdir()) == []


def test_dossier_de_donnees_dans_reglages(client):
    connecter(client)
    d = client.get("/api/dossier").json()
    assert d["total"] > 0 and d["inscriptible"] is True
    assert "disque" not in {s["id"] for s in client.get("/api/maison/services").json()["services"]}
