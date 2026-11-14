# Docling sur le processeur, avec Tesseract (français et anglais) pour la lecture.
FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-fra tesseract-ocr-eng libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
# torch en version processeur (bien plus léger que la version CUDA, inutile avec une carte AMD sous Docker Desktop)
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir "docling>=2.60" "pillow-heif>=0.18"
WORKDIR /outils
COPY outils/ /outils/
ENV PYTHONUNBUFFERED=1 SONDE_RACINE=/sonde HF_HOME=/sonde/.cache/huggingface OMP_NUM_THREADS=8
