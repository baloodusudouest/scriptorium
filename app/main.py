"""Scriptorium : d'un livre scanné à un livre en texte (FastAPI + interface Svelte compilée).

Livraison 0.1 : import d'un PDF (envoi par morceaux), découpe en pages et inventaire des pages manquantes,
lecture par Mistral OCR, EPUB recomposé simple et PDF d'archive, dépôt dans le bookdrop de Grimmory.

Routes publiques : /health, /api/session, /api/connexion. Tout le reste demande la session.
Écritures hors de chez Scriptorium (gardées par exiger_ecriture, journalisées) :
    - l'envoi des pages à Mistral (elles sortent de la maison et la lecture est payante) ;
    - le dépôt dans le bookdrop de Grimmory (jamais par-dessus un fichier existant).
"""
from __future__ import annotations

import asyncio
import shutil
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response

from . import __version__, fabrication, inventaire, mistral
from .auth import COMMUN, DUREE, Sessions
from .base import Base, maintenant
from .config import APPLI, Config, charger
from .travail import Travail, supprimer_dossier, vignette

ETAT: dict = {}
PUBLIQUES = ("/api/connexion", "/api/session")
ETATS_LIVRE = {
    "envoi": "Envoi du PDF", "decoupe": "Découpe des pages", "inventaire": "Inventaire à confirmer",
    "lecture": "Lecture", "pret": "Prêt à fabriquer", "erreur": "En erreur",
}


def _fichier_generation(cfg: Config) -> Path:
    return cfg.data / "session_generation"


def _lire_generation(cfg: Config) -> int:
    try:
        return int(_fichier_generation(cfg).read_text().strip())
    except (OSError, ValueError):
        return 0


def _inscriptible(dossier: Path | None) -> bool:
    if not dossier or not dossier.is_dir():
        return False
    essai = dossier / ".scriptorium-essai"
    try:
        essai.write_text("ok")
        essai.unlink()
        return True
    except OSError:
        return False


@asynccontextmanager
async def cycle(app: FastAPI):
    cfg = ETAT.get("cfg") or charger()
    cfg.data.mkdir(parents=True, exist_ok=True)
    base = Base(cfg.data)
    travail = Travail(base, cfg)
    ETAT.update(cfg=cfg, base=base, travail=travail, sessions=Sessions(APPLI, cfg.password, _lire_generation(cfg)))
    # Un envoi ou une lecture interrompus par un redémarrage reprennent tout seuls.
    if cfg.travail_auto:
        travail.demarrer()
    yield
    travail.arreter()
    base.fermer()


app = FastAPI(title=APPLI, version=__version__, lifespan=cycle, docs_url=None, redoc_url=None)


# ================================================================ sécurité

@app.middleware("http")
async def garde(request: Request, appel):
    chemin = request.url.path
    if chemin.startswith("/api/") and chemin not in PUBLIQUES and not ETAT["sessions"].connecte(request.cookies):
        return JSONResponse({"detail": "Connexion nécessaire."}, status_code=401)
    reponse = await appel(request)
    if chemin.startswith("/api/") and "Cache-Control" not in reponse.headers:
        reponse.headers["Cache-Control"] = "no-store"
    return reponse


class LectureSeule(Exception):
    """Écriture refusée : l'appli tourne en lecture seule (SCRIPTORIUM_LECTURE_SEULE)."""


def exiger_ecriture(quoi: str = "") -> None:
    """À appeler en tête de toute route qui envoie ou écrit hors de Scriptorium (Mistral, Grimmory).
    Le refus arrive avant toute trace dans un journal."""
    if ETAT["cfg"].lecture_seule:
        raise LectureSeule(f"Mode lecture seule : rien n'est {quoi or 'écrit'}.")


@app.exception_handler(LectureSeule)
async def _lecture_seule(_: Request, exc: LectureSeule):
    return JSONResponse({"detail": str(exc)}, status_code=409)


# ================================================================ public et connexion

@app.get("/health")
def sante():
    return {"ok": True, "version": __version__}


@app.get("/api/session")
def session(request: Request):
    s = ETAT["sessions"]
    return {"connecte": s.connecte(request.cookies), "version": __version__,
            "lecture_seule": ETAT["cfg"].lecture_seule}


@app.post("/api/connexion")
async def connexion(corps: dict = Body(...)):
    s = ETAT["sessions"]
    if ETAT["cfg"].attente_connexion:
        await asyncio.sleep(s.attente())
    if not s.verifier_mot_de_passe(str(corps.get("mot_de_passe", ""))):
        raise HTTPException(401, "Mot de passe incorrect.")
    r = JSONResponse({"ok": True})
    r.set_cookie(s.cookie, s.creer(), max_age=DUREE, httponly=True, samesite="strict")
    return r


@app.post("/api/deconnexion")
def deconnexion():
    s = ETAT["sessions"]
    s.generation += 1
    try:
        _fichier_generation(ETAT["cfg"]).write_text(str(s.generation))
    except OSError:
        pass  # volume en lecture seule : la déconnexion vaut jusqu'au prochain redémarrage
    r = JSONResponse({"ok": True})
    r.delete_cookie(s.cookie)
    r.delete_cookie(COMMUN)      # « Se déconnecter » ferme aussi la connexion commune
    return r


# ================================================================ livres

def _livre(livre_id: int) -> dict:
    livre = ETAT["base"].un("SELECT * FROM livres WHERE id = ?", livre_id)
    if not livre:
        raise HTTPException(404, "Livre inconnu.")
    return livre


def _pages(livre_id: int) -> list[dict]:
    return ETAT["base"].lire("SELECT rang, numero_lu, numero, ecartee, lecture, lecture_erreur, pages_facturees "
                             "FROM pages WHERE livre_id = ? ORDER BY rang", livre_id)


def _bilan(livre: dict, pages: list[dict]) -> dict:
    gardees = [p for p in pages if not p["ecartee"]]
    inv = inventaire.analyser([p["numero"] for p in gardees])
    # Les places renvoyées par l'analyse sont celles des pages gardées : on les ramène aux rangs du PDF.
    inv["sans_numero"] = [gardees[i]["rang"] for i in inv["sans_numero"]]
    compte = {k: sum(1 for p in gardees if p["lecture"] == k) for k in ("attente", "faite", "douteuse", "erreur")}
    a_lire = compte["attente"] + compte["erreur"]
    cfg = ETAT["cfg"]
    return {
        "pages": len(pages), "gardees": len(gardees), "ecartees": len(pages) - len(gardees),
        "inventaire": inv, "lecture": compte,
        "estimation": {"pages": a_lire, "dollars": round(a_lire * cfg.prix_page, 2)},
        "facturees": sum(p["pages_facturees"] for p in pages),
        "fabrique": bool(livre["epub"]) and (ETAT["base"].dossier(livre["id"]) / "sortie" / livre["epub"]).exists(),
    }


def _vue(livre: dict, avec_pages: bool = False) -> dict:
    pages = _pages(livre["id"])
    v = {**livre, "etat_nom": ETATS_LIVRE.get(livre["etat"], livre["etat"]), "bilan": _bilan(livre, pages)}
    if avec_pages:
        v["liste_pages"] = pages
    return v


@app.get("/api/livres")
def livres():
    return [_vue(l) for l in ETAT["base"].lire("SELECT * FROM livres ORDER BY id DESC")]


@app.post("/api/livres")
def nouveau_livre(corps: dict = Body(...)):
    titre = str(corps.get("titre", "")).strip()
    nom = str(corps.get("nom_fichier", "")).strip()
    octets = int(corps.get("octets") or 0)
    if not titre:
        raise HTTPException(422, "Donne un titre au livre.")
    if not nom.lower().endswith(".pdf") or octets <= 0:
        raise HTTPException(422, "Choisis un fichier PDF.")
    base: Base = ETAT["base"]
    libre = shutil.disk_usage(ETAT["cfg"].data).free
    if octets * 3 > libre:   # le PDF, ses pages découpées et le livre fabriqué
        raise HTTPException(507, f"Place insuffisante sur le NAS : il faut environ {octets * 3 // 10**6} Mo, il en reste {libre // 10**6}.")
    livre_id = base.ecrire("INSERT INTO livres (titre, auteur, langue, source_nom, source_octets, cree_le) VALUES (?, ?, ?, ?, ?, ?)",
                           titre, str(corps.get("auteur", "")).strip(), str(corps.get("langue") or "fr")[:5], nom, octets, maintenant())
    base.dossier(livre_id).mkdir(parents=True, exist_ok=True)
    return _vue(_livre(livre_id))


@app.get("/api/livres/{livre_id}")
def livre(livre_id: int):
    return _vue(_livre(livre_id), avec_pages=True)


@app.post("/api/livres/{livre_id}/fiche")
def fiche(livre_id: int, corps: dict = Body(...)):
    _livre(livre_id)
    titre = str(corps.get("titre", "")).strip()
    if not titre:
        raise HTTPException(422, "Le titre ne peut pas être vide.")
    ETAT["base"].ecrire("UPDATE livres SET titre = ?, auteur = ?, langue = ? WHERE id = ?", titre,
                        str(corps.get("auteur", "")).strip(), str(corps.get("langue") or "fr")[:5], livre_id)
    return _vue(_livre(livre_id))


@app.post("/api/livres/{livre_id}/supprimer")
def supprimer(livre_id: int):
    livre_ = _livre(livre_id)
    base: Base = ETAT["base"]
    base.ecrire("DELETE FROM livres WHERE id = ?", livre_id)
    supprimer_dossier(base.dossier(livre_id))
    base.noter("suppression", livre_id, livre_["titre"])
    return {"ok": True}


# ---------------------------------------------------------------- envoi par morceaux

def _partiel(livre_id: int) -> Path:
    return ETAT["base"].dossier(livre_id) / "source.pdf.partiel"


@app.get("/api/livres/{livre_id}/envoi")
def envoi_etat(livre_id: int):
    livre_ = _livre(livre_id)
    p = _partiel(livre_id)
    return {"recus": p.stat().st_size if p.exists() else 0, "attendus": livre_["source_octets"]}


@app.put("/api/livres/{livre_id}/envoi")
async def envoi_morceau(livre_id: int, debut: int, request: Request):
    """Ajoute un morceau au PDF en cours d'envoi. « debut » doit être la taille déjà reçue : un morceau
    renvoyé après une coupure n'est jamais ajouté deux fois, et un trou est refusé."""
    livre_ = _livre(livre_id)
    if livre_["etat"] != "envoi":
        raise HTTPException(409, "Ce livre n'attend plus d'envoi.")
    p = _partiel(livre_id)
    recus = p.stat().st_size if p.exists() else 0
    if debut != recus:
        return JSONResponse({"detail": "Reprise de l'envoi.", "recus": recus}, status_code=409)
    ecrits = 0
    with p.open("ab") as f:
        async for bout in request.stream():
            ecrits += len(bout)
            if recus + ecrits > livre_["source_octets"]:
                raise HTTPException(413, "Le fichier envoyé est plus gros qu'annoncé.")
            f.write(bout)
    return {"recus": recus + ecrits}


@app.post("/api/livres/{livre_id}/envoi/fin")
def envoi_fin(livre_id: int):
    livre_ = _livre(livre_id)
    p = _partiel(livre_id)
    recus = p.stat().st_size if p.exists() else 0
    if recus != livre_["source_octets"]:
        raise HTTPException(409, f"Envoi incomplet : {recus} octets reçus sur {livre_['source_octets']}.")
    with p.open("rb") as f:
        if f.read(5) != b"%PDF-":
            raise HTTPException(422, "Ce fichier n'est pas un PDF.")
    p.rename(p.with_name("source.pdf"))
    ETAT["base"].ecrire("UPDATE livres SET etat = 'decoupe', avancement = 0 WHERE id = ?", livre_id)
    ETAT["base"].noter("import", livre_id, f"{livre_['source_nom']} ({recus // 10**6} Mo)")
    return _vue(_livre(livre_id))


# ---------------------------------------------------------------- pages et inventaire

@app.get("/api/livres/{livre_id}/pages/{rang}.jpg")
def image_page(livre_id: int, rang: int, cote: int = 0):
    chemin = ETAT["base"].dossier(livre_id) / "pages" / f"{rang:04d}.jpg"
    if not chemin.is_file():
        raise HTTPException(404, "Page inconnue.")
    entetes = {"Cache-Control": "private, max-age=86400"}   # les images, elles, peuvent rester en cache
    if cote:
        return Response(vignette(chemin, max(80, min(cote, 1600))), media_type="image/jpeg", headers=entetes)
    return FileResponse(chemin, media_type="image/jpeg", headers=entetes)


@app.get("/api/livres/{livre_id}/pages/{rang}/texte")
def texte_page(livre_id: int, rang: int):
    chemin = ETAT["base"].dossier(livre_id) / "lu" / f"{rang:04d}.md"
    return {"markdown": chemin.read_text(encoding="utf-8") if chemin.is_file() else ""}


@app.post("/api/livres/{livre_id}/pages/{rang}")
def modifier_page(livre_id: int, rang: int, corps: dict = Body(...)):
    """Corrige le numéro imprimé d'une page, ou l'écarte (page en double, page inutile)."""
    _livre(livre_id)
    base: Base = ETAT["base"]
    if not base.un("SELECT id FROM pages WHERE livre_id = ? AND rang = ?", livre_id, rang):
        raise HTTPException(404, "Page inconnue.")
    if "numero" in corps:
        n = corps["numero"]
        n = int(n) if n not in (None, "") else None
        if n is not None and not 0 < n < 10000:
            raise HTTPException(422, "Numéro de page entre 1 et 9999.")
        base.ecrire("UPDATE pages SET numero = ? WHERE livre_id = ? AND rang = ?", n, livre_id, rang)
    if "ecartee" in corps:
        base.ecrire("UPDATE pages SET ecartee = ? WHERE livre_id = ? AND rang = ?", 1 if corps["ecartee"] else 0, livre_id, rang)
    return _vue(_livre(livre_id), avec_pages=True)


@app.post("/api/livres/{livre_id}/numeros/relire")
def relire_numeros(livre_id: int):
    """Relit les numéros imprimés de toutes les pages (après une amélioration de la lecture). Les numéros
    corrigés à la main sont remplacés ; les pages écartées le restent. Seulement avant la lecture par Mistral."""
    livre_ = _livre(livre_id)
    if livre_["etat"] not in ("inventaire", "lecture") or livre_["lecture_demandee"] or \
            ETAT["base"].un("SELECT COUNT(*) AS n FROM pages WHERE livre_id = ? AND lecture != 'attente'", livre_id)["n"]:
        raise HTTPException(409, "Les numéros ne se relisent qu'avant la lecture par Mistral.")
    ETAT["base"].ecrire("UPDATE livres SET etat = 'decoupe', relire = 1, inventaire_confirme = 0, avancement = 0 WHERE id = ?", livre_id)
    return _vue(_livre(livre_id))


@app.post("/api/livres/{livre_id}/inventaire/confirmer")
def confirmer_inventaire(livre_id: int):
    livre_ = _livre(livre_id)
    if livre_["etat"] not in ("inventaire", "lecture", "pret"):
        raise HTTPException(409, "L'inventaire n'est pas encore prêt.")
    etat = "lecture" if livre_["etat"] == "inventaire" else livre_["etat"]
    ETAT["base"].ecrire("UPDATE livres SET inventaire_confirme = 1, etat = ? WHERE id = ?", etat, livre_id)
    return _vue(_livre(livre_id), avec_pages=True)


# ---------------------------------------------------------------- lecture par Mistral

@app.post("/api/livres/{livre_id}/lecture")
def lancer_lecture(livre_id: int):
    livre_ = _livre(livre_id)
    if not livre_["inventaire_confirme"]:
        raise HTTPException(409, "Confirme d'abord l'inventaire des pages.")
    if not ETAT["cfg"].mistral_cle:
        raise HTTPException(409, "Aucune clé Mistral dans la stack (SCRIPTORIUM_MISTRAL_CLE).")
    exiger_ecriture("envoyé à Mistral")
    ETAT["base"].ecrire("UPDATE livres SET etat = 'lecture', lecture_demandee = 1, erreur = '' WHERE id = ?", livre_id)
    return _vue(_livre(livre_id))


# ---------------------------------------------------------------- fabrication et dépôt

@app.post("/api/livres/{livre_id}/fabriquer")
def fabriquer(livre_id: int):
    livre_ = _livre(livre_id)
    if not livre_["inventaire_confirme"]:
        raise HTTPException(409, "Confirme d'abord l'inventaire des pages.")
    base: Base = ETAT["base"]
    pages = base.lire("SELECT * FROM pages WHERE livre_id = ? AND ecartee = 0 ORDER BY rang", livre_id)
    if not pages:
        raise HTTPException(409, "Aucune page à mettre dans le livre.")
    dossier = base.dossier(livre_id)
    nom = fabrication.nom_fichier(livre_["auteur"], livre_["titre"])
    bilan = fabrication.fabriquer_epub(dossier, livre_, pages, dossier / "sortie" / f"{nom}.epub")
    fabrication.fabriquer_archive(dossier, pages, dossier / "sortie" / f"{nom} - pages.pdf")
    base.ecrire("UPDATE livres SET epub = ?, archive = ? WHERE id = ?", f"{nom}.epub", f"{nom} - pages.pdf", livre_id)
    return {**_vue(_livre(livre_id)), "fabrication": bilan}


@app.get("/api/livres/{livre_id}/telecharger/{quoi}")
def telecharger(livre_id: int, quoi: str):
    livre_ = _livre(livre_id)
    nom = {"epub": livre_["epub"], "archive": livre_["archive"]}.get(quoi)
    chemin = ETAT["base"].dossier(livre_id) / "sortie" / (nom or "")
    if not nom or not chemin.is_file():
        raise HTTPException(404, "Livre pas encore fabriqué.")
    media = "application/epub+zip" if quoi == "epub" else "application/pdf"
    return FileResponse(chemin, media_type=media, filename=nom)


@app.post("/api/livres/{livre_id}/deposer")
def deposer(livre_id: int):
    """Dépose l'EPUB dans le bookdrop de Grimmory. Seulement l'EPUB : un PDF du même livre créerait une
    seconde fiche dans la bibliothèque. Jamais par-dessus un fichier existant."""
    livre_ = _livre(livre_id)
    source = ETAT["base"].dossier(livre_id) / "sortie" / (livre_["epub"] or "")
    if not livre_["epub"] or not source.is_file():
        raise HTTPException(409, "Fabrique d'abord le livre.")
    exiger_ecriture("déposé dans Grimmory")
    dossier = ETAT["cfg"].bookdrop
    if not _inscriptible(dossier):
        raise HTTPException(409, "Le dossier d'import de Grimmory n'est pas accessible en écriture (SCRIPTORIUM_BOOKDROP).")
    cible = dossier / source.name
    if cible.exists():
        raise HTTPException(409, f"« {source.name} » est déjà dans le dossier d'import de Grimmory : rien n'a été remplacé.")
    tmp = dossier / f".{source.name}.scriptorium"
    shutil.copyfile(source, tmp)
    tmp.rename(cible)   # Grimmory ne voit le fichier qu'une fois complet
    ETAT["base"].ecrire("UPDATE livres SET depose_le = ? WHERE id = ?", maintenant(), livre_id)
    ETAT["base"].noter("depot_grimmory", livre_id, source.name)
    return _vue(_livre(livre_id))


# ================================================================ services, réglages

@app.get("/api/services")
def services():
    cfg: Config = ETAT["cfg"]
    disque = shutil.disk_usage(cfg.data)
    return {
        "lecture_seule": cfg.lecture_seule,
        "mistral": {"cle": bool(cfg.mistral_cle), "modele": cfg.mistral_modele, "prix_page": cfg.prix_page,
                    "facturees": ETAT["base"].un("SELECT COALESCE(SUM(pages_facturees), 0) AS n FROM pages")["n"]},
        "grimmory": {"configure": bool(cfg.bookdrop), "inscriptible": _inscriptible(cfg.bookdrop)},
        "disque": {"total": disque.total, "libre": disque.free, "inscriptible": _inscriptible(cfg.data)},
        "travail": ETAT["travail"].en_cours,
    }


@app.post("/api/services/mistral/verifier")
def verifier_mistral():
    cfg: Config = ETAT["cfg"]
    return mistral.verifier(cfg.mistral_cle, cfg.mistral_url)


@app.get("/api/journal")
def journal():
    return ETAT["base"].lire("SELECT j.*, l.titre FROM journal j LEFT JOIN livres l ON l.id = j.livre_id ORDER BY j.id DESC LIMIT 200")


# ================================================================ interface

@app.get("/{chemin:path}")
def interface(chemin: str):
    statique = ETAT["cfg"].static
    fichier = (statique / chemin).resolve() if chemin else None
    if fichier and fichier.is_file() and statique.resolve() in fichier.parents:
        return FileResponse(fichier)
    index = statique / "index.html"
    if index.is_file():
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
    return JSONResponse({"detail": "Interface non compilée."}, status_code=404)
