"""0.6 : réglages d'usage dans l'appli, sauvegarde par l'Anneau (/externe/sauvegarde) et restauration.

Sans réseau : l'Anneau est simulé par l'argument « lire » de maison.lire_sauvegarde (main.ETAT["lire_anneau"]).
"""
import dataclasses
import io
import json
import urllib.error

import pytest
from fastapi.testclient import TestClient

from app import main
from app.config import EXCLUS, REGLAGES, charger

VARIABLES = ("MAISON_PASSWORD", "SCRIPTORIUM_PASSWORD", "MAISON_LECTURE_SEULE", "SCRIPTORIUM_LECTURE_SEULE",
             "MAISON_JETON", "MAISON_JETON_ANCIEN", "SCRIPTORIUM_JETON_CALCUL", "SCRIPTORIUM_MISTRAL_CLE",
             "SCRIPTORIUM_RECHERCHE_WEB", "SCRIPTORIUM_PRIX_PAGE", "SCRIPTORIUM_DPI")
MDP = "mot-de-passe-commun-long"
JETON_MAISON = "jeton-commun-de-la-maison-9876543210"
JETON_PC = "jeton-du-pc-de-calcul-0123456789"
CLE_MISTRAL = "cle-mistral-de-test-a-ne-jamais-sortir"


@pytest.fixture(autouse=True)
def environnement(monkeypatch, tmp_path):
    for nom in VARIABLES:
        monkeypatch.delenv(nom, raising=False)
    monkeypatch.setenv("MAISON_PASSWORD", MDP)
    monkeypatch.setenv("SCRIPTORIUM_DATA", str(tmp_path))
    monkeypatch.setenv("SCRIPTORIUM_JETON_CALCUL", JETON_PC)
    monkeypatch.setenv("SCRIPTORIUM_MISTRAL_CLE", CLE_MISTRAL)


def demarrer():
    """Un démarrage de Scriptorium (cycle de vie complet) ; à utiliser dans un « with »."""
    main.ETAT.clear()
    main.ETAT["cfg"] = dataclasses.replace(charger(), attente_connexion=False, travail_auto=False)
    return TestClient(main.app)


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("MAISON_JETON", JETON_MAISON)
    with demarrer() as c:
        yield c
    main.ETAT.clear()


def connecter(c):
    assert c.post("/api/connexion", json={"mot_de_passe": MDP}).status_code == 200


# ---------------------------------------------------------------- reprise et écran Réglages

def test_reprise_au_premier_demarrage_puis_variable_ignoree(monkeypatch, tmp_path):
    monkeypatch.setenv("SCRIPTORIUM_RECHERCHE_WEB", "non")
    monkeypatch.setenv("SCRIPTORIUM_PRIX_PAGE", "0,003")
    monkeypatch.setenv("SCRIPTORIUM_DPI", "150")
    with demarrer() as c:
        connecter(c)
        assert c.get("/api/reglages").json()["reglages"] == {"recherche_web": False, "prix_page": 0.003, "dpi": 150, "plafond_livre": 2.0}
        journal = [j for j in c.get("/api/journal").json() if j["quoi"] == "reglage_repris"]
        assert len(journal) == 3 and any("SCRIPTORIUM_RECHERCHE_WEB" in j["detail"] for j in journal)
    assert json.loads((tmp_path / "reglages.json").read_text())["dpi"] == 150
    # Second démarrage : la variable a changé dans la stack, mais elle n'est plus lue
    monkeypatch.setenv("SCRIPTORIUM_RECHERCHE_WEB", "oui")
    monkeypatch.setenv("SCRIPTORIUM_DPI", "300")
    with demarrer() as c:
        connecter(c)
        assert c.get("/api/reglages").json()["reglages"]["recherche_web"] is False
        assert c.get("/api/reglages").json()["reglages"]["dpi"] == 150
        assert len([j for j in c.get("/api/journal").json() if j["quoi"] == "reglage_repris"]) == 3
    main.ETAT.clear()


def test_defauts_sans_variable(client):
    connecter(client)
    assert client.get("/api/reglages").json()["reglages"] == REGLAGES


def test_reglages_demandent_la_session(client):
    assert client.get("/api/reglages").status_code == 401
    assert client.put("/api/reglages", json={"dpi": 150}).status_code == 401
    assert client.get("/api/restaurer").status_code == 401


def test_changer_les_reglages(client):
    connecter(client)
    r = client.put("/api/reglages", json={"recherche_web": False, "prix_page": 0.004, "dpi": 300})
    assert r.status_code == 200
    assert r.json()["reglages"] == {"recherche_web": False, "prix_page": 0.004, "dpi": 300, "plafond_livre": 2.0}
    assert main.ETAT["travail"]._dpi() == 300                         # la découpe suit le réglage
    assert client.get("/api/services").json()["mistral"]["prix_page"] == 0.004
    assert any(j["quoi"] == "reglages" and "dpi : 200 → 300" in j["detail"] for j in client.get("/api/journal").json())


@pytest.mark.parametrize("corps", [
    {"recherche_web": "non"}, {"recherche_web": 1}, {"dpi": "beaucoup"}, {"dpi": 150.5}, {"dpi": True},
    {"dpi": 20}, {"prix_page": "0.002"}, {"prix_page": -1}, {"inconnu": 1}, {"plafond_livre": -1}, {"plafond_livre": 500},
])
def test_mauvais_type_refuse(client, corps):
    connecter(client)
    r = client.put("/api/reglages", json=corps)
    assert r.status_code == 400 and r.json()["detail"]
    assert client.get("/api/reglages").json()["reglages"] == REGLAGES   # rien n'a changé


def test_reglages_permis_en_lecture_seule(client):
    connecter(client)
    main.ETAT["cfg"] = dataclasses.replace(main.ETAT["cfg"], lecture_seule=True, origine_lecture_seule="maison")
    assert client.put("/api/reglages", json={"dpi": 250}).status_code == 200


# ---------------------------------------------------------------- porte de sauvegarde

def test_sauvegarde_ouverte_par_le_jeton_commun(client):
    r = client.get("/externe/sauvegarde", headers={"Authorization": f"Bearer {JETON_MAISON}"})
    assert r.status_code == 200
    s = r.json()
    assert s["contrat"] == 1 and s["appli"] == "scriptorium" and s["reglages"] == REGLAGES
    texte = r.text
    for secret in (MDP, JETON_MAISON, JETON_PC, CLE_MISTRAL, "MAISON_", "SCRIPTORIUM_", "/data", "/bookdrop"):
        assert secret not in texte
    assert not any(k in s["reglages"] for k in EXCLUS)
    # X-Maison-Jeton est accepté aussi ; aucune session n'est demandée
    assert client.get("/externe/sauvegarde", headers={"X-Maison-Jeton": JETON_MAISON}).status_code == 200


def test_sauvegarde_fermee_sans_bon_jeton(client):
    assert client.get("/externe/sauvegarde").status_code == 401
    assert client.get("/externe/sauvegarde", headers={"Authorization": "Bearer mauvais"}).status_code == 401
    # le jeton du PC de calcul n'ouvre pas la porte de sauvegarde
    assert client.get("/externe/sauvegarde", headers={"Authorization": f"Bearer {JETON_PC}"}).status_code == 401
    # le cookie de session ne l'ouvre pas non plus
    connecter(client)
    assert client.get("/externe/sauvegarde").status_code == 401


def test_sauvegarde_fermee_si_jeton_commun_vide(monkeypatch):
    monkeypatch.delenv("MAISON_JETON", raising=False)
    with demarrer() as c:
        assert c.get("/externe/sauvegarde", headers={"Authorization": "Bearer "}).status_code == 404
        assert c.get("/externe/sauvegarde", headers={"Authorization": f"Bearer {JETON_PC}"}).status_code == 404
    main.ETAT.clear()


def test_porte_du_pc_fermee_au_jeton_commun(client):
    assert client.get("/calcul/travail", headers={"Authorization": f"Bearer {JETON_MAISON}"}).status_code == 401


def test_sante_inchangee(client):
    r = client.get("/health").json()
    assert r["ok"] is True and r["version"] == main.__version__
    assert set(r) == {"ok", "version", "version_socle", "taches", "copie_base"}       # 0.7.0 : santé des tâches


# ---------------------------------------------------------------- restauration

def faux_anneau(sauvegardes):
    """Faux Anneau : {date: réglages} ; garde les demandes reçues (adresse, jeton)."""
    demandes = []

    def lire(adresse, jeton):
        demandes.append((adresse, jeton))
        if "?le=" not in adresse:
            return {"dates": sorted(sauvegardes, reverse=True)}
        le = adresse.rsplit("?le=", 1)[1]
        if le not in sauvegardes:
            raise urllib.error.HTTPError(adresse, 404, "Not Found", {}, io.BytesIO(b""))
        return {"le": le, "version": "0.6.0", "reglages": sauvegardes[le]}
    lire.demandes = demandes
    return lire


def test_restaurer_dates_differences_application(client):
    connecter(client)
    anneau = faux_anneau({"2026-11-14": {"recherche_web": False, "prix_page": 0.002, "dpi": 300, "ancien": 1,
                                         "mistral_cle": "fuite"},
                          "2026-11-15": REGLAGES})
    main.ETAT["lire_anneau"] = anneau
    assert client.get("/api/restaurer").json() == {"dates": ["2026-11-15", "2026-11-14"]}
    assert anneau.demandes[0] == ("http://anneau:8094/externe/sauvegardes/scriptorium", JETON_MAISON)
    r = client.get("/api/restaurer", params={"le": "2026-11-14"}).json()
    assert r["le"] == "2026-11-14" and r["version"] == "0.6.0"
    assert r["differences"] == [{"cle": "dpi", "actuel": 200, "sauve": 300},
                                {"cle": "recherche_web", "actuel": True, "sauve": False}]
    r = client.post("/api/restaurer", json={"le": "2026-11-14"})
    assert r.status_code == 200
    assert r.json()["reglages"] == {"recherche_web": False, "prix_page": 0.002, "dpi": 300, "plafond_livre": 2.0}
    assert r.json()["appliques"] == ["dpi", "recherche_web"]
    assert any(j["quoi"] == "restauration" and "2026-11-14" in j["detail"] for j in client.get("/api/journal").json())
    # Plus rien à restaurer ce jour-là
    assert client.get("/api/restaurer", params={"le": "2026-11-14"}).json()["differences"] == []


def test_restaurer_permis_en_lecture_seule(client):
    connecter(client)
    main.ETAT["lire_anneau"] = faux_anneau({"2026-11-14": {"dpi": 300}})
    main.ETAT["cfg"] = dataclasses.replace(main.ETAT["cfg"], lecture_seule=True, origine_lecture_seule="appli")
    assert client.post("/api/restaurer", json={"le": "2026-11-14"}).json()["reglages"]["dpi"] == 300


def test_restaurer_ignore_une_valeur_invalide(client):
    connecter(client)
    main.ETAT["lire_anneau"] = faux_anneau({"2026-11-14": {"dpi": 5000, "prix_page": 0.01}})
    r = client.post("/api/restaurer", json={"le": "2026-11-14"}).json()
    assert r["appliques"] == ["prix_page"] and r["reglages"]["dpi"] == 200


def test_restaurer_sans_sauvegarde_ou_date_inconnue(client):
    connecter(client)
    main.ETAT["lire_anneau"] = faux_anneau({})
    r = client.get("/api/restaurer")
    assert r.status_code == 404 and "aucune sauvegarde" in r.json()["detail"]
    main.ETAT["lire_anneau"] = faux_anneau({"2026-11-14": REGLAGES})
    r = client.get("/api/restaurer", params={"le": "2026-01-01"})
    assert r.status_code == 404 and "2026-01-01" in r.json()["detail"]
    assert client.post("/api/restaurer", json={}).status_code == 400


def test_anneau_injoignable(client):
    connecter(client)

    def eteint(adresse, jeton):
        raise urllib.error.URLError("connexion refusée")
    main.ETAT["lire_anneau"] = eteint
    for r in (client.get("/api/restaurer"), client.get("/api/restaurer", params={"le": "2026-11-14"}),
              client.post("/api/restaurer", json={"le": "2026-11-14"})):
        assert r.status_code == 503 and "Anneau injoignable" in r.json()["detail"]
    assert client.get("/api/reglages").json()["reglages"] == REGLAGES


def test_restaurer_sans_jeton_commun(monkeypatch):
    monkeypatch.delenv("MAISON_JETON", raising=False)
    with demarrer() as c:
        connecter(c)
        r = c.get("/api/restaurer")
        assert r.status_code == 503 and "MAISON_JETON" in r.json()["detail"]
    main.ETAT.clear()
