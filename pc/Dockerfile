# syntax=docker/dockerfile:1
# Contre-lecture de Scriptorium sur le PC (Docker Desktop) : Marker sur le processeur.
# Docker Desktop sous Windows ne donne pas accès aux cartes AMD : tout se calcule sur le processeur.
FROM python:3.12-slim-bookworm
LABEL org.opencontainers.image.title="scriptorium-calcul" \
      org.opencontainers.image.description="Contre-lecture des pages de Scriptorium par Marker, sur le PC de calcul" \
      org.opencontainers.image.source="https://github.com/baloodusudouest/scriptorium"

RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 tzdata \
    && rm -rf /var/lib/apt/lists/*
# torch en version processeur (bien plus légère que la version CUDA), puis Marker (version figée : son API bouge).
# 0.6.7 (audit, M41) : torch et torchvision bornés à leur ligne actuelle (torch 2.x, torchvision 0.x) : une version
# majeure ne peut plus arriver seule à la reconstruction. Les versions exactes n'ont pas pu être relevées sans réseau :
# au premier build réussi, lire « pip freeze | grep torch » dans l'image et les écrire ici (torch==…, torchvision==…).
RUN pip install --no-cache-dir "torch>=2,<3" "torchvision<1" --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir "marker-pdf==2.2.0" "httpx==0.28.1"

# 0.6.7 (audit, M41) : le calcul tourne sous un compte sans droits (uid 1000), propriétaire du cache des modèles
RUN useradd --create-home --uid 1000 calcul && mkdir -p /cache && chown calcul:calcul /cache

WORKDIR /calcul
COPY calcul.py .
# Les modèles (environ 2 Go) sont téléchargés au premier lancement dans /cache, gardé dans un volume
ENV TZ=Europe/Paris PYTHONUNBUFFERED=1 TORCH_DEVICE=cpu XDG_CACHE_HOME=/cache HF_HOME=/cache/huggingface
VOLUME /cache
USER calcul
CMD ["python", "calcul.py"]
