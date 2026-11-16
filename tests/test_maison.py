"""Variables communes de la maison (module app/maison.py, contrat 2).

0.6 : l'ancien nom du mot de passe (SCRIPTORIUM_PASSWORD) n'est plus lu. Scriptorium ne reçoit aucune porte d'une
autre appli maison ; seule /externe/sauvegarde s'ouvre au jeton commun (voir tests/test_reglages.py). Restent la
lecture seule (commune, forçable par SCRIPTORIUM_LECTURE_SEULE) ; la porte du PC de calcul garde son propre jeton.
"""
import dataclasses

import pytest
from fastapi.testclient import TestClient

from app import maison, main
from app.config import Config, charger

VARIABLES = ("MAISON_PASSWORD", "SCRIPTORIUM_PASSWORD", "MAISON_LECTURE_SEULE", "SCRIPTORIUM_LECTURE_SEULE",
             "MAISON_JETON", "MAISON_JETON_ANCIEN", "SCRIPTORIUM_JETON_CALCUL")
JETON_PC = "jeton-du-pc-de-calcul-0123456789"
JETON_MAISON = "jeton-commun-de-la-maison-9876543210"


@pytest.fixture(autouse=True)
def environnement_vide(monkeypatch):
    for nom in VARIABLES:
        monkeypatch.delenv(nom, raising=False)


def test_copie_du_module_non_retouchee():
    assert maison.CONTRAT == 2 and maison.CONTRAT_SAUVEGARDE == 1
    assert maison.empreinte_calculee() == maison.empreinte_ecrite()


def test_mot_de_passe_commun_seul(monkeypatch):
    monkeypatch.setenv("SCRIPTORIUM_PASSWORD", "ancien-mot-de-passe-long")
    with pytest.raises(SystemExit, match="MAISON_PASSWORD est absent ou trop court"):
        charger()                                                    # 0.6 : l'ancien nom seul ne suffit plus
    monkeypatch.setenv("MAISON_PASSWORD", "mot-de-passe-commun-long")
    assert charger().password == "mot-de-passe-commun-long"


def test_mot_de_passe_absent_ou_court_refuse(monkeypatch):
    with pytest.raises(SystemExit, match="MAISON_PASSWORD"):
        charger()
    monkeypatch.setenv("MAISON_PASSWORD", "court")
    with pytest.raises(SystemExit, match="MAISON_PASSWORD est absent ou trop court"):
        charger()


def test_lecture_seule_maison_et_forcage(monkeypatch):
    monkeypatch.setenv("MAISON_PASSWORD", "mot-de-passe-commun-long")
    c = charger()
    assert (c.lecture_seule, c.origine_lecture_seule) == (False, "")
    monkeypatch.setenv("MAISON_LECTURE_SEULE", "oui")
    c = charger()
    assert (c.lecture_seule, c.origine_lecture_seule) == (True, "maison")
    monkeypatch.setenv("SCRIPTORIUM_LECTURE_SEULE", "non")            # l'appli seule reprend l'écriture
    c = charger()
    assert (c.lecture_seule, c.origine_lecture_seule) == (False, "")
    monkeypatch.delenv("MAISON_LECTURE_SEULE")
    for valeur in ("oui", "1", "true", "yes"):                         # valeurs déjà acceptées avant la 0.5
        monkeypatch.setenv("SCRIPTORIUM_LECTURE_SEULE", valeur)
        c = charger()
        assert (c.lecture_seule, c.origine_lecture_seule) == (True, "appli"), valeur


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MAISON_PASSWORD", "mot-de-passe-commun-long")
    monkeypatch.setenv("SCRIPTORIUM_DATA", str(tmp_path))
    monkeypatch.setenv("SCRIPTORIUM_JETON_CALCUL", JETON_PC)
    monkeypatch.setenv("MAISON_JETON", JETON_MAISON)
    main.ETAT.clear()
    main.ETAT["cfg"] = dataclasses.replace(charger(), attente_connexion=False, travail_auto=False)
    with TestClient(main.app) as c:
        yield c
    main.ETAT.clear()


def test_connexion_par_le_mot_de_passe_commun(client):
    assert client.post("/api/connexion", json={"mot_de_passe": "mot-de-passe-commun-long"}).status_code == 200
    assert client.get("/api/livres").status_code == 200


def test_origine_de_la_lecture_seule_annoncee(client):
    s = client.get("/api/session").json()
    assert (s["lecture_seule"], s["origine_lecture_seule"]) == (False, "")
    main.ETAT["cfg"] = dataclasses.replace(main.ETAT["cfg"], lecture_seule=True, origine_lecture_seule="maison")
    s = client.get("/api/session").json()
    assert (s["lecture_seule"], s["origine_lecture_seule"]) == (True, "maison")
    main.ETAT["cfg"] = dataclasses.replace(main.ETAT["cfg"], origine_lecture_seule="appli")
    assert client.get("/api/session").json()["origine_lecture_seule"] == "appli"
    assert client.post("/api/connexion", json={"mot_de_passe": "mot-de-passe-commun-long"}).status_code == 200
    assert client.get("/api/services").json()["origine_lecture_seule"] == "appli"


def test_porte_du_pc_non_ouverte_par_le_jeton_commun(client):
    """Le PC de calcul garde son propre jeton (SCRIPTORIUM_JETON_CALCUL) : MAISON_JETON n'ouvre pas sa porte."""
    assert client.get("/calcul/travail", headers={"Authorization": f"Bearer {JETON_MAISON}"}).status_code == 401
    assert client.get("/calcul/travail", headers={"Authorization": f"Bearer {JETON_PC}"}).status_code == 204
