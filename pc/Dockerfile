# syntax=docker/dockerfile:1
# Contre-lecture de Scriptorium sur le PC (Docker Desktop) : Marker sur le processeur.
# Docker Desktop sous Windows ne donne pas accès aux cartes AMD : tout se calcule sur le processeur.
FROM python:3.12-slim-bookworm
LABEL org.opencontainers.image.title="scriptorium-calcul" \
      org.opencontainers.image.description="Contre-lecture des pages de Scriptorium par Marker, sur le PC de calcul" \
      org.opencontainers.image.source="https://github.com/baloodusudouest/scriptorium"

RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 tzdata \
    && rm -rf /var/lib/apt/lists/*
# torch en version processeur (bien plus légère que la version CUDA), puis Marker (version figée : son API bouge)
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir "marker-pdf==2.2.0" "httpx==0.28.1"

WORKDIR /calcul
COPY calcul.py .
# Les modèles (environ 2 Go) sont téléchargés au premier lancement dans /cache, gardé dans un volume
ENV TZ=Europe/Paris PYTHONUNBUFFERED=1 TORCH_DEVICE=cpu XDG_CACHE_HOME=/cache HF_HOME=/cache/huggingface
VOLUME /cache
CMD ["python", "calcul.py"]
