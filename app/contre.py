"""Contre-lecture par le PC de calcul (0.3.1), côté NAS.

Le PC (conteneur `pc/calcul.yml`, Marker sur le processeur) vient chercher le travail : il demande une page,
la lit et renvoie son texte. Il ne peut rien faire d'autre. Le PC éteint ne bloque rien : les pages attendent
seulement leur contre-lecture.

Pages proposées au PC : celles des livres découpés, gardées, pas corrigées à la main, sans contre-lecture,
d'abord celles que Mistral a déjà lues (la comparaison peut se faire tout de suite). Une page prise par le PC
et jamais rendue (PC éteint en route) redevient libre au bout de 15 minutes.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from . import comparaison
from .base import Base, maintenant

DELAI_REPRISE = 15 * 60   # secondes


def prochaine_page(base: Base) -> dict | None:
    limite = time.time() - DELAI_REPRISE
    page = base.un(
        "SELECT p.id, p.livre_id, p.rang, l.langue FROM pages p JOIN livres l ON l.id = p.livre_id "
        "WHERE l.etat IN ('inventaire', 'lecture', 'pret') AND l.supprime_le = '' AND p.ecartee = 0 AND p.texte_main = 0 "
        "AND (p.contre = 'attente' OR (p.contre = 'calcul' AND p.contre_depuis < ?)) "
        "ORDER BY (p.lecture = 'faite') DESC, l.id, p.ordre LIMIT 1", limite)
    if page:
        base.ecrire("UPDATE pages SET contre = 'calcul', contre_depuis = ?, contre_erreur = '' WHERE id = ?",
                    time.time(), page["id"])
    return page


def pages_en_attente(base: Base) -> int:
    return base.un(
        "SELECT COUNT(*) AS n FROM pages p JOIN livres l ON l.id = p.livre_id "
        "WHERE l.etat IN ('inventaire', 'lecture', 'pret') AND l.supprime_le = '' AND p.ecartee = 0 AND p.texte_main = 0 "
        "AND p.contre IN ('attente', 'calcul')")["n"]


def signaler_passage(base: Base, moteur: str) -> None:
    base.memo("pc_vu_le", maintenant())
    if moteur:
        base.memo("pc_moteur", moteur[:80])


def enregistrer(base: Base, livre_id: int, rang: int, markdown: str | None, erreur: str = "") -> None:
    page = base.un("SELECT id FROM pages WHERE livre_id = ? AND rang = ?", livre_id, rang)
    if not page:
        return
    if erreur or markdown is None:
        base.ecrire("UPDATE pages SET contre = 'erreur', contre_erreur = ? WHERE id = ?", (erreur or "aucun texte")[:500], page["id"])
        return
    lu = base.dossier(livre_id) / "lu"
    lu.mkdir(parents=True, exist_ok=True)
    (lu / f"{rang:04d}.marker.md").write_text(markdown, encoding="utf-8")
    base.ecrire("UPDATE pages SET contre = 'faite', contre_erreur = '' WHERE id = ?", page["id"])
    comparer_page(base, livre_id, rang)


def comparer_page(base: Base, livre_id: int, rang: int) -> dict | None:
    """Compare le texte gardé de la page (Mistral ou corrigé) à la contre-lecture, s'il y a les deux.
    Écrit lu/NNNN.doutes.json et le nombre de doutes en base ; renvoie le résultat."""
    lu = base.dossier(livre_id) / "lu"
    texte, contre = lu / f"{rang:04d}.md", lu / f"{rang:04d}.marker.md"
    fichier = lu / f"{rang:04d}.doutes.json"
    if not (texte.is_file() and contre.is_file()):
        fichier.unlink(missing_ok=True)
        base.ecrire("UPDATE pages SET doutes = 0, accord = NULL WHERE livre_id = ? AND rang = ?", livre_id, rang)
        return None
    r = comparaison.comparer(texte.read_text(encoding="utf-8"), contre.read_text(encoding="utf-8"))
    fichier.write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
    base.ecrire("UPDATE pages SET doutes = ?, accord = ? WHERE livre_id = ? AND rang = ?",
                len(r["doutes"]), r["accord"], livre_id, rang)
    return r


def lire_doutes(dossier: Path, rang: int) -> dict | None:
    fichier = dossier / "lu" / f"{rang:04d}.doutes.json"
    try:
        return json.loads(fichier.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def a_relire(page: dict) -> bool:
    """Page signalée par la contre-lecture et pas encore relue."""
    if page.get("relue") or page.get("texte_main") or page.get("ecartee") or page.get("contre") != "faite":
        return False
    accord = page.get("accord")
    return bool(page.get("doutes")) or (accord is not None and accord < comparaison.ACCORD_FAIBLE)


# ---------------------------------------------------------------- fiche « PC de calcul » (0.8.0, contrat 3)

VU_RECEMMENT_S = 10 * 60    # passé il y a moins de 10 minutes : la fiche dit « Répond » (même seuil que l'ancien écran)


def depuis_passage(vu_le: str | None) -> float | None:
    """Secondes depuis le dernier passage du PC (None : jamais vu, ou date illisible)."""
    if not vu_le:
        return None
    try:
        from datetime import datetime
        return max(0.0, time.time() - datetime.fromisoformat(vu_le).timestamp())
    except ValueError:
        return None


def _texte_depuis(secondes: float | None) -> str:
    if secondes is None:
        return "jamais vu"
    minutes = round(secondes / 60)
    if minutes < 2:
        return "vu à l'instant"
    if minutes < 120:
        return f"vu il y a {minutes} min"
    if minutes < 2880:
        return f"vu il y a {round(minutes / 60)} h"
    return f"vu il y a {round(minutes / 1440)} jours"


def essai(base: Base) -> tuple[bool, str]:
    """« Vérifier » du PC de calcul : lit seulement la date du dernier passage notée par la porte /calcul.
    Scriptorium n'appelle jamais le PC (c'est lui qui vient chercher le travail) : rien ne peut le réveiller."""
    vu = depuis_passage(base.memo("pc_vu_le"))
    attente = pages_en_attente(base)
    pages = f"{attente} page{'s' if attente > 1 else ''} en attente"
    if vu is None:
        return False, f"Le PC n'est encore jamais passé · {pages}."
    moteur = base.memo("pc_moteur")
    texte = f"{_texte_depuis(vu).capitalize()}{f' · {moteur}' if moteur else ''} · {pages}."
    if vu < VU_RECEMMENT_S:
        return True, texte
    return False, f"{texte} PC éteint, en veille ou conteneur arrêté."


def guide(base: Base, jeton_regle: bool) -> dict:
    """Marche à suivre de la fiche « PC de calcul » (même blocs que « IA du PC » de Gazette) : réglages lus,
    marche normale, pannes connues avec les commandes à taper sur le PC, installation (une seule fois).
    Repris de l'ancien écran Connexion, de pc/LISEZMOI.md, pc/calcul.yml, pc/.env.exemple et des messages de
    pc/calcul.py. Aucune valeur secrète : le jeton n'est jamais montré."""
    vu_le = base.memo("pc_vu_le")
    vu = depuis_passage(vu_le)
    moteur = base.memo("pc_moteur")
    attente = pages_en_attente(base)
    if vu_le and vu is not None:
        from datetime import datetime
        dernier = datetime.fromisoformat(vu_le).strftime("%d/%m/%Y à %H:%M") + f" ({_texte_depuis(vu)})"
    else:
        dernier = "le PC n'est encore jamais passé"
    dc = "docker compose -f calcul.yml"
    return {
        "reglages": [
            {"nom": "Sens de la liaison", "valeur": "Le PC vient chercher le travail chez Scriptorium (porte /calcul) ; "
                                                   "Scriptorium n'appelle jamais le PC, Vérifier ne peut donc pas le réveiller."},
            {"nom": "Jeton (SCRIPTORIUM_JETON_CALCUL)",
             "valeur": "réglé dans la stack (la valeur de la stack, même valeur dans le .env du PC)" if jeton_regle
             else "pas réglé : la porte du PC est fermée"},
            {"nom": "Adresse à mettre dans le .env du PC (SCRIPTORIUM_URL)",
             "valeur": "http://<adresse du NAS>:8091 (adresse du NAS sur le réseau local, ou son nom Tailscale)"},
            {"nom": "Dernier passage", "valeur": dernier},
            {"nom": "Moteur annoncé", "valeur": moteur or "pas encore annoncé"},
            {"nom": "Pages en attente", "valeur": f"{attente} page{'s' if attente > 1 else ''}"},
            {"nom": "Rythme", "valeur": "une demande toutes les 30 secondes quand rien n'attend (CALCUL_ATTENTE dans le .env du "
                                        "PC) ; de 10 à 20 secondes par page sur le processeur"},
            {"nom": "Répond", "valeur": "si le PC est passé il y a moins de 10 minutes"},
        ],
        "allumer": [
            "Allumer le PC (ou le sortir de veille) et ouvrir Docker Desktop.",
            "Rien d'autre à faire : le conteneur scriptorium-calcul redémarre avec Docker Desktop et demande du travail "
            "toutes les 30 secondes.",
            "Le PC relit chaque page avec Marker, sur son processeur, et rend le texte. Les mots qui diffèrent de la lecture "
            "de Mistral deviennent les mots à relire.",
            "Compter de 10 à 20 secondes par page : un livre de 300 pages se relit en une à deux heures.",
            "Vérifier dans cette fiche : « Répond » dès que le PC est passé (moins de 10 minutes).",
            "PC éteint : rien n'est bloqué. Les pages attendent, et la relecture reste possible sans les mots surlignés. "
            "Une page prise par le PC et jamais rendue (PC éteint en route) est reproposée au bout de 15 minutes.",
        ],
        "terminal": "Commandes à taper sur le PC, dans PowerShell, dans le dossier où se trouvent calcul.yml et .env.",
        "pannes": [
            {"signe": "« Ne répond pas » : le PC n'est jamais passé, ou plus depuis plus de 10 minutes",
             "faire": ["Le PC est-il allumé et sorti de veille ? Docker Desktop est-il ouvert ?",
                       "Le conteneur scriptorium-calcul tourne-t-il ? Sinon, le relancer (première commande).",
                       "Suivre ses journaux (seconde commande) : ils disent pourquoi il ne passe pas (voir les pannes ci-dessous)."],
             "commandes": [f"{dc} up -d", f"{dc} logs -f"]},
            {"signe": "Les journaux disent « Jeton refusé par Scriptorium »",
             "faire": ["Le jeton du .env du PC n'est pas celui de la stack : mettre la même valeur des deux côtés "
                       "(SCRIPTORIUM_JETON_CALCUL), puis relancer le conteneur.",
                       "Le PC réessaie de lui-même toutes les 5 minutes."],
             "commandes": [f"{dc} up -d"]},
            {"signe": "Les journaux disent « Porte /calcul fermée »",
             "faire": ["SCRIPTORIUM_JETON_CALCUL est vide dans la stack du NAS : le remplir dans Portainer et redéployer.",
                       "Le PC réessaie de lui-même toutes les 5 minutes."],
             "commandes": []},
            {"signe": "Les journaux disent « Scriptorium injoignable »",
             "faire": ["SCRIPTORIUM_URL du .env du PC ne mène pas à Scriptorium : l'adresse du NAS et le port 8091 "
                       "(ou son nom Tailscale). La corriger, puis relancer le conteneur.",
                       "Le NAS ou Scriptorium sont-ils allumés ? Le PC réessaie toutes les 30 secondes."],
             "commandes": [f"{dc} up -d"]},
            {"signe": "Le conteneur s'arrête aussitôt : « SCRIPTORIUM_URL et SCRIPTORIUM_JETON_CALCUL sont nécessaires »",
             "faire": ["Le fichier .env manque à côté de calcul.yml, ou une des deux lignes est vide : copier .env.exemple "
                       "en .env et le remplir (voir « Installation »)."],
             "commandes": [f"{dc} up -d"]},
            {"signe": "Les journaux disent « Permission denied » sur /cache",
             "faire": ["Le volume modeles a été créé par une version d'avant la 0.6.7 et appartient à root : le rendre au "
                       "compte calcul une fois (commande), ou supprimer le volume (les modèles se retéléchargent)."],
             "commandes": [f"{dc} run --rm --user root calcul chown -R 1000:1000 /cache"]},
            {"signe": "Les journaux disent « API de Marker indisponible »",
             "faire": ["Marker est appelé par sa commande marker_single à chaque page : ça marche, mais plus lentement.",
                       "Mettre l'image à jour (commandes) ; si le message reste, le signaler."],
             "commandes": [f"{dc} pull", f"{dc} up -d"]},
            {"signe": "Une page est notée en erreur (« page … illisible » dans les journaux)",
             "faire": ["Une page illisible n'arrête pas le PC : il passe à la suivante. La page reste relisible à la main, "
                       "sans mots surlignés."],
             "commandes": []},
            {"signe": "Après une nouvelle version de Scriptorium : mettre à jour l'image du PC",
             "faire": ["Télécharger la nouvelle image, puis relancer le conteneur."],
             "commandes": [f"{dc} pull", f"{dc} up -d"]},
        ],
        "une_fois": [
            {"texte": "Créer un jeton : 32 caractères au hasard, par exemple dans PowerShell :",
             "commande": "-join ((48..57)+(65..90)+(97..122) | Get-Random -Count 32 | % {[char]$_})"},
            {"texte": "Côté NAS : dans la stack Portainer, donner ce jeton à SCRIPTORIUM_JETON_CALCUL, puis redéployer.",
             "commande": ""},
            {"texte": "Côté PC : copier le dossier pc/ du dépôt (calcul.yml et .env.exemple suffisent), renommer .env.exemple "
                      "en .env et le remplir : SCRIPTORIUM_URL (adresse du NAS et port 8091) et SCRIPTORIUM_JETON_CALCUL "
                      "(le même jeton).", "commande": ""},
            {"texte": "Dans ce dossier, lancer le conteneur :", "commande": f"{dc} up -d"},
            {"texte": "Suivre le premier lancement : les modèles (environ 2 Go) se téléchargent une fois, dans un volume Docker.",
             "commande": f"{dc} logs -f"},
        ],
        "note": "Mode d'emploi complet : dossier pc/ du dépôt (fichier LISEZMOI.md), lancé dans Docker Desktop. Le calcul se "
                "fait sur le processeur (Docker Desktop ne donne pas accès à la carte AMD).",
    }
