"""Marker (moteurs Surya / Indra), sur le processeur, en mode « fast » (le seul raisonnable sans carte NVIDIA)."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from commun import traiter


def lire(page: Path, sortie: Path) -> dict:
    tmp = sortie / "_marker"
    if tmp.exists():
        shutil.rmtree(tmp)
    r = subprocess.run(
        ["marker_single", str(page), "--output_dir", str(tmp), "--output_format", "markdown", "--mode", "fast"],
        capture_output=True, text=True, timeout=1800,
    )
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout)[-600:])
    mds = list(tmp.rglob("*.md"))
    if not mds:
        raise RuntimeError("Marker n'a produit aucun Markdown")
    md = mds[0]
    texte = md.read_text(encoding="utf-8")
    nb = 0
    for img in md.parent.iterdir():
        if img.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
            shutil.move(str(img), sortie / "images" / img.name)
            texte = texte.replace(f"]({img.name})", f"](images/{img.name})")
            nb += 1
    (sortie / "page.md").write_text(texte, encoding="utf-8")
    shutil.rmtree(tmp, ignore_errors=True)
    return {"images": nb}


if __name__ == "__main__":
    traiter("marker", lire)
