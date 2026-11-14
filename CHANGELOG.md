# Journal des versions — Scriptorium

## Sonde — 14/11/2026

- `sonde/` : kit à lancer sur le PC, dans Docker Desktop.
  - Préparation des pages : PDF, JPEG, HEIC.
  - Quatre moteurs : Docling (Tesseract en français) et Marker sur le processeur ; modèle de vision par LM Studio ; Mistral OCR.
  - Rapport HTML autonome, avec les rendus côte à côte et les temps.
- Tests de la partie légère, avec de faux serveurs Mistral et LM Studio, ajoutés à GitHub Actions. `pytest.ini` limite les tests de l'appli au dossier `tests/`.

## 0.1.0 — 14/11/2026

- Squelette copié du socle 0.3.2 : FastAPI, Svelte 5, Tailwind 4, shadcn-svelte, mot de passe commun et cookie de l'Anneau, mode lecture seule, `/health`.
- Nom Scriptorium, variables `SCRIPTORIUM_PASSWORD`, `SCRIPTORIUM_DATA`, `SCRIPTORIUM_LECTURE_SEULE` et `SCRIPTORIUM_PORT`, port 8091.
- Couleur sépia papier ancien (`#c4a07a`).
- Écran « Composants » du socle retiré.
- `docs/dossier.md` : conception en six sections, issue du grill.
