# Journal des versions — Scriptorium

## Inventaire et décisions — 14/11/2026

- `sonde/outils/inventaire.py` (`docker compose run --rm inventaire`) : pages manquantes, à vérifier, en double, et pages sans numéro d'un PDF déjà scanné. La lecture du numéro imprimé se fait en local (taches d'encre lues une à une par Tesseract) ; le PDF est lu page par page.
- Dossier : décisions prises après la sonde (Mistral d'abord avec contre-lecture locale, prise page par page, import d'un gros PDF, inventaire).

## Sonde, tour 2 — 14/11/2026

- Préparation des pages, version 2 :
  - sens de lecture trouvé par Tesseract (lecture d'un extrait dans les quatre sens) ;
  - recadrage sur le papier (clair et peu coloré), d'abord en hauteur sur toute la double page, puis en largeur page par page ;
  - coupe au pli : une bande sombre des deux côtés, pour qu'une photo sombre pleine page n'attire pas la coupe.
- Image légère : Tesseract français et numpy.
- `docs/sonde.md` : compte rendu du tour 1.

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
