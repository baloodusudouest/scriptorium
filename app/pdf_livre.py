"""PDF A5 soigné (0.4.0) : le livre recomposé, mis en page pour être lu à l'écran ou imprimé.

Même texte que l'EPUB (fabrication.composer), composé par WeasyPrint :
- format A5, marges de livre (plus larges côté reliure), EB Garamond (fichiers dans app/polices, licence OFL) ;
- couverture (la page choisie, pleine page), page de titre, sommaire avec numéros de page, colophon ;
- titre courant en haut de page, numéro en bas ; le numéro de la page du livre papier en marge (« p. 72 ») ;
- une page gardée en image occupe sa propre page ;
- un titre ne reste jamais seul en bas de page, une liste d'ingrédients n'est pas coupée.

Fabriqué en tâche de fond : un livre de 300 pages prend quelques minutes sur le NAS.
"""
from __future__ import annotations

import html
import re
from datetime import date
from pathlib import Path

from . import fabrication

POLICES = Path(__file__).parent / "polices"


def _css() -> str:
    faces = "".join(
        f'@font-face {{ font-family: "Livre"; font-weight: {poids}; font-style: {style}; '
        f'src: url("{(POLICES / f"eb-garamond-latin-{poids}-{style}.woff2").as_uri()}"); }}\n'
        for poids in (400, 600) for style in ("normal", "italic"))
    return faces + """
@page {
  size: A5;
  margin: 17mm 14mm 19mm 18mm;
  @top-center { content: string(courant); font: italic 8.5pt "Livre", serif; color: #6b6259; }
  @bottom-center { content: counter(page); font: 9pt "Livre", serif; color: #3a332c; }
}
@page :left { margin-left: 14mm; margin-right: 18mm; }
@page couverture { margin: 0; @top-center { content: none; } @bottom-center { content: none; } }
@page liminaire { @top-center { content: none; } @bottom-center { content: none; } }
@page plein { margin: 10mm; @top-center { content: none; } }

html { font-family: "Livre", Georgia, serif; font-size: 10.5pt; line-height: 1.42; color: #1d1915;
       hyphens: auto; text-align: justify; }
.couverture { page: couverture; height: 210mm; width: 148mm; margin: 0; break-after: page; }
.couverture img { width: 148mm; height: 210mm; object-fit: cover; display: block; }
.titre-livre { page: liminaire; break-after: page; text-align: center; padding-top: 45mm; }
.titre-livre h1 { font-size: 22pt; font-weight: 400; line-height: 1.15; margin: 0 0 6mm; }
.titre-livre .auteur { font-size: 13pt; font-style: italic; margin: 0 0 30mm; }
.titre-livre .edition { font-size: 9.5pt; color: #6b6259; }
.sommaire { page: liminaire; break-after: page; }
.sommaire h2 { font-size: 14pt; font-weight: 400; text-align: center; margin: 0 0 6mm; }
.sommaire ul { list-style: none; padding: 0; margin: 0; }
.sommaire li { text-align: left; margin: 0 0 1.2mm; font-size: 9.5pt; }
.sommaire a { color: inherit; text-decoration: none; }
.sommaire a::after { content: leader(".") target-counter(attr(href), page); }

main h1, main h2, main h3 { text-align: left; hyphens: manual; break-after: avoid; line-height: 1.2; font-weight: 600; }
main h1 { font-size: 15pt; margin: 7mm 0 2.5mm; string-set: courant content(); }
main h2 { font-size: 12.5pt; margin: 5mm 0 2mm; }
main h3 { font-size: 11pt; margin: 4mm 0 1.5mm; }
main p { margin: 0 0 2mm; orphans: 2; widows: 2; }
main ul, main ol { margin: 0 0 2.5mm; padding-left: 5mm; text-align: left; break-inside: avoid; }
main li { margin: 0 0 0.6mm; }
main em { font-style: italic; }
main blockquote { margin: 3mm 0; padding: 1mm 0 1mm 4mm; border-left: 0.6pt solid #a39684; font-style: italic; }
main table { border-collapse: collapse; margin: 2mm 0 3mm; font-size: 9pt; break-inside: avoid; }
main td, main th { border: 0.4pt solid #a39684; padding: 0.6mm 1.6mm; vertical-align: top; text-align: left; }
main img { max-width: 100%; max-height: 120mm; display: block; margin: 2mm auto; break-inside: avoid; }
main .page-originale { float: right; margin: 0 -11mm 0 2mm; width: 10mm; text-align: right; font-size: 7pt;
                       color: #8a7f72; font-family: sans-serif; line-height: 1; }
main .page-image { page: plein; break-before: page; break-after: page; text-align: center; }
main .page-image img { max-height: 188mm; max-width: 128mm; margin: 0 auto; }
.colophon { page: liminaire; break-before: page; padding-top: 120mm; font-size: 8.5pt; color: #6b6259; text-align: center; }
"""


def construire_html(dossier: Path, livre: dict, pages: list[dict]) -> str:
    c = fabrication.composer(dossier, pages)
    # Les images sont prises sur le disque : « images/x » devient un chemin file://
    def source(m: re.Match) -> str:
        fichier = c["images"].get(m.group(1))
        return f'src="{fichier.as_uri()}"' if fichier and fichier.is_file() else 'src=""'

    corps = "".join("".join(f["corps"]) for f in c["fichiers"])
    corps = re.sub(r'src="(images/[^"]+)"', source, corps)
    corps = re.sub(r'href="p\d{4}\.xhtml#', 'href="#', corps)      # liens internes : un seul document
    e = html.escape
    rang_couverture = livre.get("couverture") or (pages[0]["rang"] if pages else None)
    image_couverture = dossier / "pages" / f"{rang_couverture:04d}.jpg" if rang_couverture else None
    couverture = (f'<section class="couverture"><img src="{image_couverture.as_uri()}" alt=""/></section>'
                  if image_couverture and image_couverture.is_file() else "")
    edition = " · ".join(x for x in (livre.get("editeur"), livre.get("annee")) if x)
    sommaire = ""
    if len(c["sommaire"]) > 1:
        lignes = "".join(f'<li><a href="#{e(ancre)}">{e(titre)}</a></li>' for _, ancre, titre in c["sommaire"])
        sommaire = f'<nav class="sommaire"><h2>Sommaire</h2><ul>{lignes}</ul></nav>'
    isbn = f"ISBN {livre['isbn']}. " if livre.get("isbn") else ""
    return f"""<!DOCTYPE html>
<html lang="{e(livre.get('langue') or 'fr')}"><head><meta charset="utf-8"/><title>{e(livre['titre'])}</title>
<meta name="author" content="{e(livre.get('auteur') or '')}"/><style>{_css()}</style></head><body>
{couverture}
<section class="titre-livre"><h1>{e(livre['titre'])}</h1>
<p class="auteur">{e(livre.get('auteur') or '')}</p><p class="edition">{e(edition)}</p></section>
{sommaire}
<main>{corps}</main>
<section class="colophon"><p>{e(livre['titre'])}{(' — ' + e(livre['auteur'])) if livre.get('auteur') else ''}.<br/>
{e(edition)}{'. ' if edition else ''}{e(isbn)}<br/>
Recomposé par Scriptorium à partir d'un exemplaire scanné, le {date.today().strftime('%d/%m/%Y')}.<br/>
Les numéros en marge renvoient aux pages du livre papier.</p></section>
</body></html>"""


def fabriquer_pdf(dossier: Path, livre: dict, pages: list[dict], sortie: Path) -> dict:
    from weasyprint import HTML

    document = HTML(string=construire_html(dossier, livre, pages), base_url=str(dossier)).render()
    sortie.parent.mkdir(parents=True, exist_ok=True)
    tmp = sortie.with_suffix(".tmp")
    document.write_pdf(tmp)
    tmp.replace(sortie)
    return {"pages_pdf": len(document.pages)}
