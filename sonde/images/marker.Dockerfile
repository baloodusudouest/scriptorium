# Marker sur le processeur.
FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir "marker-pdf>=1.8"
WORKDIR /outils
COPY outils/ /outils/
ENV PYTHONUNBUFFERED=1 SONDE_RACINE=/sonde HF_HOME=/sonde/.cache/huggingface TORCH_DEVICE=cpu
