"""Assemble resultats/rapport.html : pour chaque page, l'image d'origine puis le rendu de chaque moteur, côte à côte.

Le rapport est autonome (images incluses en base64) : on peut l'ouvrir hors ligne, ou l'envoyer tel quel.
"""
from __future__ import annotations

import base64
import html
import io
import json
import mimetypes
import os
import re
from pathlib import Path

import markdown
from PIL import Image

RACINE = Path(os.environ.get("SONDE_RACINE", "/sonde"))
PREP = RACINE / "pages_prep"
RESULTATS = RACINE / "resultats"
ORDRE = ["docling", "marker", "vision", "mistral"]
NOMS = {"docling": "Docling (processeur)", "marker": "Marker (processeur)",
        "vision": "Modèle de vision (carte AMD)", "mistral": "Mistral OCR (en ligne)"}


def _donnees(chemin: Path, cote: int | None = None) -> str:
    if cote:
        with Image.open(chemin) as im:
            im = im.convert("RGB")
            im.thumbnail((cote, cote))
            t = io.BytesIO()
            im.save(t, "JPEG", quality=82)
        return "data:image/jpeg;base64," + base64.b64encode(t.getvalue()).decode()
    type_ = mimetypes.guess_type(chemin.name)[0] or "image/png"
    return f"data:{type_};base64," + base64.b64encode(chemin.read_bytes()).decode()


def _rendu(dossier: Path) -> str:
    md_fichier = dossier / "page.md"
    if not md_fichier.exists():
        return "<p class='vide'>pas de texte</p>"
    texte = md_fichier.read_text(encoding="utf-8")

    def remplacer(m: re.Match) -> str:
        cible = (dossier / m.group(2)).resolve()
        if cible.is_file() and dossier.resolve() in cible.parents:
            return f"![{m.group(1)}]({_donnees(cible, 900)})"
        return f"*[illustration : {m.group(1) or 'sans légende'}]*"

    texte = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", remplacer, texte)
    # Le texte vient des moteurs : on le rend en HTML mais sans laisser passer de balise <script>.
    rendu = markdown.markdown(texte, extensions=["tables", "footnotes", "sane_lists"])
    return re.sub(r"(?is)<\s*/?\s*script[^>]*>", "", rendu)


def _mesure(dossier: Path) -> dict:
    try:
        return json.loads((dossier / "mesure.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def construire() -> Path:
    pages = sorted(PREP.glob("*.png"))
    moteurs = [m for m in ORDRE if (RESULTATS / m).is_dir()]
    lignes_temps, sections = [], []
    for m in moteurs:
        mesures = [_mesure(RESULTATS / m / p.stem) for p in pages]
        ok = [x for x in mesures if x and not x.get("erreur")]
        moyen = round(sum(x["secondes"] for x in ok) / len(ok), 1) if ok else None
        erreurs = sum(1 for x in mesures if x.get("erreur"))
        factures = sum(x.get("pages_facturees", 0) for x in ok)
        lignes_temps.append(
            f"<tr><td>{NOMS[m]}</td><td>{len(ok)}/{len(pages)}</td>"
            f"<td>{moyen if moyen is not None else '—'} s</td><td>{erreurs}</td>"
            f"<td>{factures if m == 'mistral' else '—'}</td></tr>")
    for p in pages:
        colonnes = [f"<div class='col orig'><h3>Page d'origine</h3><img src='{_donnees(p, 1400)}' alt='page'></div>"]
        for m in moteurs:
            d = RESULTATS / m / p.stem
            me = _mesure(d)
            entete = f"{NOMS[m]} · {me.get('secondes', '?')} s"
            if me.get("modele"):
                entete += f" · {html.escape(str(me['modele']))}"
            corps = (f"<p class='erreur'>{html.escape(me['erreur'])}</p>" if me.get("erreur") else _rendu(d))
            colonnes.append(f"<div class='col'><h3>{entete}</h3><div class='texte'>{corps}</div></div>")
        sections.append(f"<section><h2>{html.escape(p.stem)}</h2><div class='grille'>{''.join(colonnes)}</div></section>")
    page = f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Scriptorium — rapport de sonde</title>
<style>
:root{{color-scheme:dark;--fond:#151311;--surface:#1f1c19;--filet:#312c27;--texte:#f2ece2;--second:#a89e91;--app:#c4a07a}}
body{{margin:0;background:var(--fond);color:var(--texte);font:15px/1.5 Inter,system-ui,sans-serif}}
header{{padding:24px 28px;border-bottom:1px solid var(--filet)}} h1{{font-weight:300;font-size:32px;margin:0 0 12px}}
table{{border-collapse:collapse}} td,th{{padding:6px 12px;border-bottom:1px solid var(--filet);text-align:left}} th{{color:var(--second);font-weight:500}}
section{{padding:20px 28px;border-bottom:1px solid var(--filet)}} h2{{font-weight:300;color:var(--app)}}
.grille{{display:grid;grid-template-columns:repeat({len(moteurs) + 1},minmax(320px,1fr));gap:14px;overflow-x:auto}}
.col{{background:var(--surface);border:1px solid var(--filet);border-radius:12px;padding:12px;min-width:0}}
.col h3{{font-size:13px;font-weight:500;color:var(--second);margin:0 0 8px}}
.orig img{{width:100%;border-radius:6px;position:sticky;top:8px}}
.texte{{font-family:"EB Garamond",Georgia,serif;font-size:16px;max-height:80vh;overflow:auto}}
.texte img{{max-width:100%;border-radius:4px}} .texte table{{font-size:13px}} .texte td,.texte th{{border:1px solid var(--filet)}}
.texte blockquote{{border-left:3px solid var(--app);margin-left:0;padding-left:12px;color:var(--second)}}
.erreur{{color:#e58a7a}} .vide{{color:var(--second)}}
</style></head><body>
<header><h1>Scriptorium — rapport de sonde</h1>
<table><tr><th>Moteur</th><th>Pages lues</th><th>Temps moyen</th><th>Erreurs</th><th>Pages Mistral facturées</th></tr>
{''.join(lignes_temps)}</table></header>
{''.join(sections)}
</body></html>"""
    sortie = RESULTATS / "rapport.html"
    sortie.write_text(page, encoding="utf-8")
    print(f"Rapport écrit : resultats/rapport.html ({len(pages)} page(s), moteurs : {', '.join(moteurs) or 'aucun'})")
    return sortie


if __name__ == "__main__":
    construire()
