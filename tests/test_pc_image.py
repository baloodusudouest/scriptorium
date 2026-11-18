"""0.6.7 (audit du 17/11/2026, M41) : l'image du PC de calcul ne tourne pas en root et torch n'y bouge pas seul."""
from __future__ import annotations

import re
from pathlib import Path

DOCKERFILE = (Path(__file__).resolve().parent.parent / "pc" / "Dockerfile").read_text()


def test_utilisateur_non_root():
    users = re.findall(r"^USER\s+(\S+)", DOCKERFILE, flags=re.M)
    assert users and users[-1] not in ("root", "0")
    assert DOCKERFILE.index("USER") < DOCKERFILE.index("CMD")
    assert "chown" in DOCKERFILE and "/cache" in DOCKERFILE      # le cache des modèles lui appartient


def test_versions_bornees():
    pip = " ".join(re.findall(r"pip install[^\n]*(?:\\\n[^\n]*)*", DOCKERFILE))
    for paquet in ("torch", "torchvision", "marker-pdf"):
        assert re.search(rf'"{paquet}(==|>=|<)[^"]+"', pip), paquet            # jamais sans version
    assert '"marker-pdf==2.2.0"' in pip
    assert re.search(r'"torch>=2,<3"', pip) and re.search(r'"torchvision<1"', pip)
