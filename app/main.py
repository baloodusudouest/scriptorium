"""Scriptorium : d'un livre scanné à un livre en texte (FastAPI + interface Svelte compilée).

Livraison 0.1 : import d'un PDF (envoi par morceaux), découpe en pages et inventaire des pages manquantes,
lecture par Mistral OCR, EPUB recomposé simple et PDF d'archive, dépôt dans le bookdrop de Grimmory.

Routes publiques : /health, /api/session, /api/connexion. Tout le reste demande la session, sauf la porte
du PC de calcul (/calcul/…), gardée par son propre jeton (SCRIPTORIUM_JETON_CALCUL ; vide : porte fermée).
Écritures hors de chez Scriptorium (gardées par exiger_ecriture, journalisées) :
    - l'envoi des pages à Mistral (elles sortent de la maison et la lecture est payante) ;
    - le dépôt dans le bookdrop de Grimmory (jamais par-dessus un fichier existant).
"""
from __future__ import annotations

import asyncio
import hmac
import shutil
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response

from . import __version__, capture, contre, fabrication, inventaire, mistral, notice
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
    return ETAT["base"].lire("SELECT rang, ordre, source, numero_lu, numero_mistral, numero, numero_manuel, ecartee, lecture, "
                             "lecture_erreur, pages_facturees, rendu_choisi, texte_main, contre, contre_erreur, doutes, accord, relue FROM pages WHERE livre_id = ? ORDER BY ordre", livre_id)


def _bilan(livre: dict, pages: list[dict]) -> dict:
    gardees = [p for p in pages if not p["ecartee"]]
    inv = inventaire.analyser([p["numero"] for p in gardees])
    # Les places renvoyées par l'analyse sont celles des pages gardées : on les ramène aux rangs du PDF.
    inv["sans_numero"] = [gardees[i]["rang"] for i in inv["sans_numero"]]
    compte = {k: sum(1 for p in gardees if p["lecture"] == k) for k in ("attente", "faite", "douteuse", "erreur")}
    a_lire = compte["attente"] + compte["erreur"]
    contre_compte = {k: sum(1 for p in gardees if p["contre"] == k and not p["texte_main"]) for k in ("attente", "calcul", "faite", "erreur")}
    cfg = ETAT["cfg"]
    return {
        "pages": len(pages), "gardees": len(gardees), "ecartees": len(pages) - len(gardees),
        "inventaire": inv, "lecture": compte,
        "contre": {**contre_compte, "a_relire": [p["rang"] for p in gardees if contre.a_relire(p)],
                   "pc": bool(ETAT["cfg"].jeton_calcul)},
        "estimation": {"pages": a_lire, "dollars": round(a_lire * cfg.prix_page, 2)},
        "facturees": sum(p["pages_facturees"] for p in pages),
        "pdf": bool(livre["pdf"]) and (ETAT["base"].dossier(livre["id"]) / "sortie" / livre["pdf"]).exists(),
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
    """Fiche du livre : titre, auteur(s) séparés par des virgules, éditeur, année, ISBN, langue."""
    livre_ = _livre(livre_id)
    titre = str(corps.get("titre", livre_["titre"])).strip()
    if not titre:
        raise HTTPException(422, "Le titre ne peut pas être vide.")
    isbn = str(corps.get("isbn", livre_["isbn"]) or "").strip()
    if isbn:
        isbn = notice.isbn13(isbn) or ""
        if not isbn:
            raise HTTPException(422, "ISBN invalide : la clé de contrôle ne correspond pas.")
    annee = str(corps.get("annee", livre_["annee"]) or "").strip()
    if annee and not (annee.isdigit() and len(annee) == 4):
        raise HTTPException(422, "Année sur quatre chiffres.")
    ETAT["base"].ecrire("UPDATE livres SET titre = ?, auteur = ?, langue = ?, editeur = ?, annee = ?, isbn = ? WHERE id = ?", titre,
                        str(corps.get("auteur", livre_["auteur"])).strip()[:300], str(corps.get("langue") or livre_["langue"] or "fr")[:5],
                        str(corps.get("editeur", livre_["editeur"])).strip()[:200], annee, isbn, livre_id)
    return _vue(_livre(livre_id), avec_pages=True)


@app.post("/api/livres/{livre_id}/notice")
def chercher_notice(livre_id: int, corps: dict = Body(default={})):
    """Cherche la fiche par l'ISBN (donné, ou repéré dans le texte lu des premières et dernières pages).
    Renvoie une proposition, rien n'est enregistré."""
    _livre(livre_id)
    if not ETAT["cfg"].recherche_web:
        raise HTTPException(409, "Recherche en ligne coupée (SCRIPTORIUM_RECHERCHE_WEB=non) : remplis la fiche à la main.")
    trouves: list[str] = []
    isbn = str(corps.get("isbn") or "").strip()
    if isbn:
        if not notice.isbn13(isbn):
            raise HTTPException(422, "ISBN invalide : la clé de contrôle ne correspond pas.")
        trouves = [notice.isbn13(isbn)]
    else:
        pages = ETAT["base"].lire("SELECT rang FROM pages WHERE livre_id = ? AND ecartee = 0 ORDER BY ordre", livre_id)
        lu = ETAT["base"].dossier(livre_id) / "lu"
        for p in pages[:12] + pages[-8:]:
            f = lu / f"{p['rang']:04d}.md"
            if f.is_file():
                trouves += [n for n in notice.trouver_isbn(f.read_text(encoding="utf-8")) if n not in trouves]
        if not trouves:
            return {"isbn_trouves": [], "notice": None,
                    "message": "Aucun ISBN dans le texte lu des premières et dernières pages : tape-le (dos du livre ou page de copyright)."}
    try:
        resultat = notice.chercher(trouves[0])
    except notice.ErreurNotice as e:
        raise HTTPException(502, str(e)) from e
    return {"isbn_trouves": trouves, "notice": resultat,
            "message": "" if resultat else f"Ni la BnF ni Open Library ne connaissent l'ISBN {trouves[0]}."}


@app.post("/api/livres/{livre_id}/couverture")
def choisir_couverture(livre_id: int, corps: dict = Body(...)):
    """Page qui sert de couverture à l'EPUB et au PDF (sans choix : la première page gardée)."""
    _livre(livre_id)
    rang = corps.get("rang")
    if rang is not None:
        _page(livre_id, int(rang))
    ETAT["base"].ecrire("UPDATE livres SET couverture = ? WHERE id = ?", int(rang) if rang is not None else None, livre_id)
    return _vue(_livre(livre_id), avec_pages=True)


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
    entetes = {"Cache-Control": "private, max-age=60"}   # court : une page peut être tournée
    if cote:
        return Response(vignette(chemin, max(80, min(cote, 1600))), media_type="image/jpeg", headers=entetes)
    return FileResponse(chemin, media_type="image/jpeg", headers=entetes)


@app.get("/api/livres/{livre_id}/pages/{rang}/texte")
def texte_page(livre_id: int, rang: int):
    """Texte gardé de la page, contre-lecture de Marker et mots qui diffèrent (positions dans le texte gardé)."""
    dossier = ETAT["base"].dossier(livre_id)
    chemin, marker = dossier / "lu" / f"{rang:04d}.md", dossier / "lu" / f"{rang:04d}.marker.md"
    return {"markdown": chemin.read_text(encoding="utf-8") if chemin.is_file() else "",
            "marker": marker.read_text(encoding="utf-8") if marker.is_file() else None,
            "comparaison": contre.lire_doutes(dossier, rang)}


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
        base.ecrire("UPDATE pages SET numero = ?, numero_manuel = ? WHERE livre_id = ? AND rang = ?",
                    n, 1 if n is not None else 0, livre_id, rang)
    if "ecartee" in corps:
        base.ecrire("UPDATE pages SET ecartee = ? WHERE livre_id = ? AND rang = ?", 1 if corps["ecartee"] else 0, livre_id, rang)
    if "rendu" in corps:   # « image » : la page entre en image dans le livre ; « auto » : en texte dès qu'elle est lue
        if corps["rendu"] not in ("auto", "image"):
            raise HTTPException(422, "Rendu « auto » ou « image ».")
        base.ecrire("UPDATE pages SET rendu_choisi = ? WHERE livre_id = ? AND rang = ?", corps["rendu"], livre_id, rang)
    return _vue(_livre(livre_id), avec_pages=True)


def _page(livre_id: int, rang: int) -> dict:
    page = ETAT["base"].un("SELECT * FROM pages WHERE livre_id = ? AND rang = ?", livre_id, rang)
    if not page:
        raise HTTPException(404, "Page inconnue.")
    return page


@app.put("/api/livres/{livre_id}/pages/ajouter")
async def ajouter_page(livre_id: int, numero: int, request: Request):
    """Page reprise à l'iPhone (une page manquante du PDF) : la photo est remise droite, recadrée, puis insérée
    à sa place d'après son numéro imprimé. Elle attend ensuite sa lecture comme les autres."""
    livre_ = _livre(livre_id)
    if livre_["etat"] not in ("inventaire", "lecture", "pret"):
        raise HTTPException(409, "Les pages du livre ne sont pas encore découpées.")
    if not 0 < numero < 10000:
        raise HTTPException(422, "Numéro de page entre 1 et 9999.")
    contenu = await request.body()
    if not contenu or len(contenu) > 40 * 10**6:
        raise HTTPException(422, "Photo absente ou trop lourde (40 Mo au plus).")
    try:
        jpeg = capture.preparer_photo(contenu)
    except ValueError as e:
        raise HTTPException(422, f"Photo illisible : {e}") from e
    base: Base = ETAT["base"]
    pages = base.lire("SELECT rang, ordre, numero, ecartee FROM pages WHERE livre_id = ? ORDER BY ordre", livre_id)
    rang = max((p["rang"] for p in pages), default=0) + 1
    ordre = _place(pages, numero)
    (base.dossier(livre_id) / "pages").mkdir(parents=True, exist_ok=True)
    (base.dossier(livre_id) / "pages" / f"{rang:04d}.jpg").write_bytes(jpeg)
    base.ecrire("INSERT INTO pages (livre_id, rang, ordre, source, numero, numero_manuel) VALUES (?, ?, ?, 'photo', ?, 1)",
                livre_id, rang, ordre, numero)
    if livre_["etat"] == "pret":   # une page à lire : le livre n'est plus « prêt »
        base.ecrire("UPDATE livres SET etat = 'lecture' WHERE id = ?", livre_id)
    return {**_vue(_livre(livre_id), avec_pages=True), "ajoutee": rang}


def _place(pages: list[dict], numero: int) -> float:
    """Place (ordre) d'une page de numéro donné : juste après la dernière page de numéro inférieur et les pages
    sans numéro qui la suivent (photos pleine page), avant la page de numéro supérieur."""
    numerotees = [p for p in pages if p["numero"] is not None and not p["ecartee"]]
    avant = [p for p in numerotees if p["numero"] < numero]
    apres = [p for p in numerotees if p["numero"] > numero]
    if avant:
        precedente = max(avant, key=lambda p: (p["numero"], p["ordre"]))
        suivantes = [p for p in pages if p["ordre"] > precedente["ordre"]]
        borne = min((p["ordre"] for p in apres if p["ordre"] > precedente["ordre"]), default=None)
        # Les pages sans numéro qui suivent la précédente (avant la borne) restent avec elle
        apres_sans = [p for p in suivantes if p["numero"] is None and (borne is None or p["ordre"] < borne)]
        depart = max([precedente["ordre"]] + [p["ordre"] for p in apres_sans])
        fin = min((p["ordre"] for p in pages if p["ordre"] > depart), default=depart + 2)
        return (depart + fin) / 2
    if apres:
        suivante = min(apres, key=lambda p: p["ordre"])
        debut = max((p["ordre"] for p in pages if p["ordre"] < suivante["ordre"]), default=suivante["ordre"] - 2)
        return (debut + suivante["ordre"]) / 2
    return max((p["ordre"] for p in pages), default=0) + 1


@app.post("/api/livres/{livre_id}/pages/{rang}/texte")
def enregistrer_texte(livre_id: int, rang: int, corps: dict = Body(...)):
    """Texte corrigé à la relecture : il remplace celui de Mistral, et une nouvelle lecture ne l'écrase plus."""
    _livre(livre_id)
    _page(livre_id, rang)
    texte = str(corps.get("markdown", ""))
    if len(texte) > 200_000:
        raise HTTPException(413, "Texte trop long pour une page.")
    lu = ETAT["base"].dossier(livre_id) / "lu"
    lu.mkdir(parents=True, exist_ok=True)
    (lu / f"{rang:04d}.md").write_text(texte, encoding="utf-8")
    ETAT["base"].ecrire("UPDATE pages SET lecture = 'faite', lecture_erreur = '', texte_main = 1, relue = 1 "
                        "WHERE livre_id = ? AND rang = ?", livre_id, rang)
    contre.comparer_page(ETAT["base"], livre_id, rang)
    return _vue(_livre(livre_id), avec_pages=True)


@app.post("/api/livres/{livre_id}/pages/{rang}/relue")
def marquer_relue(livre_id: int, rang: int, corps: dict = Body(default={})):
    """« Page relue » : ses mots à relire ne sont plus comptés (le texte de Mistral est gardé tel quel)."""
    _livre(livre_id)
    _page(livre_id, rang)
    ETAT["base"].ecrire("UPDATE pages SET relue = ? WHERE livre_id = ? AND rang = ?",
                        0 if corps.get("relue") is False else 1, livre_id, rang)
    return _vue(_livre(livre_id), avec_pages=True)


@app.post("/api/livres/{livre_id}/pages/{rang}/relire")
def relire_page(livre_id: int, rang: int):
    """Fait relire cette page seule par Mistral (le texte corrigé à la main est alors abandonné)."""
    _livre(livre_id)
    _page(livre_id, rang)
    if not ETAT["cfg"].mistral_cle:
        raise HTTPException(409, "Aucune clé Mistral dans la stack (SCRIPTORIUM_MISTRAL_CLE).")
    exiger_ecriture("envoyé à Mistral")
    base: Base = ETAT["base"]
    base.ecrire("UPDATE pages SET lecture = 'attente', lecture_erreur = '', texte_main = 0, relue = 0, ecartee = 0 "
                "WHERE livre_id = ? AND rang = ?", livre_id, rang)
    base.ecrire("UPDATE livres SET etat = 'lecture', lecture_demandee = 1, erreur = '' WHERE id = ?", livre_id)
    return _vue(_livre(livre_id), avec_pages=True)


@app.post("/api/livres/{livre_id}/pages/{rang}/tourner")
def tourner_page(livre_id: int, rang: int):
    """Tourne l'image d'un quart de tour (photo prise de travers). Une page déjà lue repasse « à lire »."""
    _livre(livre_id)
    page = _page(livre_id, rang)
    chemin = ETAT["base"].dossier(livre_id) / "pages" / f"{rang:04d}.jpg"
    if not chemin.is_file():
        raise HTTPException(404, "Image de la page absente.")
    capture.tourner(chemin, 90)
    if page["lecture"] != "attente" and not page["texte_main"]:
        ETAT["base"].ecrire("UPDATE pages SET lecture = 'attente' WHERE id = ?", page["id"])
    # L'image a changé : la contre-lecture est à refaire
    lu = ETAT["base"].dossier(livre_id) / "lu"
    for f in (lu / f"{rang:04d}.marker.md", lu / f"{rang:04d}.doutes.json"):
        f.unlink(missing_ok=True)
    ETAT["base"].ecrire("UPDATE pages SET contre = 'attente', doutes = 0, accord = NULL WHERE id = ?", page["id"])
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
    ETAT["base"].ecrire("UPDATE livres SET inventaire_confirme = 1 WHERE id = ?", livre_id)
    return _vue(_livre(livre_id), avec_pages=True)


# ---------------------------------------------------------------- lecture par Mistral

@app.post("/api/livres/{livre_id}/lecture")
def lancer_lecture(livre_id: int):
    """Envoie à Mistral toutes les pages pas encore lues (0.2.2 : sans attendre l'inventaire, car Mistral
    repère aussi le numéro imprimé de chaque page ; l'inventaire se confirme ensuite)."""
    livre_ = _livre(livre_id)
    if livre_["etat"] not in ("inventaire", "lecture", "pret"):
        raise HTTPException(409, "Les pages ne sont pas encore découpées.")
    if not ETAT["cfg"].mistral_cle:
        raise HTTPException(409, "Aucune clé Mistral dans la stack (SCRIPTORIUM_MISTRAL_CLE).")
    exiger_ecriture("envoyé à Mistral")
    ETAT["base"].ecrire("UPDATE livres SET etat = 'lecture', lecture_demandee = 1, erreur = '' WHERE id = ?", livre_id)
    return _vue(_livre(livre_id))


# ---------------------------------------------------------------- fabrication et dépôt

@app.post("/api/livres/{livre_id}/fabriquer")
def fabriquer(livre_id: int, partiel: bool = False):
    """Fabrique l'EPUB et le PDF d'archive. « partiel » : un EPUB d'essai avec les seules pages déjà lues,
    pour voir le rendu pendant la lecture ; il n'est jamais déposé dans Grimmory."""
    livre_ = _livre(livre_id)
    if livre_["etat"] not in ("inventaire", "lecture", "pret"):
        raise HTTPException(409, "Les pages ne sont pas encore découpées.")
    base: Base = ETAT["base"]
    filtre = "AND lecture IN ('faite', 'douteuse')" if partiel else ""
    pages = base.lire(f"SELECT * FROM pages WHERE livre_id = ? AND ecartee = 0 {filtre} ORDER BY ordre", livre_id)
    if not pages:
        raise HTTPException(409, "Aucune page lue pour l'instant." if partiel else "Aucune page à mettre dans le livre.")
    dossier = base.dossier(livre_id)
    nom = fabrication.nom_fichier(livre_["auteur"], livre_["titre"])
    if partiel:
        bilan = fabrication.fabriquer_epub(dossier, livre_, pages, dossier / "sortie" / f"{nom} (essai).epub")
        return {**_vue(_livre(livre_id)), "fabrication": bilan, "essai": f"{nom} (essai).epub"}
    bilan = fabrication.fabriquer_epub(dossier, livre_, pages, dossier / "sortie" / f"{nom}.epub")
    fabrication.fabriquer_archive(dossier, pages, dossier / "sortie" / f"{nom} - pages.pdf")
    base.ecrire("UPDATE livres SET epub = ?, archive = ? WHERE id = ?", f"{nom}.epub", f"{nom} - pages.pdf", livre_id)
    return {**_vue(_livre(livre_id)), "fabrication": bilan}


@app.post("/api/livres/{livre_id}/pdf")
def demander_pdf(livre_id: int):
    """PDF A5 soigné, fabriqué en tâche de fond (quelques minutes pour un gros livre)."""
    livre_ = _livre(livre_id)
    if livre_["etat"] not in ("inventaire", "lecture", "pret"):
        raise HTTPException(409, "Les pages ne sont pas encore découpées.")
    ETAT["base"].ecrire("UPDATE livres SET pdf_demande = 1, pdf_erreur = '' WHERE id = ?", livre_id)
    return _vue(_livre(livre_id), avec_pages=True)


@app.get("/api/livres/{livre_id}/telecharger/{quoi}")
def telecharger(livre_id: int, quoi: str):
    livre_ = _livre(livre_id)
    essai = f"{fabrication.nom_fichier(livre_['auteur'], livre_['titre'])} (essai).epub"
    nom = {"epub": livre_["epub"], "archive": livre_["archive"], "essai": essai, "pdf": livre_["pdf"]}.get(quoi)
    chemin = ETAT["base"].dossier(livre_id) / "sortie" / (nom or "")
    if not nom or not chemin.is_file():
        raise HTTPException(404, "Livre pas encore fabriqué.")
    media = "application/pdf" if quoi in ("archive", "pdf") else "application/epub+zip"
    return FileResponse(chemin, media_type=media, filename=nom)


@app.post("/api/livres/{livre_id}/deposer")
def deposer(livre_id: int):
    """Dépose l'EPUB dans le bookdrop de Grimmory. Seulement l'EPUB : un PDF du même livre créerait une
    seconde fiche dans la bibliothèque. Jamais par-dessus un fichier existant."""
    livre_ = _livre(livre_id)
    source = ETAT["base"].dossier(livre_id) / "sortie" / (livre_["epub"] or "")
    if not livre_["epub"] or not source.is_file():
        raise HTTPException(409, "Fabrique d'abord le livre.")
    if not livre_["inventaire_confirme"]:
        raise HTTPException(409, "Confirme d'abord l'inventaire des pages : le livre déposé doit être complet ou accepté tel quel.")
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


# ================================================================ porte du PC de calcul (contre-lecture)

def _jeton_pc(request: Request) -> None:
    attendu = ETAT["cfg"].jeton_calcul
    if not attendu:
        raise HTTPException(404, "Porte du PC de calcul fermée (SCRIPTORIUM_JETON_CALCUL vide).")
    donne = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    if not hmac.compare_digest(donne.encode(), attendu.encode()):
        raise HTTPException(401, "Jeton du PC de calcul refusé.")
    contre.signaler_passage(ETAT["base"], request.headers.get("x-moteur", ""))


@app.get("/calcul/travail")
def calcul_travail(request: Request):
    """Le PC demande une page à relire. 204 : rien à faire, il repassera."""
    _jeton_pc(request)
    page = contre.prochaine_page(ETAT["base"])
    if not page:
        return Response(status_code=204)
    return {"livre_id": page["livre_id"], "rang": page["rang"], "langue": page["langue"],
            "image": f"/calcul/pages/{page['livre_id']}/{page['rang']}.jpg"}


@app.get("/calcul/pages/{livre_id}/{rang}.jpg")
def calcul_image(livre_id: int, rang: int, request: Request):
    _jeton_pc(request)
    chemin = ETAT["base"].dossier(livre_id) / "pages" / f"{rang:04d}.jpg"
    if not chemin.is_file():
        raise HTTPException(404, "Page inconnue.")
    return FileResponse(chemin, media_type="image/jpeg")


@app.post("/calcul/pages/{livre_id}/{rang}")
def calcul_rendu(livre_id: int, rang: int, request: Request, corps: dict = Body(...)):
    """Le PC rend sa lecture : {"markdown": "..."} ou {"erreur": "..."}."""
    _jeton_pc(request)
    markdown = corps.get("markdown")
    if markdown is not None and (not isinstance(markdown, str) or len(markdown) > 400_000):
        raise HTTPException(422, "Texte absent ou trop long.")
    contre.enregistrer(ETAT["base"], livre_id, rang, markdown, str(corps.get("erreur") or ""))
    return {"ok": True}


# ================================================================ services, réglages

@app.get("/api/services")
def services():
    cfg: Config = ETAT["cfg"]
    disque = shutil.disk_usage(cfg.data)
    return {
        "lecture_seule": cfg.lecture_seule,
        "mistral": {"cle": bool(cfg.mistral_cle), "modele": cfg.mistral_modele, "prix_page": cfg.prix_page,
                    "facturees": ETAT["base"].un("SELECT COALESCE(SUM(pages_facturees), 0) AS n FROM pages")["n"]},
        "pc": {"configure": bool(cfg.jeton_calcul), "vu_le": ETAT["base"].memo("pc_vu_le"),
               "moteur": ETAT["base"].memo("pc_moteur"), "en_attente": contre.pages_en_attente(ETAT["base"])},
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
