# Image légère : préparation des pages, Mistral OCR, modèle de vision (appel réseau), rapport.
FROM python:3.12-slim-bookworm
RUN pip install --no-cache-dir "pillow>=10" "pillow-heif>=0.18" "pypdfium2>=4.30" "httpx>=0.27" "markdown>=3.6"
WORKDIR /outils
COPY outils/ /outils/
ENV PYTHONUNBUFFERED=1 SONDE_RACINE=/sonde
