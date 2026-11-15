# Journal des versions — Scriptorium

## 0.4.2 — 15/11/2026 — numéro de page dans l'écran de la page

- L'écran de relecture d'une page permet de changer son numéro imprimé (« Enregistrer le numéro » ; vide : sans numéro), avec son origine (« posé à la main » ou « lu par Mistral »), et d'écarter la page ou de la remettre dans le livre. Le titre et les boutons précédente/suivante suivent aussitôt.
- Un numéro qui n'est pas un nombre est refusé proprement (422 au lieu d'une erreur du serveur).
- Tests : 70 (numéro non numérique, numéro changé depuis l'écran de la page).

## 0.4.1 — 15/11/2026 — tuiles du bilan cliquables

Demande de l'utilisateur, qui lisait « À vérifier : rien » comme « rien à vérifier avec le PC ».

- Les tuiles du bilan des pages filtrent la grille : un clic ne montre que les pages manquantes (avec leur bouton « Prendre »), les trous à vérifier (et les pages qui les bordent), les pages en double, les pages sans numéro lu ; un second clic, ou « Tout montrer », montre tout. Une tuile vide n'est pas cliquable.
- « À vérifier » devient « Trous à vérifier » : il s'agit de la numérotation, pas du texte.
- Nouvelle tuile « Mots à relire (PC) » : les pages signalées par la contre-lecture, ou l'avancement du PC (« PC : 40 faites, 260 en attente »), ou « pas de PC ».
- Test d'écran du filtre (69 tests).

## 0.4.0 — 15/11/2026 — fiche par l'ISBN, couverture, PDF A5

- **Fiche du livre** : éditeur, année et ISBN en plus du titre et de l'auteur (plusieurs auteurs séparés par des virgules). L'ISBN est vérifié (clé de contrôle) et gardé en ISBN-13 ; un ISBN-10 est converti.
- **Chercher la fiche par l'ISBN** (`app/notice.py`) : l'ISBN tapé, ou à défaut celui repéré dans le texte lu des 12 premières et 8 dernières pages (page de copyright, dos). Recherche au catalogue général de la BnF (API SRU, critère `bib.fuzzyISBN`), puis sur Open Library. La fiche trouvée est **proposée** (« Reprendre dans la fiche »), jamais enregistrée d'office. Lecture seule ; `SCRIPTORIUM_RECHERCHE_WEB=non` coupe la recherche. Le code-barres lu à l'iPhone n'est pas fait : l'ISBN se tape ou se trouve dans le texte.
- **Couverture** : « Prendre comme couverture » sur n'importe quelle page (par défaut : la première page gardée). Elle sert à l'EPUB (vraie couverture, vue par Grimmory et la liseuse) et au PDF.
- **EPUB** : ISBN (`urn:isbn`), éditeur, année, un `dc:creator` par auteur, mention de la recomposition par Scriptorium.
- **PDF A5 soigné** (`app/pdf_livre.py`, WeasyPrint) : même texte que l'EPUB, en EB Garamond (polices incluses, licence OFL) ; couverture pleine page, page de titre, sommaire avec numéros de page, titre courant et folio, numéro de la page du livre papier en marge, page gardée en image sur sa propre page, titres jamais seuls en bas de page, listes d'ingrédients non coupées, colophon. Fabriqué en tâche de fond (« Mettre en page un PDF A5 », puis « PDF A5 » à télécharger). Le PDF d'archive des images de pages reste à côté. Le PDF A5 n'est pas déposé dans Grimmory (une seconde fiche du même livre).
- **Ingrédients** : « Complétez avec… » est reconnu comme une ligne d'ingrédient (avant, seul « Compléter » l'était, et la liste entière restait en paragraphe), dans l'EPUB comme dans le PDF.
- Image Docker : pango et harfbuzz pour WeasyPrint (environ 40 Mo de plus).
- Tests : 68 au total (ISBN, BnF et Open Library simulées, recherche coupée, fiche refusée si ISBN faux, métadonnées et couverture de l'EPUB, PDF A5 au format A5 avec sommaire, repères de page, page en image et ISBN, écran de la fiche et de la couverture).

## 0.3.1 — 15/11/2026 — contre-lecture par le PC (fin de la 0.3)

- **Contre-lecture par Marker sur le PC** : nouveau dossier `pc/` (`calcul.yml` pour Docker Desktop, `calcul.py`, `Dockerfile`, `LISEZMOI.md`). Le conteneur demande une page au NAS toutes les 30 s, la lit avec Marker 2.2 sur le processeur (mode « fast », modèles chargés une fois et gardés dans un volume) et renvoie le texte. Image publiée sur `ghcr.io/baloodusudouest/scriptorium-calcul` par une action à part (seulement quand `pc/` change).
- **Porte du PC** (`/calcul/travail`, `/calcul/pages/…`) : hors session, gardée par son propre jeton `SCRIPTORIUM_JETON_CALCUL` (comparaison à temps constant) ; jeton vide : porte fermée (404). Le PC ne peut que prendre une page et rendre sa lecture. Une page prise et jamais rendue (PC éteint en route) est reproposée au bout de 15 minutes. Les pages déjà lues par Mistral passent en premier.
- **Mots à relire** (`app/comparaison.py`) : le texte de Mistral et celui de Marker sont comparés mot à mot (ponctuation, mise en forme, numéros de page, lettres de marge et césures ignorés). Seules les substitutions courtes (1 à 4 mots de chaque côté) deviennent des mots à relire ; si les deux lectures se ressemblent trop peu (accord < 0,5), toute la page est signalée. La comparaison se refait à chaque nouveau texte (lecture Mistral, contre-lecture, texte corrigé).
- **Écran de relecture** : au-dessus du texte, la liste des mots à relire (« vermouth — Marker lit vermout ») ; toucher un mot le sélectionne dans le texte, « Prendre » met la lecture de Marker à sa place. « Page relue, rien à changer » ou « Enregistrer le texte » sortent la page de la liste. « Page suivante à relire » saute aux pages signalées. La lecture complète de Marker est dépliable sous le texte.
- **Livre** : l'étape 2 dit où en est la contre-lecture et combien de pages sont à relire (« Relire la première ») ; les vignettes signalées portent « n mots à relire ».
- **Connexion** : tuile « PC de calcul » (dernier passage, moteur, pages en attente).
- Une page tournée perd sa contre-lecture, refaite par le PC.
- Tests : 56 au total (comparaison, porte et jeton, PC simulé de bout en bout avec un faux Marker, page abandonnée reproposée, page illisible par le PC, relue ou corrigée, écran des mots à relire sur PC et iPhone). **Marker lui-même n'est pas testé ici** (trop lourd pour la CI) : l'essai réel se fait sur le PC.

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
