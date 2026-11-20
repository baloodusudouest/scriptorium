"""Tests de Scriptorium : santé, garde des routes, connexion, déconnexion, services."""
import dataclasses

import pytest
from fastapi.testclient import TestClient

from app import main
from app.config import Config

MOT_DE_PASSE = "mot-de-passe-de-test"


@pytest.fixture()
def client(tmp_path):
    main.ETAT.clear()
    main.SERVICES._dernier.clear()     # 0.8.0 : derniers essais des fiches « Connexion » (registre du module)
    main.ETAT["cfg"] = Config(password=MOT_DE_PASSE, data=tmp_path, static=tmp_path / "static",
                              attente_connexion=False, travail_auto=False, bookdrop=tmp_path / "bookdrop")
    with TestClient(main.app) as c:
        yield c
    main.ETAT.clear()


def connecter(client):
    r = client.post("/api/connexion", json={"mot_de_passe": MOT_DE_PASSE})
    assert r.status_code == 200


def test_sante_publique(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["ok"] is True


def test_api_fermee_sans_connexion(client):
    for chemin in ("/api/livres", "/api/services", "/api/journal", "/api/livres/1/pages/1.jpg"):
        assert client.get(chemin).status_code == 401, chemin
    assert client.post("/api/livres", json={"titre": "x"}).status_code == 401
    assert client.get("/api/session").json()["connecte"] is False


def test_mauvais_mot_de_passe_refuse(client):
    r = client.post("/api/connexion", json={"mot_de_passe": "faux"})
    assert r.status_code == 401
    assert client.get("/api/livres").status_code == 401


def test_connexion_puis_services(client):
    connecter(client)
    s = client.get("/api/services").json()
    assert s["mistral"]["cle"] is False
    assert s["grimmory"] == {"configure": True, "inscriptible": False}   # dossier absent
    assert s["disque"]["inscriptible"] is True
    assert client.get("/api/livres").headers["cache-control"] == "no-store"


def test_deconnexion_invalide_les_anciens_cookies(client, tmp_path):
    connecter(client)
    ancien = client.cookies.get("scriptorium_session")
    assert client.post("/api/deconnexion").status_code == 200
    client.cookies.set("scriptorium_session", ancien)
    assert client.get("/api/livres").status_code == 401
    # La génération est écrite sur disque : elle survit à un redémarrage
    assert (tmp_path / "session_generation").read_text() == "1"


def test_cookie_falsifie_refuse(client):
    client.cookies.set("scriptorium_session", "0.9999999999.deadbeef")
    assert client.get("/api/livres").status_code == 401


def test_interface_non_compilee_signalee(client):
    r = client.get("/")
    assert r.status_code == 404 and "non compilée" in r.json()["detail"]


def test_mistral_verifier_sans_cle(client):
    connecter(client)
    r = client.post("/api/services/mistral/verifier").json()
    assert r["ok"] is False and "SCRIPTORIUM_MISTRAL_CLE" in r["message"]


def test_lecture_seule_annoncee(client):
    connecter(client)
    assert client.get("/api/session").json()["lecture_seule"] is False
    main.ETAT["cfg"] = dataclasses.replace(main.ETAT["cfg"], lecture_seule=True)
    assert client.get("/api/session").json()["lecture_seule"] is True
