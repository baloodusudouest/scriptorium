"""0.3.1 : contre-lecture par le PC (Marker) et mots à relire.

Le PC est simulé : pc/calcul.py tourne contre l'appli de test avec un faux lecteur (pas de Marker ici).
"""
from __future__ import annotations

import dataclasses
import sys
import time
from pathlib import Path

import pytest

from app import comparaison, contre, main, mistral
from tests.test_livres import client, importer, pdf_livre  # noqa: F401  (fixture)
from tests.test_relecture import lecture_numerotee

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pc"))
import calcul  # noqa: E402

JETON = "jeton-du-pc-de-calcul-0123456789"
PC = {"Authorization": f"Bearer {JETON}"}


class FauxMarker:
    """Lit « comme Marker » : le texte de Mistral, avec un mot changé et la mise en forme écrasée."""
    nom = "faux marker"

    def __init__(self, remplacements=None):
        self.remplacements = remplacements or {}
        self.vues = []

    def lire(self, chemin: Path) -> str:
        assert chemin.read_bytes()[:2] == b"\xff\xd8"          # une vraie image JPEG
        n = int(chemin.stem.rsplit("-", 1)[1])
        self.vues.append(n)
        texte = f"Recette {9 + n}\nTexte de la page {9 + n}, assez long pour être lu."
        for a, b in self.remplacements.get(n, {}).items():
            texte = texte.replace(a, b)
        return texte


@pytest.fixture()
def pc(client):  # noqa: F811
    main.ETAT["cfg"] = dataclasses.replace(main.ETAT["cfg"], jeton_calcul=JETON)
    client.headers.update(PC)        # même client : les routes /calcul ne regardent que le jeton
    return client


def livre(client, monkeypatch, n=3):  # noqa: F811
    livre_id = importer(client, pdf_livre([None] * n))
    main.ETAT["travail"].tout_faire()
    monkeypatch.setattr(mistral, "lire_page", lecture_numerotee(list(range(10, 10 + n))))
    client.post(f"/api/livres/{livre_id}/lecture")
    main.ETAT["travail"].tout_faire()
    return livre_id


# ---------------------------------------------------------------- comparaison

def test_comparaison_ne_retient_que_les_mots_changes():
    mistral_md = "# Le Négroni\n\n- 3 cl de gin\n\nremuer. Il demanda à son mari un cocktail.\n\n72"
    marker_md = "Le Negroni\n3 cl de gin\nre-\nmuer. Il demanda à son barman un cocktail.\nZ"
    r = comparaison.comparer(mistral_md, marker_md)
    assert [(d["lu"], d["propose"]) for d in r["doutes"]] == [("Négroni", "Negroni"), ("mari", "barman")]
    d = r["doutes"][1]
    assert mistral_md[d["debut"]:d["fin"]] == "mari"         # position juste dans le texte de Mistral
    assert not r["page_entiere"]


def test_comparaison_page_entiere_si_les_lectures_divergent():
    r = comparaison.comparer("Un texte sur le rhum et la canne à sucre des Antilles.", "Recette du pisco sour au blanc d'œuf")
    assert r["page_entiere"] and r["accord"] < 0.5


# ---------------------------------------------------------------- porte du PC

def test_porte_fermee_sans_jeton_et_jeton_verifie(client):  # noqa: F811
    assert client.get("/calcul/travail", headers=PC).status_code == 404       # jeton vide dans la stack
    main.ETAT["cfg"] = dataclasses.replace(main.ETAT["cfg"], jeton_calcul=JETON)
    assert client.get("/calcul/travail", headers={"Authorization": "Bearer faux"}).status_code == 401
    assert client.get("/calcul/travail").status_code == 401
    assert client.get("/calcul/travail", headers=PC).status_code == 204       # rien à faire


def test_le_pc_relit_et_les_mots_differents_sont_a_relire(pc, monkeypatch):
    livre_id = livre(pc, monkeypatch)
    lecteur = FauxMarker({2: {"assez long": "asez long"}})
    while calcul.une_page(pc, lecteur):
        pass
    assert sorted(lecteur.vues) == [1, 2, 3]
    v = pc.get(f"/api/livres/{livre_id}").json()
    assert v["bilan"]["contre"]["faite"] == 3 and v["bilan"]["contre"]["a_relire"] == [2]
    t = pc.get(f"/api/livres/{livre_id}/pages/2/texte").json()
    assert t["marker"].startswith("Recette 11")
    doute = t["comparaison"]["doutes"][0]
    assert (doute["lu"], doute["propose"]) == ("assez", "asez")
    assert t["markdown"][doute["debut"]:doute["fin"]] == "assez"
    services = pc.get("/api/services").json()["pc"]
    assert services["configure"] and services["vu_le"] and services["moteur"] == "faux marker" and services["en_attente"] == 0


def test_page_relue_ou_corrigee_n_est_plus_a_relire(pc, monkeypatch):
    livre_id = livre(pc, monkeypatch)
    lecteur = FauxMarker({1: {"assez": "asez"}, 2: {"assez": "asez"}})
    while calcul.une_page(pc, lecteur):
        pass
    assert pc.get(f"/api/livres/{livre_id}").json()["bilan"]["contre"]["a_relire"] == [1, 2]
    pc.post(f"/api/livres/{livre_id}/pages/1/relue")
    pc.post(f"/api/livres/{livre_id}/pages/2/texte", json={"markdown": "# Recette 11\n\nTexte de la page 11, asez long pour être lu."})
    v = pc.get(f"/api/livres/{livre_id}").json()
    assert v["bilan"]["contre"]["a_relire"] == []
    # Le texte corrigé est recomparé : il ne diffère plus de Marker
    assert pc.get(f"/api/livres/{livre_id}/pages/2/texte").json()["comparaison"]["doutes"] == []


def test_contre_lecture_avant_mistral_comparee_a_l_arrivee_du_texte(pc, monkeypatch):
    livre_id = importer(pc, pdf_livre([None] * 2))
    main.ETAT["travail"].tout_faire()
    lecteur = FauxMarker({1: {"assez": "asez"}})
    while calcul.une_page(pc, lecteur):
        pass
    assert pc.get(f"/api/livres/{livre_id}").json()["bilan"]["contre"]["a_relire"] == []   # pas encore de texte Mistral
    monkeypatch.setattr(mistral, "lire_page", lecture_numerotee([10, 11]))
    pc.post(f"/api/livres/{livre_id}/lecture")
    main.ETAT["travail"].tout_faire()
    assert pc.get(f"/api/livres/{livre_id}").json()["bilan"]["contre"]["a_relire"] == [1]


def test_page_illisible_par_le_pc_et_page_abandonnee_reproposee(pc, monkeypatch):
    livre_id = livre(pc, monkeypatch, n=2)

    class EnPanne(FauxMarker):
        def lire(self, chemin):
            raise RuntimeError("modèle absent")
    assert calcul.une_page(pc, EnPanne())
    pages = pc.get(f"/api/livres/{livre_id}").json()["liste_pages"]
    assert pages[0]["contre"] == "erreur" and "modèle absent" in pages[0]["contre_erreur"]
    # Le PC prend la page 2 puis s'éteint : elle revient au bout de 15 minutes
    assert pc.get("/calcul/travail").json()["rang"] == 2
    assert pc.get("/calcul/travail").status_code == 204
    monkeypatch.setattr(contre.time, "time", lambda: time.time_ns() / 1e9 + contre.DELAI_REPRISE + 1)
    assert pc.get("/calcul/travail").json()["rang"] == 2


def test_rotation_relance_la_contre_lecture(pc, monkeypatch):
    livre_id = livre(pc, monkeypatch, n=1)
    while calcul.une_page(pc, FauxMarker()):
        pass
    pc.post(f"/api/livres/{livre_id}/pages/1/tourner")
    p = pc.get(f"/api/livres/{livre_id}").json()["liste_pages"][0]
    assert p["contre"] == "attente"
    assert pc.get(f"/api/livres/{livre_id}/pages/1/texte").json()["marker"] is None


def test_boucle_du_pc_attend_quand_rien_n_attend(pc, monkeypatch):
    attentes = []
    monkeypatch.setattr(calcul.time, "sleep", lambda s: attentes.append(s))
    tours = iter([False, True])
    calcul.boucle(pc, FauxMarker(), attente=30, arret=lambda: next(tours))
    assert attentes == [30]
