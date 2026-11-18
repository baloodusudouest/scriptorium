"""0.7.0 (socle 0.9.0) : santé des tâches de fond dans /health et copie cohérente de la base."""
from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import main, maison
from app.base import maintenant
from app.config import Config

MOT_DE_PASSE = "mot-de-passe-de-test"
JETON = "jeton-commun-essai"


@pytest.fixture(autouse=True)
def registre_neuf(monkeypatch):
    """Registre de tâches propre à chaque test (le vrai vit le temps du processus)."""
    monkeypatch.setattr(maison, "TACHES", maison.Taches())
    monkeypatch.setenv("MAISON_JETON", JETON)


@pytest.fixture()
def client(tmp_path):
    main.ETAT.clear()
    main.ETAT["cfg"] = Config(password=MOT_DE_PASSE, data=tmp_path, static=tmp_path / "static",
                              attente_connexion=False, travail_auto=False, bookdrop=tmp_path / "bookdrop")
    with TestClient(main.app) as c:
        yield c
    main.ETAT.clear()


def par_nom(sante):
    return {t["nom"]: t for t in sante["taches"]}


def un_tour(travail):
    """Fait tourner le fil de travail une seule fois (coupé dans les tests) : la purge, au début du tour, l'arrête."""
    purge = travail.purger_corbeille

    def purge_puis_arret():
        travail.arreter()
        return purge()
    travail.purger_corbeille = purge_puis_arret
    travail.demarrer()
    travail._fil.join(5)
    assert not travail._fil.is_alive()


def test_health_porte_la_sante_sans_message_sans_jeton(client):
    un_tour(main.ETAT["travail"])
    r = client.get("/health").json()
    assert r["version_socle"] == "0.9.1"
    taches = par_nom(r)
    assert set(taches) == {"purge-corbeille", "decoupe", "lecture-mistral", "pdf-a5", "copie-des-bases"}
    assert taches["purge-corbeille"]["type"] == "reguliere" and taches["purge-corbeille"]["periode_s"] == 3600
    assert taches["purge-corbeille"]["etat"] == "ok"
    assert {taches[n]["type"] for n in ("decoupe", "lecture-mistral", "pdf-a5")} == {"demande"}
    assert taches["copie-des-bases"]["type"] == "reguliere" and taches["copie-des-bases"]["periode_s"] == 86400
    assert all("message" not in t for t in r["taches"])
    assert r["copie_base"] == {"le": None, "ok": False, "bases": ["scriptorium.db"], "taille": 0}
    avec = client.get("/health", headers={"Authorization": f"Bearer {JETON}"}).json()
    assert all("message" in t for t in avec["taches"])
    assert all("message" not in t for t in client.get("/health", headers={"Authorization": "Bearer faux"}).json()["taches"])
    assert client.post("/api/connexion", json={"mot_de_passe": MOT_DE_PASSE}).status_code == 200
    assert all("message" in t for t in client.get("/health").json()["taches"])


def test_purge_ratee_passe_en_retard(client):
    travail = main.ETAT["travail"]

    def purge_cassee():
        raise OSError("disque plein")
    travail.purger_corbeille = purge_cassee
    un_tour(travail)
    t = par_nom(client.get("/health", headers={"Authorization": f"Bearer {JETON}"}).json())["purge-corbeille"]
    assert t["etat"] == "en_retard" and t["message"] == "OSError: disque plein"


def test_decoupe_qui_casse_passe_en_erreur(client):
    travail = main.ETAT["travail"]
    travail.base.ecrire("INSERT INTO livres (titre, etat, cree_le) VALUES ('Livre inventé', 'decoupe', ?)", maintenant())

    def decoupe_cassee(livre_id):
        raise RuntimeError("pdfium a disparu")
    travail.decouper = decoupe_cassee
    with pytest.raises(RuntimeError):            # comme avant : l'erreur remonte au fil, qui la note au journal
        travail.une_tache()
    assert par_nom(client.get("/health").json())["decoupe"]["etat"] == "erreur"


def test_copie_de_la_base(client, tmp_path):
    r = maison.copier_bases([tmp_path / "scriptorium.db"], tmp_path / "copies")
    assert r["ok"] and r["bases"] == ["scriptorium.db"] and r["taille"] > 0
    assert client.get("/health").json()["copie_base"]["ok"] is True
    copie = sqlite3.connect(tmp_path / "copies" / "scriptorium-derniere.db")
    try:
        assert copie.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        copie.close()
