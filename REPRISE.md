# Reprise — Scriptorium

Fichier à lire en premier dans une nouvelle session. Le mettre à jour à chaque fin de session, dans le même commit que le code.

## État (15/11/2026)

- **0.3.0** (15/11/2026) : reprise d'une page manquante à l'iPhone, rangée à sa place d'après son numéro ; écran de relecture d'une page (image et texte, correction gardée, relecture d'une seule page par Mistral, « garder en image », rotation). Voir `CHANGELOG.md`.
- **0.2.4** (15/11/2026) : icône propre (lettrine « S » sépia). Tuile dans l'Anneau (Médias, à côté de Grimmory), posée dans Atlas.
- **0.2.3** (14/11/2026) : EPUB lisible par Comptoir (recette jamais coupée entre deux fichiers, ingrédients en liste, repères de page dans le fil).
- **0.2.2** (14/11/2026) : Mistral lit sans attendre l'inventaire et donne les numéros de page, EPUB d'essai (pages lues), page de l'original dans l'EPUB (repère et `page-list`), dépôt après inventaire confirmé.
- **0.2.1** (14/11/2026) : numéros de page mieux lus, et « Relire les numéros » (voir `CHANGELOG.md`).
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
2. Faits en 0.3.0 : relecture image/texte, choix « recomposer / garder en image », reprise des pages manquantes à l'iPhone. **Reste de la 0.3** : contre-lecture Marker sur le PC (`pc/calcul.yml`) et mots à relire surlignés dans l'écran de relecture.
3. Livraison 0.4 : fiche par ISBN, PDF A5 soigné. (La prise iPhone faite en 0.3.0 est une page à la fois, sans file d'attente hors ligne : à revoir si un livre entier doit être pris à l'iPhone.)
4. Sur le vrai livre, à surveiller : les listes numérotées (« ordre de préparation ») qui, dans l'essai de Comptoir, ne gardaient que les numéros 1. à 7. sans leur texte.

## Décisions tranchées

Voir la fin de `docs/dossier.md`. Pour mémoire :

- Mistral d'abord, contre-lecture Marker sur le PC (en 0.3).
- Prise iPhone page par page.
- Livre recomposé (EPUB), une page douteuse entrant en image.
- Trois livraisons.
- Rien vers Home Assistant.

## Pièges

- L'EPUB a deux lecteurs : la liseuse (KOReader) et **Comptoir**, qui en tire les recettes. Contrat avec Comptoir : titre de recette en `h1`–`h3`, ingrédients en `ul`, repère `epub:type="pagebreak"` (avec `title` = page du livre papier) dans le fil. Ne pas le casser sans prévenir Comptoir.

- EbookLib n'écrit pas la liste des pages (`page-list`) : `fabrication.ajouter_liste_des_pages` la glisse dans `nav.xhtml` en réécrivant l'archive, avec « mimetype » en tête et non compressé.
- Numéro de page : celui corrigé à la main (`numero_manuel`), sinon celui de Mistral (`numero_mistral`), sinon celui de Tesseract (`numero_lu`) ; puis `corriger` écarte ce qui ne suit pas la pente des voisines.

- Le squelette s'appelait déjà 0.1.0 : les livraisons du conseil sont numérotées 0.2, 0.3 et 0.4.
- Le mode lecture seule bloque aussi l'envoi à Mistral : les pages sortiraient de la maison, et la lecture est payante.
- Mistral peut rendre une page sous forme de données (`[{"box_2d": …}]`) au lieu de texte : cette page est marquée « douteuse » et entre dans le livre en image (`app/mistral.py`, `_douteuse`).
- Avec la liste blanche de chiffres, Tesseract change n'importe quelle lettre en chiffre : le « Z » d'un index de marge devenait « 2 » (premier vrai livre, 0.2.1). Les gardes actuelles :
  - seule la dernière ligne d'encre est lue ;
  - une ligne de texte est refusée ;
  - le nombre doit être confirmé par une lecture libre ;
  - une tache plus large que 3,5 fois sa hauteur (un mot) est ignorée.
  Le Z d'un index lu seul, sous le texte, reste possible ; il est alors écarté par la pente des numéros voisins (`corriger`).
- `tools/demo.py` remplace la lecture de Mistral le temps de préparer ses livres, puis la remet en place. Sans cela, les tests du vrai client échouent quand ils passent après les tests d'écran.
- Le conteneur prend les droits du propriétaire de `/data` : le bookdrop de Grimmory doit être inscriptible par ce même compte.
- Sonde : Hugging Face et l'API Mistral sont injoignables depuis l'environnement de Claude. `docling` 2.150 a déprécié `force_full_page_ocr` (écrire `mode=OcrMode.FULL_PAGE`).
- Hérités du socle : `pages/Services.svelte` est l'écran « Connexion », et `pages/Connexion.svelte` la page du mot de passe.

## Non-objectifs

- Pas d'envoi des illustrations dans Immich.
- Pas de dossier surveillé.
- Pas de lien avec Home Assistant.
- Pas de fiches vers Mealie pour l'instant.
