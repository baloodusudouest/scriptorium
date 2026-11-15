"""Serveur de démonstration : Scriptorium avec un faux livre déjà importé, découpé et en partie lu.

Sert aux tests d'écran et aux captures. Rien n'est envoyé à Mistral : la lecture est simulée.
Usage : python -m tools.demo [port]   (mot de passe : demo-demo-demo)
"""
from __future__ import annotations

import io
import sys
import tempfile
from pathlib import Path

import uvicorn
from PIL import Image, ImageDraw, ImageFont

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from app import contre, main, mistral  # noqa: E402
from app.config import Config  # noqa: E402

MDP = "demo-demo-demo"


def _police(taille):
    import glob
    polices = glob.glob("/usr/share/fonts/**/DejaVuSerif.ttf", recursive=True)
    return ImageFont.truetype(polices[0], taille) if polices else ImageFont.load_default()


def faux_pdf(numeros) -> bytes:
    corps, chiffres, titre = _police(20), _police(28), _police(44)
    pages = []
    for n in numeros:
        im = Image.new("RGB", (1240, 1754), (250, 248, 243))
        d = ImageDraw.Draw(im)
        d.text((150, 140), f"Recette {n or ''}", font=titre, fill=(40, 30, 25))
        for y in range(240, 1400, 40):
            d.text((150, y), "45 ml de gin, 15 ml de vermouth, un trait de bitters.", font=corps, fill=(40, 40, 40))
        if n is not None:
            d.text((600 if n % 2 else 1050, 1680), str(n), font=chiffres, fill="black")
        pages.append(im)
    t = io.BytesIO()
    pages[0].save(t, "PDF", save_all=True, append_images=pages[1:], resolution=150)
    return t.getvalue()


def preparer(data: Path) -> None:
    """Deux livres : un en inventaire (pages manquantes, double), un lu et prêt."""
    from fastapi.testclient import TestClient

    def lecture(image, cle, url, modele, client=None):
        return mistral.PageLue("# Recette\n\n45 ml de *gin*, 15 ml de vermouth.\n\nUn trait de bitters.", {}, 1, "")

    vraie = mistral.lire_page
    mistral.lire_page = lecture          # remise en place à la fin : les tests du vrai client ne doivent pas la voir
    try:
        _remplir(TestClient, lecture)
    finally:
        mistral.lire_page = vraie


def _remplir(TestClient, lecture) -> None:
    with TestClient(main.app) as c:
        c.post("/api/connexion", json={"mot_de_passe": MDP})
        for titre, auteur, numeros in (("Le grand livre des cocktails", "Auteur Inventé", [None, 1, 2, 3, 6, 7, 8, 8, 9, 10, 11, 12]),
                                       ("Daiquiri et compagnie", "Autre Auteur", [1, 2, 3, 4, 5, 6])):
            contenu = faux_pdf(numeros)
            livre = c.post("/api/livres", json={"titre": titre, "auteur": auteur, "nom_fichier": "livre.pdf", "octets": len(contenu)}).json()
            c.put(f"/api/livres/{livre['id']}/envoi?debut=0", content=contenu)
            c.post(f"/api/livres/{livre['id']}/envoi/fin")
            main.ETAT["travail"].tout_faire()
            if titre.startswith("Daiquiri"):
                c.post(f"/api/livres/{livre['id']}/inventaire/confirmer")
                c.post(f"/api/livres/{livre['id']}/lecture")
                main.ETAT["travail"].tout_faire()
                c.post(f"/api/livres/{livre['id']}/fabriquer")
                # Contre-lecture simulée (le PC) : les pages 5 et 6 ont un mot que Marker lit autrement
                for rang in range(1, 7):
                    texte = "Recette\n45 ml de gin, 15 ml de vermouth.\nUn trait de bitters."
                    if rang >= 5:
                        texte = texte.replace("vermouth", "vermout")
                    contre.enregistrer(main.ETAT["base"], livre["id"], rang, texte)


def lancer(port: int = 8191, data: Path | None = None):
    data = data or Path(tempfile.mkdtemp(prefix="scriptorium-demo-"))
    (data / "bookdrop").mkdir(parents=True, exist_ok=True)
    main.ETAT.clear()
    main.ETAT["cfg"] = Config(password=MDP, data=data / "data", static=RACINE / "app" / "static", attente_connexion=False,
                              travail_auto=False, mistral_cle="demo", bookdrop=data / "bookdrop", dpi=120,
                              jeton_calcul="demo-jeton-du-pc")
    preparer(data)
    main.ETAT["cfg"] = Config(password=MDP, data=data / "data", static=RACINE / "app" / "static", attente_connexion=False,
                              travail_auto=False, mistral_cle="demo", bookdrop=data / "bookdrop", dpi=120,
                              jeton_calcul="demo-jeton-du-pc")
    uvicorn.run(main.app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    lancer(int(sys.argv[1]) if len(sys.argv) > 1 else 8191)
