# Dossier de Scriptorium — d'un livre scanné à un livre en texte

Écrit le 14/11/2026 à partir du grill (cinq tours). Seul le squelette est codé (0.1.0, copie du socle).

Mis à jour le 14/11/2026 : la carte graphique du PC de calcul est une **AMD Radeon RX 6700 (10 Go)**. La sonde décidera entre deux voies : calcul sur processeur dans Docker, ou calcul sur la carte par un programme Windows (§ 2, § 6).

## 1. Besoin

L'utilisateur veut transformer un livre papier en **vrai livre numérique** : du texte, pas des images de pages. Le livre fini doit garder la mise en forme (titres, italiques, notes, encadrés, tableaux) ainsi que les photos et illustrations, replacées dans le texte.

OCRmyPDF, l'outil vu au départ, ne fait pas cela : il garde l'image de chaque page et pose un texte invisible dessus. Scriptorium **recompose** le livre.

Décidé au grill :

- **Entrée des pages** : prise à l'iPhone, double page coupée en deux (reprise de Scan Immich), **et** import de PDF ou d'images déjà scannés, par dépôt dans l'appli. Pas de dossier surveillé.
- **Livres visés** : mises en page riches (colonnes, encadrés, tableaux, images), livres de cuisine, beaux livres.
- **Résultat** : un **PDF et un EPUB recomposés**. Le PDF sert d'archive, l'EPUB de lecture (liseuse, Grimmory).
- **Images** : découpées, redressées, débarrassées de la trame d'impression, gardées **dans le livre seulement** (pas d'envoi dans Immich).
- **Calcul** : d'abord sur le **PC**, dans un conteneur Docker Desktop. Le NAS garde les livres, la file d'attente et l'interface.
- **Pages douteuses** : signalées. Pour chacune, l'utilisateur **corrige à la main** ou **clique pour l'envoyer à Mistral OCR**, avec le coût affiché. Rien ne part en ligne sans son clic.
- **Pages trop complexes** (schéma annoté, double page très graphique) : décision à la relecture. On recompose quand même, ou on garde la page en image, avec son texte cherchable dans le PDF.
- **Relecture ciblée** : sur PC, image et texte côte à côte ; sur iPhone pour les petites corrections.
- **Fiche du livre** : ISBN lu dans le livre (page de copyright ou code-barres), fiche cherchée à la BnF puis sur Open Library, puis corrigée à la main. La couverture est la photo de la couverture.
- **Langue** : français par défaut, autre langue réglable par livre.
- **Volume** : quelques livres par an, donc une file simple suffit.
- **Sortie** : dépôt dans le `bookdrop` de **Grimmory**, plus un bouton de téléchargement.
- **Home Assistant** : rien.
- **Livraison** : tout d'un bloc (voir § 6 et la question au conseil).

## 2. Technique

### Le chemin d'une page

```
Prise iPhone / import PDF ─► NAS : page brute rangée, livre en file
                                   │
              PC allumé ◄──────────┘  (le PC vient chercher le travail)
                 │
   1. Préparer : coupe de la double page au pli, redressement de la courbure,
                 recadrage, inclinaison
   2. Analyser : blocs de la page (titre, paragraphe, note, légende, encadré,
                 tableau, image, en-tête courant, numéro de page) + ordre de lecture
   3. Lire     : texte de chaque bloc, avec italiques et gras, confiance par mot
   4. Nettoyer : césures de fin de ligne recollées, typographie française
                 (espaces insécables), images détramées
                 │
                 ▼
NAS : page « lue » (blocs + texte + confiance) ─► À relire si douteuse
                 │
Relecture : corriger à la main / Mistral OCR sur un clic / garder en image
                 │
Assemblage (NAS) : chapitres, notes reliées, table des matières ─► EPUB + PDF ─► bookdrop
```

### Côté NAS (conteneur `scriptorium`)

- **FastAPI + SQLite + Svelte**, parti du socle :
  - mot de passe commun et cookie de l'Anneau ;
  - `/health` ;
  - mode lecture seule (`SCRIPTORIUM_LECTURE_SEULE`) ;
  - pas de mise à jour automatique par Watchtower.
- **Stockage**, dans le dossier de données `livres/<id>/` :
  - `brutes/` : pages telles que prises ;
  - `pages/` : pages préparées ;
  - `images/` : illustrations découpées ;
  - `sortie/` : livres fabriqués.

  Les pages restent tant que le livre n'est pas supprimé, pour pouvoir relancer un calcul avec un meilleur modèle.
- **Porte du PC** : préfixe `/calcul/…`, avec son propre jeton (`SCRIPTORIUM_JETON_CALCUL`, même valeur dans le `.env` du PC). Le PC demande une page, la renvoie lue, et ne peut rien faire d'autre. Jeton vide : porte fermée.
- **Mistral OCR** : appelé depuis le NAS, uniquement sur un clic. La clé (`SCRIPTORIUM_MISTRAL_CLE`) reste dans la stack. Le coût estimé s'affiche avant l'envoi, le total dépensé dans Réglages. Clé vide : le bouton n'apparaît pas.
- **Assemblage** : l'EPUB 3 est construit à partir des blocs :
  - une section par chapitre ;
  - notes en liens aller-retour ;
  - tableaux en vrais tableaux ;
  - encadrés stylés ;
  - images en figures avec légende.

  Le PDF est composé à partir du même HTML (WeasyPrint, format A5, police à empattements libre). Une page gardée en image y est insérée avec son texte invisible.
- **Grimmory** : le dossier `bookdrop` est monté en écriture (`SCRIPTORIUM_BOOKDROP`), et les fichiers sont nommés « Auteur - Titre ». C'est la seule écriture hors du dossier de l'appli : elle est journalisée, et on n'écrase jamais un fichier existant.
- **Fiche du livre** : ISBN repéré dans le texte de la page de copyright (avec contrôle de la clé), ou code-barres lu à l'iPhone. Recherche à la BnF (SRU), puis sur Open Library.
- **HTTPS pour la caméra** : Tailscale Serve sur un port libre. Vérifier `tailscale serve status` avant, et ajouter la redirection à la tâche commune qui regroupe toutes les redirections : un port ne sert qu'un service.

### Côté iPhone (prise)

Reprise de Scan Immich :

- caméra en direct et détection du livre ouvert (OpenCV.js) ;
- **prise automatique quand l'image est stable** ;
- indicateur de définition, prise bloquée si la page est trop petite.

Nouveautés :

- repérage du pli au milieu, pour couper en deux pages ;
- la correction de la courbure se fait au PC, pas dans le téléphone ;
- les pages restent dans IndexedDB jusqu'à l'envoi. Dans Scan Immich, une prise se perdait si iOS fermait l'appli.

### Côté PC (conteneur « calcul »)

`pc/calcul.yml` dans le dépôt, lancé dans Docker Desktop. Il interroge le NAS toutes les 30 s et fait le travail en attente.

**La carte du PC est une AMD Radeon RX 6700 (10 Go).** Docker Desktop sous Windows ne donne accès qu'aux cartes NVIDIA : dans le conteneur, le calcul se fait donc **sur le processeur**. Deux voies, départagées par la sonde :

- **Voie A, processeur dans Docker** : une seule installation, mais plus lent. Avec quelques livres par an, un livre peut se calculer en une nuit.
- **Voie B, carte graphique par un programme Windows** : un modèle de vision servi par LM Studio ou Ollama (accélération Vulkan ou ROCm sur la RX 6700), que le conteneur appelle sur le réseau local. Plus rapide, peut-être meilleur sur les mises en page riches, mais c'est une installation de plus. Le support de la RX 6700 est à vérifier dans la sonde.

**Le modèle sera choisi par la sonde**, parmi :

| Candidat | Ce qu'il fait | Voie |
|---|---|---|
| Marker (moteur Surya) | Page → texte structuré, images, tableaux | A (processeur, lent) |
| Docling (IBM) | Analyse de mise en page et tableaux, sortie structurée | A |
| MinerU (mode pipeline) | Spécialisé dans les mises en page riches | A |
| PaddleOCR PP-StructureV3 | Mise en page + lecture, bon sur les tableaux | A |
| Modèle de vision local (famille Qwen VL ou équivalent, tenant dans 10 Go) | Page → texte structuré par un modèle de vision | B (carte graphique) |

Redressement de la courbure : méthode « page-dewarp » (modèle de surface cylindrique), ou celle du modèle retenu s'il en a une.

**Confiance** :

- Un **mot** est douteux si sa confiance de lecture est basse, ou s'il n'est pas dans le dictionnaire français (Hunspell). Exception : un nom propre répété dans le livre.
- Une **page** est douteuse si :
  - la proportion de mots douteux dépasse un seuil ;
  - l'ordre de lecture est incertain (colonnes, encadrés) ;
  - ou elle contient un tableau.
- Une page est **complexe** si les images et le texte s'entremêlent au-delà d'un seuil.

Un modèle de vision (voie B) ne donne pas toujours de confiance par mot. Il faudrait alors s'appuyer davantage sur le dictionnaire, ou comparer avec une lecture classique.

## 3. Parcours des clics et des écrans

Cinq entrées. Rail à gauche sur PC, pilule d'icônes en bas sur iPhone.

**Livres** (écran d'ouverture) : la bibliothèque des livres. Chaque livre est une tuile avec sa couverture, son titre et son état :

- en prise ;
- en calcul (n pages sur N) ;
- à relire (n pages) ;
- prêt ;
- déposé dans Grimmory.

Le bouton plein « Nouveau livre » propose **Prendre à l'iPhone** ou **Importer un PDF ou des images**, puis la langue.

**Un livre ouvert** :

- la fiche (titre, auteur, année, éditeur, ISBN, couverture), proposée par l'ISBN et modifiable ;
- la bande des pages en vignettes, colorées selon leur état ;
- « Recalculer », pour une page ou tout le livre ;
- l'aperçu de l'EPUB ;
- « Fabriquer le livre », actif quand plus rien n'attend ;
- « Déposer dans Grimmory » et « Télécharger PDF / EPUB ».

**Prendre** (caméra, iPhone) : le livre ouvert devant l'objectif, contour et pli dessinés en direct, prise automatique, compteur de pages. La pilule s'efface pendant la prise : rien entre le pouce et le geste répété. On termine avec « Envoyer au Scriptorium ».

**À relire** : des tuiles par type, avec leur nombre : mots douteux, pages à l'ordre incertain, tableaux à vérifier, pages complexes.

Une page ouverte montre **l'image à gauche et le texte recomposé à droite**. Les mots douteux sont surlignés en sépia. Un clic sur un mot met en avant sa zone dans l'image. Gestes :

- corriger le mot ;
- « C'est bon » ;
- « Relire par Mistral (≈ 0,002 €) » ;
- pour une page complexe, « Garder en image » ou « Recomposer ».

Sur iPhone : un mot douteux à la fois, avec l'extrait de l'image au-dessus ; on valide ou corrige au pouce.

**Connexion** : trois tuiles avec voyant :

- **PC de calcul** : vu il y a n minutes, modèle utilisé, pages en attente ;
- **Mistral OCR** : clé présente, crédit dépensé ce mois ;
- **Grimmory** : dossier `bookdrop` accessible en écriture.

Gestes : **Vérifier**, et pour le PC, « Mode d'emploi ».

**Réglages** : langue par défaut, seuils des mots douteux, format du PDF (A5 / A4), police, journal des écritures (dépôts dans Grimmory), total Mistral, version, déconnexion.

## 4. Design

Format commun : toujours sombre, neutres chauds, Inter, titres d'écran grands et fins.

**Couleur : sépia papier ancien `#c4a07a`**. Son ton brun la distingue de l'or pâle de l'Anneau. Elle porte le bouton plein de chaque bloc, l'onglet actif, les compteurs et les mots surlignés.

**Signature : la lettrine.** Le titre de chaque livre s'ouvre sur une grande initiale en sépia, dans une police à empattements de copiste (EB Garamond). Dans la relecture, le texte recomposé est lui aussi en EB Garamond : on lit déjà le livre tel qu'il sortira.

## 5. Schéma de données

```
livres     id, titre, auteur, annee, editeur, isbn, langue, source (iphone|import),
           etat (prise|calcul|relecture|pret|depose), couverture, cree_le, depose_le
pages      id, livre_id, rang, brute, preparee, etat (attente|calcul|lue|douteuse|complexe|validee),
           rendu (texte|image), moteur (local|mistral|main), confiance, cout_mistral
blocs      id, page_id, rang_lecture, type (titre1|titre2|paragraphe|note|legende|encadre|tableau|image|entete|numero),
           cadre (x,y,l,h), contenu (texte riche), confiance
mots_doute id, bloc_id, position, lu, propose, issue (corrige|accepte|mistral)
journal    le, quoi (depot_grimmory|appel_mistral|suppression_livre), livre_id, detail
```

L'en-tête courant et le numéro de page sont gardés dans les blocs, mais retirés à l'assemblage. Le numéro sert à vérifier qu'aucune page ne manque.

## 6. Plan d'implémentation

Livraison choisie : **une seule** (1.0.0). Les étapes ci-dessous sont l'ordre de travail interne, testé à chaque pas, pas des versions publiées.

0. **Sonde** (avant le conseil), sur 3 ou 4 pages riches d'un vrai livre : colonnes, encadré, tableau, photo, et une double page prise à l'iPhone pour juger la courbure.
   - Chaque page passe dans chaque candidat de la voie A (processeur, dans Docker), dans un modèle de vision de la voie B (LM Studio ou Ollama sur la RX 6700), et dans Mistral OCR.
   - Mesures : texte juste, ordre de lecture, tableaux, images découpées, temps par page sur ce PC.
   - Pour la voie B, on vérifie d'abord que LM Studio ou Ollama accélère bien la RX 6700.
   - Le rapport choisit le modèle et la voie.
1. Socle copié, couleur, cinq entrées, livres et pages en base, import d'un PDF.
2. Conteneur PC : porte `/calcul`, préparation, analyse, lecture, retour des blocs. Si la voie B est retenue : appel au programme Windows, et mode d'emploi pour l'installer.
3. Assemblage EPUB + PDF, puis dépôt dans Grimmory (lecture seule respectée, aucun écrasement).
4. Relecture PC, puis iPhone ; pages complexes ; Mistral sur un clic.
5. Fiche par l'ISBN.
6. Prise iPhone en doubles pages, puis courbure au PC.
7. Essai complet sur un vrai livre, ajout à la stack, Tailscale Serve, tuile dans l'Anneau.

**Tests** :

- Le dépôt est public : aucune page de livre sous droits. Les pages de test viennent de livres du domaine public (Gallica).
- Faux NAS pour le PC, faux Mistral, faux serveur de modèle de vision.
- Un test fige ce qui est écrit dans `bookdrop`. Il prouve aussi que rien n'y est écrit en lecture seule, ni par-dessus un fichier existant.
- Tests d'écran sur PC et sur iPhone.

## Décisions prises après la sonde (14/11/2026)

Compte rendu : [`sonde.md`](sonde.md). Ce qui change par rapport au texte ci-dessus :

- **Lecture : Mistral d'abord, le PC en contre-lecture.** Toutes les pages partent chez Mistral OCR (environ 0,30 à 0,60 € pour un livre de 300 pages), qui donne la structure et le texte. Le PC relit chaque page avec Marker (voie A, processeur). Les mots qui diffèrent entre les deux lectures deviennent les mots à relire. Ce choix remplace « PC d'abord, Mistral sur un clic » : sur une page propre, Mistral est nettement meilleur, et là où il se trompe de façon plausible, Marker lit juste. Le PC éteint ne bloque pas un livre : les pages attendent seulement leur contre-lecture.
- **Prise page par page** (le téléphone dans le sens de la page, page entière dans le cadre) au lieu de la double page : les fiches denses perdent trop de netteté en double page. Le tour 2 de la sonde n'est pas fait ; la prise se réglera à l'essai.
- **Import d'un livre déjà scanné, même gros** (un PDF de 400 Mo est attendu) :
  - l'envoi se fait par morceaux, écrits sur le disque au fil de l'eau, avec reprise si la connexion coupe ; rien n'est gardé en mémoire ;
  - le PDF est découpé en pages sur le NAS.
- **Inventaire des pages manquantes** : Scriptorium lit le numéro imprimé de chaque page et liste :
  - les pages manquantes ;
  - les trous à vérifier ;
  - les pages en double ;
  - les pages sans numéro.

  Chaque page manquante devient une tâche « à prendre » dans le livre. On la photographie à l'iPhone et elle **s'insère à sa place**, d'après son numéro. Une page en double peut être écartée. L'outil existe déjà dans la sonde (`sonde/outils/inventaire.py`).
- **Voie B** (modèle de vision sur la carte AMD) : pas mesurée, mise de côté. Elle pourra remplacer Mistral plus tard si elle s'en approche.

## Décisions prises après le conseil (14/11/2026)

Avis complet : [`conseil.md`](conseil.md). Ce que l'utilisateur a retenu :

- **Trois livraisons au lieu d'une.** Le squelette porte déjà le numéro 0.1.0, donc on compte à partir de 0.2 :
  - **0.2** : import du PDF, inventaire des pages manquantes confirmé à la main, lecture par Mistral, EPUB recomposé simple et PDF d'archive, dépôt dans Grimmory ;
  - **0.3** : écran de relecture image/texte, contre-lecture Marker sur le PC, choix page par page entre « recomposer » et « garder en image » ;
  - **0.4** : prise iPhone page par page avec insertion des pages reprises, fiche par ISBN, PDF A5 soigné.
  - *Ajusté le 15/11/2026 (demande de l'utilisateur)* : la 0.3.0 livre la relecture et le choix de rendu, plus la reprise d'une page manquante à l'iPhone (une photo à la fois, rangée par son numéro) avancée depuis la 0.4. La contre-lecture Marker suit en 0.3.1.
  - *Livré le 15/11/2026* : 0.3.1 (contre-lecture Marker sur le PC, porte `/calcul` à jeton, mots à relire : substitutions de 1 à 4 mots entre les deux lectures, page entière si l'accord est sous 0,5) et 0.4.0 (fiche par l'ISBN, BnF puis Open Library, proposée seulement ; couverture choisie ; PDF A5 par WeasyPrint en tâche de fond). Le code-barres ISBN suit en 0.4.3 (photo lue sur le NAS). Reste hors livraison : la prise d'un livre entier à l'iPhone.
- **Pas de test préalable** : la 0.2 sert elle-même de test, sur le PDF de 400 Mo.
- Avis du conseil suivis dans la 0.2 :
  - l'appel à Mistral tient dans une seule fonction (`app/mistral.py`) ;
  - une page rendue de façon douteuse entre dans le livre en image ;
  - le dépôt dans Grimmory ne porte que l'EPUB, pour éviter une seconde fiche du même livre ;
  - l'archive des images de pages est fabriquée à côté.
- **Livre recomposé gardé** : le président du conseil l'a préféré au fac-similé, pour la lecture sur la liseuse.
- **Écarté pour l'instant** :
  - EPUB à mise en page fixe ;
  - voie B ;
  - fiches de recettes vers Mealie : les quantités lues ne sont pas vérifiées.

## Questions ouvertes pour le conseil

1. **Une seule livraison** pour une appli de cette taille, contre la règle du format commun (« ce qui protège d'abord »). Le risque est faible, puisque Scriptorium n'écrit que des fichiers neufs dans `bookdrop`. Faut-il quand même découper ?
2. **Double page à l'iPhone** : la courbure près du pli abîme-t-elle trop la lecture et les images des mises en page riches ? Faut-il garder une prise page par page en secours ?
3. **EPUB et mise en page riche** : colonnes et encadrés deviennent linéaires dans un EPUB. Faut-il un réglage par livre (EPUB à mise en page fixe pour un beau livre), ou s'en tenir au choix de la page gardée en image ?
4. **Seuils de doute** : comment éviter que la relecture « ciblée » devienne une relecture de chaque page sur les livres difficiles ? Et comment repérer les mots douteux avec un modèle de vision (voie B), qui ne donne pas de confiance par mot ?
5. **PDF recomposé ou fac-similé** : le recomposé a été choisi. Faut-il garder en plus, dans le dossier du livre, un PDF des images de pages pour l'archive ?
6. **Dépendance à Mistral** : toutes les pages d'un livre partent en ligne. Que faire si l'API change, augmente ses prix ou ferme ? Le PDF importé de 400 Mo pose-t-il un souci de place ou de temps sur le NAS ?
7. **Que manque-t-il ?** Par exemple : notes de bas de page sur deux pages, index, sommaire d'origine, lettrines et ornements, livres anciens en typographie d'époque.
