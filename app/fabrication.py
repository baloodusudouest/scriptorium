"""Fabrication du livre : EPUB recomposé à partir du texte lu, et PDF d'archive des images de pages.

EPUB recomposé, pensé aussi pour Comptoir (l'appli des cocktails, qui découpe un EPUB en recettes : un titre,
la liste des ingrédients, la préparation) :
- les pages, dans l'ordre du PDF et sans les écartées, sont regroupées en fichiers qui commencent à un titre :
  une recette qui passe d'une page à l'autre n'est jamais coupée en deux fichiers ;
- chaque page porte son repère du livre papier (« p. 72 », et la liste des pages EPUB 3) ;
- les lignes d'ingrédients (« 45 ml de tequila », « 1 trait de bitters ») deviennent une vraie liste ;
- les lignes qui ne sont qu'un numéro de page ou une lettre de marge sont retirées ;
- les illustrations découpées par Mistral sont replacées où il les a mises ;
- une page que Mistral a rendue de façon douteuse, ou pas lue, entre dans le livre en image ;
- la table des matières suit les titres de premier niveau.
"""
from __future__ import annotations

import html
import re
import uuid
from pathlib import Path

import markdown as md_lib
from ebooklib import epub

CSS = """
body { font-family: serif; line-height: 1.45; margin: 0 0.4em; }
h1 { font-size: 1.35em; margin: 1.2em 0 0.4em; line-height: 1.2; }
h2 { font-size: 1.15em; margin: 1em 0 0.3em; }
h3 { font-size: 1.05em; margin: 0.8em 0 0.2em; }
p { margin: 0 0 0.6em; text-align: left; }
img { max-width: 100%; height: auto; }
figure, .page-image { margin: 0.8em 0; text-align: center; }
blockquote { margin: 0.8em 0; padding: 0.4em 0.8em; border-left: 3px solid #999; }
table { border-collapse: collapse; margin: 0.6em 0; font-size: 0.9em; }
td, th { border: 1px solid #999; padding: 0.15em 0.4em; vertical-align: top; }
.page-image img { width: 100%; }
.page-originale { font-family: sans-serif; font-size: 0.7em; color: #888; text-align: right; margin: 0.4em 0 0.6em; }
"""

_LIGNE_PARASITE = re.compile(r"^\s*(\d{1,4}|[A-Z])\s*$")
_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")


def nom_fichier(auteur: str, titre: str) -> str:
    brut = f"{auteur} - {titre}" if auteur.strip() else titre
    propre = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", "", brut).strip().strip(".")
    return re.sub(r"\s+", " ", propre)[:150] or "Livre"


_INGREDIENT = re.compile(
    r"^\s*(?:compl[ée]t(?:er|ez|e)\s+(?:avec|de|à|au)\b|"
    r"(?:\d+(?:[.,]\d+)?(?:\s*(?:-|–|/|à)\s*\d+(?:[.,]\d+)?)?|½|¼|¾|1/2|1/4|une?|deux|trois|quatre|quelques)\s+"
    r"(?:ml|cl|dl|l|g|kg|oz|traits?|gouttes?|cuill[eè]res?|c\.|zestes?|feuilles?|tranches?|rondelles?|pinc[ée]es?|"
    r"quartiers?|brins?|morceaux?|doses?|barspoons?|dash(?:es)?|parts?|bâtons?|branches?|tiges?|gousses?|"
    r"cubes?|boules?|pointes?|verres?|tasses?|fruits?|citrons?|oranges?|œufs?|oeufs?|blancs?|jaunes?)\b)",
    re.IGNORECASE)


def lister_ingredients(texte: str) -> str:
    """Les paragraphes faits de lignes d'ingrédients qui se suivent deviennent une seule liste Markdown."""
    blocs = re.split(r"\n\s*\n", texte)
    sortie: list[str] = []
    liste: list[str] = []
    for bloc in blocs:
        lignes = [l.strip() for l in bloc.strip().splitlines() if l.strip()]
        if lignes and all(_INGREDIENT.match(l) and not l.startswith(("#", "-", "*", "|", ">")) for l in lignes):
            liste.extend(lignes)
            continue
        if liste:
            sortie.append("\n".join(f"- {l}" for l in liste))
            liste = []
        sortie.append(bloc.strip())
    if liste:
        sortie.append("\n".join(f"- {l}" for l in liste))
    return "\n\n".join(b for b in sortie if b)


def nettoyer(markdown_page: str, rang: int, images_connues: set[str]) -> str:
    """Retire numéros de page et lettres de marge, met les ingrédients en liste, renomme les illustrations
    de la page (p0001-img-0.jpeg)."""
    lignes = [l for l in markdown_page.splitlines() if not _LIGNE_PARASITE.match(l)]
    texte = lister_ingredients("\n".join(lignes))

    def image(m: re.Match) -> str:
        nom = f"p{rang:04d}-{Path(m.group(2)).name}"
        return f"![{m.group(1)}](images/{nom})" if nom in images_connues else ""

    return _IMAGE.sub(image, texte).strip()


def composer(dossier: Path, pages: list[dict]) -> dict:
    """Met les pages en HTML, regroupées en fichiers qui commencent à un titre. Sert à l'EPUB et au PDF A5.

    Renvoie {"fichiers": [{"nom", "titre", "corps": [...]}], "sommaire": [(fichier, ancre, titre)],
    "liste_pages": [(fichier#ancre, numéro)], "images": {chemin dans le livre: fichier sur le disque},
    "en_image": n}. Les chemins d'images sont « images/... » dans le HTML.
    """
    lu = dossier / "lu"
    images_dir = lu / "images"
    images_connues = {p.name for p in images_dir.glob("*")} if images_dir.exists() else set()
    fichiers: list[dict] = []
    sommaire: list[tuple[str, str, str]] = []
    liste_pages: list[tuple[str, str]] = []
    images: dict[str, Path] = {}
    pages_vues: set[int] = set()
    en_image = 0
    for p in pages:
        rang = p["rang"]
        md_fichier = lu / f"{rang:04d}.md"
        commence_par_titre = False
        if p["lecture"] == "faite" and md_fichier.exists() and p.get("rendu_choisi", "auto") != "image":
            texte = nettoyer(md_fichier.read_text(encoding="utf-8"), rang, images_connues)
            commence_par_titre = texte.lstrip().startswith("#")
            corps = md_lib.markdown(texte, extensions=["tables", "footnotes", "toc", "sane_lists"], output_format="xhtml")
            # Identifiants propres à la page : plusieurs pages partagent un fichier
            corps = re.sub(r'(id|href)="(#?)([^"#/:]+)"', lambda m: f'{m.group(1)}="{m.group(2)}p{rang}-{m.group(3)}"'
                           if m.group(1) == "id" or m.group(2) else m.group(0), corps)
            for nom in re.findall(r'src="images/([^"]+)"', corps):
                images[f"images/{nom}"] = images_dir / nom
        else:
            # Page douteuse, non lue ou « gardée en image » : elle entre en image, le livre reste complet.
            nom = f"page-{rang:04d}.jpg"
            corps = f'<div class="page-image"><img src="images/{nom}" alt="Page {html.escape(str(p.get("numero") or rang))}"/></div>'
            images[f"images/{nom}"] = dossier / "pages" / f"{rang:04d}.jpg"
            en_image += 1
        if not fichiers or commence_par_titre:
            fichiers.append({"nom": f"p{rang:04d}.xhtml", "titre": f"Page {p.get('numero') or rang}", "corps": []})
        courant = fichiers[-1]
        numero = p.get("numero")
        if numero is not None:
            # Page du livre papier : repère discret dans le texte, et entrée de la liste des pages (page-list)
            # que les liseuses (KOReader) utilisent pour afficher les numéros de l'original. Comptoir s'en sert
            # pour retrouver la page d'origine d'une recette.
            ancre = f"page-{numero}" if numero not in pages_vues else f"page-{numero}-{rang}"
            pages_vues.add(numero)
            corps = (f'<span epub:type="pagebreak" role="doc-pagebreak" id="{ancre}" title="{numero}"></span>'
                     f'<p class="page-originale">p. {numero}</p>{corps}')
            liste_pages.append((f"{courant['nom']}#{ancre}", str(numero)))
        courant["corps"].append(corps)
        for ancre, titre in re.findall(r'<h1 id="([^"]+)">(.*?)</h1>', corps, flags=re.S):
            titre_net = html.unescape(re.sub(r"<[^>]+>", "", titre).strip())
            if titre_net and len(sommaire) < 400:
                sommaire.append((courant["nom"], ancre, titre_net))
    return {"fichiers": fichiers, "sommaire": sommaire, "liste_pages": liste_pages, "images": images, "en_image": en_image}


def image_de_couverture(dossier: Path, livre: dict, pages: list[dict], cote: int = 1600) -> bytes | None:
    """La page choisie comme couverture (sinon la première page gardée), réduite pour la liseuse."""
    import io

    from PIL import Image

    rang = livre.get("couverture") or (pages[0]["rang"] if pages else None)
    chemin = dossier / "pages" / f"{rang:04d}.jpg" if rang else None
    if not chemin or not chemin.is_file():
        return None
    with Image.open(chemin) as im:
        im.thumbnail((cote, cote))
        t = io.BytesIO()
        im.convert("RGB").save(t, "JPEG", quality=85)
    return t.getvalue()


def fabriquer_epub(dossier: Path, livre: dict, pages: list[dict], sortie: Path) -> dict:
    """pages : lignes de la table pages, déjà triées et sans les écartées. Renvoie un petit bilan."""
    c = composer(dossier, pages)
    livre_epub = epub.EpubBook()
    livre_epub.set_identifier(f"scriptorium-{livre['id']}-{uuid.uuid4().hex[:8]}")
    livre_epub.set_title(livre["titre"])
    livre_epub.set_language(livre.get("langue") or "fr")
    if livre.get("auteur"):
        for auteur in [a.strip() for a in livre["auteur"].split(",") if a.strip()]:
            livre_epub.add_author(auteur)
    # Fiche (0.4.0) : Grimmory et les liseuses lisent l'ISBN, l'éditeur et l'année
    if livre.get("isbn"):
        livre_epub.add_metadata("DC", "identifier", f"urn:isbn:{livre['isbn']}", {"id": "isbn"})
    if livre.get("editeur"):
        livre_epub.add_metadata("DC", "publisher", livre["editeur"])
    if livre.get("annee"):
        livre_epub.add_metadata("DC", "date", livre["annee"])
    livre_epub.add_metadata("DC", "source", "Recomposé par Scriptorium à partir d'un livre scanné")
    couverture = image_de_couverture(dossier, livre, pages)
    if couverture:
        livre_epub.set_cover("couverture.jpg", couverture, create_page=False)
    style = epub.EpubItem(uid="style", file_name="style.css", media_type="text/css", content=CSS)
    livre_epub.add_item(style)

    sections = []
    for f in c["fichiers"]:
        section = epub.EpubHtml(title=f["titre"], file_name=f["nom"], lang=livre.get("langue") or "fr")
        section.content = "".join(f["corps"]) or "<p></p>"
        section.add_item(style)
        livre_epub.add_item(section)
        sections.append(section)
    for i, (chemin_livre, fichier) in enumerate(sorted(c["images"].items())):
        if fichier.is_file():
            type_ = "image/png" if fichier.suffix.lower() == ".png" else "image/jpeg"
            livre_epub.add_item(epub.EpubImage(uid=f"img{i}", file_name=chemin_livre, media_type=type_, content=fichier.read_bytes()))
    sommaire = [epub.Link(f"{nom}#{ancre}", titre, f"t-{ancre}") for nom, ancre, titre in c["sommaire"]]
    livre_epub.toc = sommaire or ([epub.Link(sections[0].file_name, livre["titre"], "debut")] if sections else [])
    livre_epub.add_item(epub.EpubNcx())
    livre_epub.add_item(epub.EpubNav())
    livre_epub.spine = ["nav", *sections]
    sortie.parent.mkdir(parents=True, exist_ok=True)
    epub.write_epub(str(sortie), livre_epub)
    if c["liste_pages"]:
        ajouter_liste_des_pages(sortie, c["liste_pages"])
    return {"sections": len(sections), "pages": len(pages), "pages_en_image": c["en_image"], "titres": len(sommaire),
            "pages_originales": len(c["liste_pages"]), "couverture": bool(couverture)}


def ajouter_liste_des_pages(chemin: Path, liste: list[tuple[str, str]]) -> None:
    """Ajoute la liste des pages du livre papier (nav epub:type="page-list") au fichier de navigation.
    EbookLib ne sait pas l'écrire : on réécrit l'archive en gardant « mimetype » en tête, non compressé."""
    import zipfile

    entrees = "".join(f'<li><a href="{html.escape(h)}">{html.escape(t)}</a></li>' for h, t in liste)
    bloc = f'<nav epub:type="page-list" id="page-list" hidden=""><h2>Pages</h2><ol>{entrees}</ol></nav>'
    tmp = chemin.with_suffix(".tmp")
    with zipfile.ZipFile(chemin) as src, zipfile.ZipFile(tmp, "w") as dst:
        for info in src.infolist():
            donnees = src.read(info.filename)
            if info.filename.endswith("nav.xhtml"):
                texte = donnees.decode("utf-8")
                if 'xmlns:epub=' not in texte:
                    texte = texte.replace("<html ", '<html xmlns:epub="http://www.idpf.org/2007/ops" ', 1)
                donnees = texte.replace("</body>", bloc + "</body>", 1).encode("utf-8")
            compression = zipfile.ZIP_STORED if info.filename == "mimetype" else zipfile.ZIP_DEFLATED
            dst.writestr(info, donnees, compress_type=compression)
    tmp.replace(chemin)


def fabriquer_archive(dossier: Path, pages: list[dict], sortie: Path) -> None:
    """PDF des images de pages, dans l'ordre, sans les écartées : l'archive fidèle du livre."""
    import img2pdf

    fichiers = [str(dossier / "pages" / f"{p['rang']:04d}.jpg") for p in pages]
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_bytes(img2pdf.convert(fichiers))
