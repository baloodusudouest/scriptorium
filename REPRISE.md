# Reprise — Scriptorium

Fichier à lire en premier dans une nouvelle session. Le mettre à jour à chaque fin de session, dans le même commit que le code.

## État (14/11/2026)

- **0.2.0, première livraison utile** (voir `CHANGELOG.md`) :
  - import d'un PDF par morceaux, avec reprise ;
  - découpe en pages sur le NAS et lecture locale des numéros imprimés (Tesseract) ;
  - inventaire : pages manquantes montrées à leur place, à vérifier, en double, sans numéro ; correction d'un numéro et mise à l'écart d'une page ; confirmation à la main ;
  - lecture par Mistral sur un clic, avec le coût estimé affiché avant ;
  - EPUB recomposé simple et PDF d'archive des images de pages ;
  - dépôt de l'EPUB dans le bookdrop de Grimmory, sans jamais remplacer un fichier ;
  - tests : 27 au total (serveur, faux Mistral, écran sur PC et iPhone par `tools/demo.py`).
- Conception : [`docs/dossier.md`](docs/dossier.md). Sonde : [`docs/sonde.md`](docs/sonde.md). Conseil : [`docs/conseil.md`](docs/conseil.md). Les décisions qui font foi sont en fin de dossier.
- **Jamais essayé sur la vraie installation** :
  - le PDF de 400 Mo (temps de découpe sur le Celeron J4125, lecture des numéros sur de vraies pages) ;
  - le vrai Mistral depuis le NAS ;
  - les droits d'écriture du conteneur dans le bookdrop de Grimmory ;
  - l'EPUB ouvert dans KOReader.

## Prochaine étape

1. L'utilisateur déploie la 0.2.0 (service `scriptorium` ajouté à `homelab.yml`, variable `SCRIPTORIUM_MISTRAL_CLE`) et importe son PDF de 400 Mo. Retours à recueillir :
   - temps de découpe ;
   - justesse de l'inventaire face au sommaire ;
   - qualité du texte lu par Mistral ;
   - rendu de l'EPUB dans Grimmory et sur la Kindle.
2. Livraison 0.3 : relecture image/texte, contre-lecture Marker (`pc/calcul.yml`), choix « recomposer / garder en image » par page.
3. Livraison 0.4 : prise iPhone page par page et insertion des pages manquantes à leur place, fiche par ISBN, PDF A5.

## Décisions tranchées

Voir la fin de `docs/dossier.md`. Pour mémoire :

- Mistral d'abord, contre-lecture Marker sur le PC (en 0.3).
- Prise iPhone page par page.
- Livre recomposé (EPUB), une page douteuse entrant en image.
- Trois livraisons.
- Rien vers Home Assistant.

## Pièges

- Le squelette s'appelait déjà 0.1.0 : les livraisons du conseil sont numérotées 0.2, 0.3 et 0.4.
- Le mode lecture seule bloque aussi l'envoi à Mistral : les pages sortiraient de la maison, et la lecture est payante.
- Mistral peut rendre une page sous forme de données (`[{"box_2d": …}]`) au lieu de texte : cette page est marquée « douteuse » et entre dans le livre en image (`app/mistral.py`, `_douteuse`).
- Tesseract force en chiffres tout ce qu'il lit avec la liste blanche de chiffres : une tache plus large que 3,5 fois sa hauteur (un mot) est ignorée, sinon un titre courant devient un faux numéro.
- `tools/demo.py` remplace la lecture de Mistral le temps de préparer ses livres, puis la remet en place. Sans cela, les tests du vrai client échouent quand ils passent après les tests d'écran.
- Le conteneur prend les droits du propriétaire de `/data` : le bookdrop de Grimmory doit être inscriptible par ce même compte.
- Sonde : Hugging Face et l'API Mistral sont injoignables depuis l'environnement de Claude. `docling` 2.150 a déprécié `force_full_page_ocr` (écrire `mode=OcrMode.FULL_PAGE`).
- Hérités du socle : `pages/Services.svelte` est l'écran « Connexion », et `pages/Connexion.svelte` la page du mot de passe.

## Non-objectifs

- Pas d'envoi des illustrations dans Immich.
- Pas de dossier surveillé.
- Pas de lien avec Home Assistant.
- Pas de fiches vers Mealie pour l'instant.
