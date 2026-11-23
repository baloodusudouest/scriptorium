# Reprise — Scriptorium

Fichier à lire en premier dans une nouvelle session. Le mettre à jour à chaque fin de session, dans le même commit que le code.

## État (23/11/2026) — 0.8.3 : listes déroulantes lisibles en sombre (`frontend/src/app.css`, bloc « Listes déroulantes (socle 0.12.2) » : `select option, select optgroup` aux couleurs `--popover`). Jamais essayé sur la vraie installation.

## État (22/11/2026) — 0.8.2 : barre d'onglets collée en bas sur iPhone (`App.svelte`, classes du socle 0.12.1 : `fixed inset-x-0 bottom-0 … pb-[calc(0.375rem+env(safe-area-inset-bottom))]`, `md:right-auto md:justify-start`). Jamais essayé sur la vraie installation.

## État (20/11/2026)

- **0.8.1 (20/11/2026)** : copies communes du socle 0.11.1 (titre « Pour le relier » quand le réglage est dans l'appli).
- **0.8.0** (20/11/2026) : fiches « Connexion » communes (contrat 3, socle 0.11.0, `app/maison.py` et `frontend/src/lib/services/` copies non retouchées).
  - Services déclarés dans `app/main.py` (section « fiches Connexion ») : `mistral` (Vérifier = liste des modèles, gratuite), `pc-calcul` (Vérifier = date du dernier passage, jamais d'appel au PC ; guide dans `contre.guide`), `grimmory` (dossier inscriptible, sans écrire). Aucun geste.
  - Routes `GET /api/maison/services`, `POST /api/maison/services/{id}/verifier` (session ou `ANNEAU_CLE`). Dossier de données dans Réglages (`GET /api/dossier`).
  - **À retirer en 0.9.0** : `GET /api/services` et `POST /api/services/mistral/verifier`.
  - **Jamais essayé sur la vraie installation** (ni l'écran, ni la lecture par l'Anneau, ni le guide du PC face au vrai PC).

## État (18/11/2026)

- **0.7.0** (18/11/2026) : santé des tâches de fond (socle 0.9.0, `app/maison.py` copie signée non retouchée).
  - Tâches dans `maison.TACHES`, déclarées par `Travail.demarrer` (rien quand `travail_auto` est coupé) : `purge-corbeille` (régulière 3 600 s, témoin de vie du fil de travail), `decoupe`, `lecture-mistral`, `pdf-a5` (à la demande, autour de chaque tâche de `une_tache` ; pour le PDF, autour de `pdf_livre.fabriquer_pdf`) ; `copie-des-bases` (régulière 86 400 s, `maison.planifier_copie` lancée dans `cycle`, annulée à l'arrêt).
  - Copie de `scriptorium.db` à 02:20 heure de Paris dans `<données>/copies` (`scriptorium-derniere.db`, `copie.json`).
  - `/health` ajoute `version_socle`, `taches`, `copie_base` (messages seulement avec `MAISON_JETON` ou une session). Un seul worker uvicorn. Tests : `tests/test_sante.py`.
  - **Jamais essayé sur la vraie installation** (ni la copie de nuit, ni une restauration depuis la copie).

## État (16/11/2026)

- **0.6.0** (16/11/2026) : réglages dans l'appli, sauvegarde et restauration ; anciens noms retirés.
  - Réglages d'usage (`app/config.py` : `REGLAGES`, `VARIABLES_REPRISES`, `BORNES`, `EXCLUS`) : `recherche_web` (oui/non, oui), `prix_page` (nombre, 0.002), `dpi` (entier, 200). Gardés dans `<données>/reglages.json` par `maison.Reglages` ; repris une fois de `SCRIPTORIUM_RECHERCHE_WEB`, `SCRIPTORIUM_PRIX_PAGE`, `SCRIPTORIUM_DPI` au premier démarrage (ligne « Réglage repris de la stack » au journal), puis ces variables ne sont plus lues. Écran : `frontend/src/pages/Reglages.svelte`, tuiles « Usage » et « Restaurer les réglages ».
  - Routes (`app/main.py`) : `GET`/`PUT /api/reglages`, `GET`/`POST /api/restaurer` (session) ; `GET /externe/sauvegarde` (jeton commun seulement, 404 si `MAISON_JETON` vide). La découpe lit `dpi` par `Travail._dpi()`.
  - Mot de passe : `MAISON_PASSWORD` seul (`SCRIPTORIUM_PASSWORD` n'est plus lu). `MAISON_JETON` entre dans le conteneur.
  - **Déploiement en deux temps** : d'abord la nouvelle image avec la stack actuelle (les réglages sont repris des anciennes variables au premier démarrage), vérifier Réglages, puis la nouvelle stack sans les anciennes lignes (`SCRIPTORIUM_PASSWORD`, `SCRIPTORIUM_RECHERCHE_WEB`) et avec `MAISON_JETON`. Attention : `MAISON_PASSWORD` doit déjà être rempli dans la stack, sinon la 0.6 ne démarre pas.
  - **Jamais essayé sur la vraie installation** (ni la reprise, ni la collecte par l'Anneau, ni la restauration).
- **0.5.0** (16/11/2026) : variables communes de la maison (`app/maison.py`, `app/config.py`, Réglages) : `MAISON_PASSWORD` (repli `SCRIPTORIUM_PASSWORD`, retiré en 0.6), `MAISON_LECTURE_SEULE` (forçable par `SCRIPTORIUM_LECTURE_SEULE`). Le jeton du PC de calcul reste propre.
- **0.4.1 à 0.4.3** (15/11/2026) : tuiles du bilan cliquables, numéro de page dans l'écran de la page, listes numérotées réparées, ISBN par photo du code-barres.
- **0.4.0** (15/11/2026) : fiche par l'ISBN (BnF puis Open Library, proposée et non imposée), couverture choisie, métadonnées dans l'EPUB, PDF A5 soigné (WeasyPrint, tâche de fond). Fin des trois livraisons prévues au conseil.
- **0.3.1** (15/11/2026) : contre-lecture par Marker sur le PC (`pc/`, image `scriptorium-calcul`), porte `/calcul` à jeton, mots à relire dans l'écran de relecture.
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

1. L'utilisateur redéploie en 0.4.0 (re-pull), ajoute `SCRIPTORIUM_JETON_CALCUL` à la stack et lance `pc/calcul.yml` sur le PC (voir `pc/LISEZMOI.md`). À recueillir sur le vrai livre :
   - temps de découpe du PDF de 400 Mo, justesse de l'inventaire, reprise des pages manquantes à l'iPhone ;
   - temps par page de Marker sur le PC, et utilité des mots à relire (trop de bruit ? assez de vraies fautes ?) ;
   - la fiche trouvée par l'ISBN ;
   - le temps de fabrication du PDF A5 sur le J4125 et son rendu ;
   - l'EPUB dans Grimmory, KOReader et Comptoir (listes numérotées « ordre de préparation » : dans l'essai de Comptoir, seuls les numéros restaient).
2. Jamais essayés en vrai : Marker 2.2 dans le conteneur du PC (l'API est appelée comme `marker_single`, avec repli sur la commande), l'API SRU de la BnF depuis le NAS, WeasyPrint dans l'image Docker.
3. À vérifier sur la page « ordre de préparation » du vrai livre : la réparation des listes numérotées (0.4.3) suppose une des trois formes connues ; si le texte de Mistral (écran de la page) en montre une autre, l'ajouter à `reparer_listes`.
4. Plus tard, si le besoin revient : prise d'un livre entier à l'iPhone (file d'attente hors ligne, HTTPS par Tailscale Serve), voie B (modèle de vision sur la carte AMD) à la place de Mistral.

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
- Réglages d'usage : ne jamais relire leur variable après le premier démarrage. Un nouveau réglage s'ajoute dans `REGLAGES` (le type de la valeur par défaut fixe son type), avec ses bornes éventuelles et son libellé dans `Reglages.svelte` ; s'il ressemble à un secret, `maison.est_secret` l'écarte des sauvegardes, sinon l'ajouter à `EXCLUS` s'il ne doit pas sortir.
- `tools/demo.py` simule l'Anneau (`ETAT["lire_anneau"]`, deux sauvegardes) pour l'écran Restaurer ; les tests passent leur faux Anneau de la même façon.
- Hérités du socle : `pages/Services.svelte` est l'écran « Connexion », et `pages/Connexion.svelte` la page du mot de passe.

## Non-objectifs

- Pas d'envoi des illustrations dans Immich.
- Pas de dossier surveillé.
- Pas de lien avec Home Assistant.
- Pas de fiches vers Mealie pour l'instant.
