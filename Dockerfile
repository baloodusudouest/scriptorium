# syntax=docker/dockerfile:1
# ---------- Étape 1 : interface Svelte compilée ----------
FROM node:22-bookworm-slim AS interface
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN mkdir -p /app && npx vite build --outDir /app/static --emptyOutDir

# ---------- Étape 2 : dépendances Python en roues ----------
FROM python:3.12-slim-bookworm AS roues
WORKDIR /build
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# ---------- Étape 3 : image d'exécution ----------
FROM python:3.12-slim-bookworm
LABEL org.opencontainers.image.title="scriptorium" \
      org.opencontainers.image.description="Scriptorium : d’un livre scanné à un livre en texte (PDF + EPUB)" \
      org.opencontainers.image.source="https://github.com/baloodusudouest/scriptorium"

# gosu : abandon des droits root ; tzdata : heure française ; tesseract : lecture des numéros de page ;
# pango et harfbuzz : mise en page du PDF A5 par WeasyPrint (les polices sont dans app/polices)
RUN apt-get update && apt-get install -y --no-install-recommends gosu tzdata tesseract-ocr \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=roues /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

WORKDIR /app
COPY app ./app
COPY --from=interface /app/static ./app/static
COPY entrypoint.sh /entrypoint.sh
RUN chmod 755 /entrypoint.sh

ENV TZ=Europe/Paris \
    SCRIPTORIUM_DATA=/data \
    SCRIPTORIUM_PORT=8091 \
    PYTHONUNBUFFERED=1

EXPOSE 8091
HEALTHCHECK --interval=60s --timeout=5s --retries=3 \
  CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('SCRIPTORIUM_PORT','8091')+'/health')" || exit 1
ENTRYPOINT ["/entrypoint.sh"]
