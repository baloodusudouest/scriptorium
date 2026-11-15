# Journal des versions — Scriptorium

## 0.3.0 — 15/11/2026 — reprise des pages manquantes et relecture page par page

Deux demandes de l'utilisateur, avancées avant la contre-lecture Marker (qui reste à faire).

- **Reprendre une page manquante à l'iPhone.** Chaque case « page manquante » a un bouton « Prendre » : sur l'iPhone il ouvre l'appareil photo (sur PC, le choix d'un fichier). Une autre page (fin du livre, cas douteux) se reprend par son numéro, sous la grille. La photo est remise droite (EXIF), recadrée sur le papier (le recadrage de la sonde, `app/capture.py`), réduite à 2400 px, puis **rangée à sa place d'après son numéro** : après la dernière page de numéro inférieur et les pages sans numéro qui la suivent (photos pleine page), avant la suivante. Elle attend ensuite la lecture par Mistral comme les autres ; son numéro, posé à la main, n'est pas remplacé. Les photos HEIC sont acceptées si `pillow-heif` est là.
- **Relecture d'une page** (`#/livre/ID/page/RANG`) : un clic sur une page ouvre l'image à gauche et le texte lu à droite (l'un sous l'autre sur iPhone), avec la page précédente et la suivante.
  - Corriger le texte et l'enregistrer : un texte corrigé à la main n'est plus jamais écrasé par une nouvelle lecture.
  - « Faire relire par Mistral » : cette seule page repart chez Mistral (le texte corrigé est alors abandonné).
  - « Recomposer (texte) » / « Garder en image » : une page gardée en image entre en image dans l'EPUB, même lue.
  - « Tourner » : un quart de tour pour une photo prise de travers ; une page déjà lue repasse « à lire ».
- Base : les pages ont une place (`ordre`, qui permet d'en insérer une entre deux), une origine (`pdf` ou `photo`), un rendu choisi et la marque « texte corrigé à la main ». Migration automatique des livres existants.
- Les images de page restent en cache une minute au lieu d'un jour (une page peut être tournée).
- Tests : 45 au total, dont photo recadrée, page insérée à sa place (au milieu, avant la première, après la dernière), photo illisible refusée, rotation, texte corrigé gardé, relecture d'une seule page, page gardée en image dans l'EPUB, et deux tests d'écran (prise d'une page manquante, relecture sur PC et iPhone).

## 0.2.4 — 15/11/2026 — icône propre

- Icône de Scriptorium à la place de celle du socle : une lettrine « S » sépia en EB Garamond (tracée en chemin, sans dépendre d'une police installée), à côté de lignes de texte, sur le fond sombre commun. `icone.svg`, `icone-180.png` et `icone-512.png` ; c'est elle que l'Anneau affiche sur la tuile.

## 0.2.3 — 14/11/2026 — EPUB lisible par Comptoir

Le livre de cocktails sera importé dans Comptoir (l'appli des cocktails). Comptoir découpe un EPUB en recettes : un titre (`h1`–`h3`), les ingrédients (liste, ou lignes qui commencent par une quantité), puis la préparation ; il garde la page d'origine de chaque recette.

- **Les pages sont regroupées en fichiers qui commencent à un titre** : une recette qui passe d'une page à l'autre n'est plus coupée en deux fichiers. Les repères de page restent dans le fil du texte. Les identifiants sont propres à chaque page, pour ne jamais se répéter dans un même fichier.
- **Les lignes d'ingrédients deviennent une vraie liste** (« 45 ml de tequila », « 1 trait de bitters », « Compléter avec du champagne ») ; les autres lignes (« VERRE : coupe ») restent des paragraphes.
- Test : une recette sur deux pages, ingrédients en liste, deux repères de page dans le même fichier, aucun identifiant en double.

## 0.2.2 — 14/11/2026 — Mistral donne les numéros de page, EPUB d'essai, pages de l'original dans l'EPUB

Constat sur le premier vrai livre : même corrigée, la lecture locale des numéros reste peu sûre. Demande de l'utilisateur : tout faire lire par Mistral, y compris le numéro de page, et pouvoir regarder un EPUB partiel.

- **La lecture par Mistral part dès la découpe**, sans attendre l'inventaire. Le numéro imprimé est repéré dans le texte rendu (une ligne qui n'est qu'un nombre : « 72 », « — 72 — », « Page 72 » ; le dernier l'emporte). Il remplace celui de Tesseract, sauf un numéro corrigé à la main. L'inventaire des pages manquantes est recalculé après chaque lecture.
- **EPUB d'essai** : seulement les pages déjà lues, à fabriquer à tout moment, même pendant la lecture. Il n'est jamais déposé dans Grimmory.
- **Pages du livre papier dans l'EPUB** : un repère discret « p. 72 » en tête de chaque page, et la liste des pages EPUB 3 (`page-list`), que KOReader sait utiliser pour afficher les numéros de l'original.
- **Le dépôt dans Grimmory attend l'inventaire confirmé** (le livre déposé doit être complet, ou accepté tel quel).
- Tests : numéro repéré dans le texte de Mistral, numéros de Mistral et pages manquantes, numéro corrigé à la main gardé, EPUB d'essai, liste des pages, archive EPUB valide.

## 0.2.1 — 14/11/2026 — numéros de page mieux lus

Constat sur le premier vrai livre : la page imprimée 72 était lue « 2 ». Dans ce livre de cocktails, la marge porte un index de lettres A à Z, et le numéro est un petit chiffre dans le coin en bas. Avec la liste blanche de chiffres, Tesseract changeait le « Z » en « 2 ».

- Seule la **dernière ligne d'encre** du bas de la page est lue (la première du haut, à défaut). Une ligne de texte (plus de trois mots, ou un bloc large de 30 % de la page) n'est pas prise pour une ligne de numéro.
- Un nombre n'est gardé que si une **lecture libre** (sans liste blanche) le confirme.
- Les bords noirs du scan ne comptent plus comme de l'encre ; la bande lue passe de 9 à 12 % de la hauteur.
- **« Relire les numéros »** : relit les numéros d'un livre déjà découpé, sans redécouper le PDF. Disponible avant la lecture par Mistral ; les numéros corrigés à la main sont remplacés, les pages écartées le restent.
- Tests : page à index de marge (numéro dans le coin, « Z » ignoré, « 5 ml » de la dernière ligne ignoré), relecture des numéros.

## 0.2.0 — 14/11/2026 — première livraison (import, inventaire, lecture, EPUB, Grimmory)

- **Import d'un livre déjà scanné**, par morceaux de 8 Mo :
  - reprise après une coupure, sans morceau en double ni trou ;
  - place disque vérifiée avant l'envoi.
- **Découpe en pages** sur le NAS (200 points par pouce), en tâche de fond qui reprend après un redémarrage.
- **Inventaire** :
  - numéros imprimés lus en local par Tesseract ;
  - pages manquantes montrées à leur place, trous à vérifier, pages en double, pages sans numéro ;
  - numéro corrigé d'un clic, page écartée ou remise ;
  - confirmation à la main.
- **Lecture par Mistral OCR** :
  - sur un clic, coût estimé affiché avant ;
  - arrêt immédiat si la clé est refusée ou le crédit épuisé ;
  - une page rendue de façon douteuse est marquée et entre dans le livre en image.
- **Fabrication** :
  - EPUB 3 recomposé : une section par page, numéros de page et lettres de marge retirés, illustrations replacées, table des matières par les titres ;
  - PDF d'archive des images de pages.
- **Dépôt dans Grimmory** : l'EPUB seul, jamais par-dessus un fichier existant, noté au journal.
- **Écrans** : Livres (lettrine sépia en EB Garamond), un livre en trois étapes (pages, lecture, livre), Connexion (Mistral, Grimmory, dossier de données), Réglages (journal).
- Lecture seule : rien n'est envoyé à Mistral et rien n'est déposé dans Grimmory.
- Retiré du socle : l'écran Synthèse et la bibliothèque de graphiques.
- Tests :
  - chemin complet d'un livre avec faux Mistral, inventaire réel par Tesseract, client Mistral, lecture seule, clé refusée ;
  - écran sur PC et iPhone (`tools/demo.py`) ;
  - en CI : Tesseract et Playwright.

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
