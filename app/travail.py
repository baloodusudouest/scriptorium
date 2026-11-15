"""Tâches de fond : découpe d'un PDF importé (et lecture des numéros), puis lecture des pages par Mistral.

Une seule tâche tourne à la fois, dans un fil à part ; l'interface lit l'avancement dans la base.
Un redémarrage reprend où l'on en était : une page déjà découpée ou déjà lue n'est pas refaite.
"""
from __future__ import annotations

import logging
import shutil
import threading
import time
from pathlib import Path

from PIL import Image

from . import contre, inventaire, mistral
from .base import Base

log = logging.getLogger("scriptorium.travail")


class Travail:
    def __init__(self, base: Base, cfg):
        self.base = base
        self.cfg = cfg
        self._arret = threading.Event()
        self._fil: threading.Thread | None = None
        self.en_cours = ""      # ce qui tourne, pour l'écran Connexion

    # ------------------------------------------------------------ fil
    def demarrer(self) -> None:
        self._fil = threading.Thread(target=self._boucle, name="travail", daemon=True)
        self._fil.start()

    def arreter(self) -> None:
        self._arret.set()

    def _boucle(self) -> None:
        while not self._arret.is_set():
            try:
                fait = self.une_tache()
            except Exception:  # noqa: BLE001 — une panne ne doit pas tuer le fil
                log.exception("tâche de fond en échec")
                fait = False
            self._arret.wait(0.5 if fait else 3)

    def une_tache(self) -> bool:
        """Fait la prochaine tâche en attente ; renvoie False s'il n'y avait rien."""
        livre = self.base.un("SELECT * FROM livres WHERE etat = 'decoupe' ORDER BY id LIMIT 1")
        if livre:
            self.decouper(livre["id"])
            return True
        livre = self.base.un("SELECT * FROM livres WHERE etat = 'lecture' AND lecture_demandee = 1 ORDER BY id LIMIT 1")
        if livre:
            self.lire(livre["id"])
            return True
        return False

    def tout_faire(self) -> None:
        """Pour les tests : enchaîne les tâches jusqu'à ce qu'il n'y en ait plus."""
        while self.une_tache():
            pass

    # ------------------------------------------------------------ découpe
    def decouper(self, livre_id: int) -> None:
        import pypdfium2 as pdfium

        dossier = self.base.dossier(livre_id)
        pages_dir = dossier / "pages"
        pages_dir.mkdir(parents=True, exist_ok=True)
        self.en_cours = f"découpe du livre {livre_id}"
        try:
            pdf = pdfium.PdfDocument(str(dossier / "source.pdf"))
        except Exception as e:  # noqa: BLE001
            self._erreur(livre_id, f"PDF illisible : {e}")
            return
        try:
            total = len(pdf)
            deja = {r["rang"] for r in self.base.lire("SELECT rang FROM pages WHERE livre_id = ?", livre_id)}
            relire = bool(self.base.un("SELECT relire FROM livres WHERE id = ?", livre_id)["relire"])
            for i in range(total):
                rang = i + 1
                image = pages_dir / f"{rang:04d}.jpg"
                if rang in deja and image.exists():
                    if relire:   # page déjà découpée : on ne relit que son numéro (la mise à l'écart est gardée)
                        with Image.open(image) as img:
                            numero = inventaire.lire_numero(img.convert("RGB"))
                        self.base.ecrire("UPDATE pages SET numero_lu = ?, numero = ? WHERE livre_id = ? AND rang = ?",
                                         numero, numero, livre_id, rang)
                        self.base.ecrire("UPDATE livres SET avancement = ? WHERE id = ?", int(100 * rang / total), livre_id)
                    continue
                img = pdf[i].render(scale=self.cfg.dpi / 72).to_pil().convert("RGB")
                img.save(image, "JPEG", quality=88)
                numero = inventaire.lire_numero(img)
                self.base.ecrire("INSERT OR REPLACE INTO pages (livre_id, rang, ordre, numero_lu, numero) VALUES (?, ?, ?, ?, ?)",
                                 livre_id, rang, rang, numero, numero)
                self.base.ecrire("UPDATE livres SET avancement = ? WHERE id = ?", int(100 * rang / total), livre_id)
        finally:
            pdf.close()
        # Lectures aberrantes écartées une fois toutes les pages vues
        pages = self.base.lire("SELECT rang, numero_lu FROM pages WHERE livre_id = ? ORDER BY ordre", livre_id)
        corriges = inventaire.corriger([p["numero_lu"] for p in pages])
        self.base.plusieurs("UPDATE pages SET numero = ? WHERE livre_id = ? AND rang = ?",
                            [(n, livre_id, p["rang"]) for p, n in zip(pages, corriges)])
        self.base.ecrire("UPDATE livres SET etat = 'inventaire', avancement = 100, erreur = '', relire = 0 WHERE id = ?", livre_id)
        self.en_cours = ""

    # ------------------------------------------------------------ lecture par Mistral
    def lire(self, livre_id: int) -> None:
        if self.cfg.lecture_seule:   # garde au plus près de l'envoi (la route refuse déjà)
            self.base.ecrire("UPDATE livres SET lecture_demandee = 0, erreur = ? WHERE id = ?",
                             "Mode lecture seule : rien n'est envoyé à Mistral.", livre_id)
            return
        dossier = self.base.dossier(livre_id)
        lu = dossier / "lu"
        (lu / "images").mkdir(parents=True, exist_ok=True)
        pages = self.base.lire("SELECT * FROM pages WHERE livre_id = ? AND ecartee = 0 ORDER BY ordre", livre_id)
        a_lire = [p for p in pages if p["lecture"] in ("attente", "erreur")]
        self.en_cours = f"lecture du livre {livre_id}"
        lues, facturees = 0, 0
        for p in a_lire:
            if self._arret.is_set():
                return
            rang = p["rang"]
            if p["texte_main"]:   # texte corrigé à la relecture : Mistral ne l'écrase pas
                self.base.ecrire("UPDATE pages SET lecture = 'faite' WHERE id = ?", p["id"])
                continue
            try:
                resultat = mistral.lire_page((dossier / "pages" / f"{rang:04d}.jpg").read_bytes(),
                                             self.cfg.mistral_cle, self.cfg.mistral_url, self.cfg.mistral_modele)
            except mistral.ErreurMistral as e:
                self.base.ecrire("UPDATE pages SET lecture = 'erreur', lecture_erreur = ? WHERE id = ?", str(e), p["id"])
                if "401" in str(e) or "429" in str(e) or "aucune clé" in str(e):
                    # Inutile d'insister page après page : on s'arrête et on le dit.
                    self.base.ecrire("UPDATE livres SET lecture_demandee = 0, erreur = ? WHERE id = ?", str(e), livre_id)
                    break
                continue
            (lu / f"{rang:04d}.md").write_text(resultat.markdown, encoding="utf-8")
            for nom, contenu in resultat.images.items():
                (lu / "images" / f"p{rang:04d}-{Path(nom).name}").write_bytes(contenu)
            etat = "douteuse" if resultat.douteuse else "faite"
            self.base.ecrire("UPDATE pages SET lecture = ?, lecture_erreur = ?, numero_mistral = ?, pages_facturees = pages_facturees + ? WHERE id = ?",
                             etat, resultat.douteuse, resultat.numero, resultat.pages_facturees, p["id"])
            if resultat.numero is not None:
                self.base.ecrire("UPDATE pages SET numero = ? WHERE id = ? AND numero_manuel = 0", resultat.numero, p["id"])
            # Nouveau texte : la page est à revoir, et sa contre-lecture (si le PC l'a déjà faite) est comparée
            self.base.ecrire("UPDATE pages SET relue = 0 WHERE id = ?", p["id"])
            contre.comparer_page(self.base, livre_id, rang)
            lues += 1
            facturees += resultat.pages_facturees
            fini = self.base.un("SELECT COUNT(*) AS n FROM pages WHERE livre_id = ? AND ecartee = 0 AND lecture IN ('faite', 'douteuse')", livre_id)["n"]
            self.base.ecrire("UPDATE livres SET avancement = ? WHERE id = ?", int(100 * fini / max(1, len(pages))), livre_id)
        if lues:
            self.base.noter("lecture_mistral", livre_id, f"{lues} page(s) lue(s), {facturees} facturée(s)")
            self.recalculer_numeros(livre_id)
        reste = self.base.un("SELECT COUNT(*) AS n FROM pages WHERE livre_id = ? AND ecartee = 0 AND lecture IN ('attente', 'erreur')", livre_id)["n"]
        if reste == 0:
            self.base.ecrire("UPDATE livres SET etat = 'pret', lecture_demandee = 0, erreur = '' WHERE id = ?", livre_id)
        else:
            livre = self.base.un("SELECT erreur FROM livres WHERE id = ?", livre_id)
            message = livre["erreur"] or f"{reste} page(s) non lue(s) : relancer la lecture."
            self.base.ecrire("UPDATE livres SET lecture_demandee = 0, erreur = ? WHERE id = ?", message, livre_id)
        self.en_cours = ""

    def recalculer_numeros(self, livre_id: int) -> None:
        """Numéro de chaque page : celui corrigé à la main, sinon celui de Mistral, sinon celui de Tesseract ;
        les lectures qui ne suivent pas leurs voisines sont écartées (pente des numéros)."""
        pages = self.base.lire("SELECT id, numero_lu, numero_mistral, numero, numero_manuel FROM pages "
                               "WHERE livre_id = ? ORDER BY ordre", livre_id)
        bruts = [p["numero_mistral"] if p["numero_mistral"] is not None else p["numero_lu"] for p in pages]
        corriges = inventaire.corriger(bruts)
        self.base.plusieurs("UPDATE pages SET numero = ? WHERE id = ? AND numero_manuel = 0",
                            [(n, p["id"]) for p, n in zip(pages, corriges)])

    # ------------------------------------------------------------ outils
    def _erreur(self, livre_id: int, message: str) -> None:
        self.base.ecrire("UPDATE livres SET etat = 'erreur', erreur = ? WHERE id = ?", message, livre_id)
        self.en_cours = ""


def vignette(chemin: Path, cote: int) -> bytes:
    import io

    with Image.open(chemin) as im:
        im.thumbnail((cote, cote))
        t = io.BytesIO()
        im.convert("RGB").save(t, "JPEG", quality=80)
    return t.getvalue()


def supprimer_dossier(dossier: Path) -> None:
    shutil.rmtree(dossier, ignore_errors=True)


def attendre(condition, delai: float = 5.0) -> bool:  # pragma: no cover — aide de débogage
    fin = time.monotonic() + delai
    while time.monotonic() < fin:
        if condition():
            return True
        time.sleep(0.05)
    return False
