# Scriptorium — conseil (14/11/2026)

Dossier soumis : docs/dossier.md (avec les décisions prises après la sonde) et docs/sonde.md. Cinq conseillers, relecture croisée anonyme, président.

## Réponses

**Réponse A :**
Non, pas en une seule livraison 1.0.0. Le dossier décrit le produit final, pas ce que tu codes lundi matin. Plusieurs semaines de travail pour quelques livres par an, avec une chaîne de lecture qui n'a jamais tourné de bout en bout : c'est le scénario classique de l'appli finie à 70 % puis abandonnée.
Lundi matin : prends UN vrai livre de fiches, scanné bien à plat, sans iPhone en direct, sans web app, sans inventaire des pages. Script de 150 lignes : PDF → Mistral OCR → Markdown → EPUB par Pandoc → dépôt dans le bookdrop. Ouvre le résultat dans Grimmory et lis-le pour de vrai. Tu sauras en un week-end si le texte de Mistral, à lui seul, donne un livre lisible et combien d'erreurs tu repères en lisant.
Ensuite seulement, dans cet ordre, chaque étape livrée et utilisée : 0.1 le script + fiche ISBN ; 0.2 l'écran de relecture image/texte sur PC (c'est lui qui protège des erreurs invisibles, pas la contre-lecture) ; 0.3 la contre-lecture Marker seulement si la 0.2 montre que tu rates des erreurs — pour chaque bloc de Mistral, chercher le passage approchant dans le texte brut de Marker (difflib), signaler l'écart ; Marker vide = relecture obligatoire ; 0.4 la prise de vue iPhone et les pages manquantes.
À couper : la double page, l'EPUB à mise en page fixe (page compliquée = image + texte cherchable), la voie B AMD.
PDF de 400 Mo : le découper sur le PC avant l'envoi, pas sur le NAS. Archive des images de pages : oui, gratuit (img2pdf). Mistral : isoler l'appel dans une seule fonction.

**Réponse B :**
Le dossier pense trop petit sur ce qui compte et trop gros sur ce qui ne compte pas. La vraie valeur n'est pas l'EPUB recomposé, c'est le corpus structuré. Un livre de cocktails ou de cuisine est une base de fiches. Mistral rend déjà la structure : sortir en plus du PDF et de l'EPUB un JSON de fiches (titre, ingrédients, quantités, étapes, photo, page source). Mealie est déjà dans la stack : chaque recette relue y entre directement, cherchable par ingrédient, listes de courses. Les cocktails peuvent avoir la même base (« que faire avec ce qui reste dans le bar ? »), voire une carte pour les clients de la chambre d'hôte ; association avec les vins du domaine familial.
La contre-lecture est un actif : chaque mot corrigé est une paire erreur → vérité. Garder ce journal : au bout de trois livres, un lexique propre qui corrige en amont, et le jeu de test pour mesurer enfin la voie B. La dépendance à Mistral devient remplaçable sur preuve.
Le module « page manquante → tâche iPhone » est un outil générique pour réparer des scans (Paperless, archives familiales).
Donc oui, découper, mais pas pour rapetisser : 1.0 = lecture + relecture + JSON de fiches vers Mealie ; 1.1 = EPUB/PDF soigné.

**Réponse C :**
Non, pas prêt. Défaut de fond : la contre-lecture ne peut pas tenir sa promesse. Mistral se trompe surtout là où Marker est faible aussi (petit texte, pages denses, photos de travers) : soit tout devient « mot à relire », soit rien n'est signalé et « jus d'oreilles » passe. Aligner deux textes de structures différentes est un projet de recherche, pas une fonction de V1.
La sonde ne prouve presque rien : 4 photos ratées et une capture de 560 px. Aucun chapitre relu contre le vrai texte, aucun taux d'erreur mesuré, voie B jamais mesurée.
L'EPUB recomposé est un leurre pour ces livres : un livre de cocktails à deux colonnes linéarisé est pire que la page d'origine. Le bon défaut est l'inverse : la page gardée en image avec texte cherchable, la recomposition en exception.
Trop gros pour quelques livres par an : caméra en direct, envoi par morceaux de 400 Mo, inventaire, ISBN, relecture iPhone. Tout en une 1.0.0 contre ta propre règle garantit qu'aucune partie ne sera bien testée.
0.1 : import PDF → Mistral → PDF en images de pages avec texte cherchable → Grimmory. Avant tout autre code : relire à la main un chapitre complet contre l'original et compter les erreurs de Mistral seul. Ensuite seulement, si les chiffres le justifient : contre-lecture, EPUB recomposé, prise de vue iPhone.

**Réponse D :**
Décalage : plusieurs semaines de code pour quelques livres par an. Pourquoi une appli, pas un script lancé à la main livre par livre ? La question n'est jamais posée.
Il manque une définition de « livre réussi » : une recette lisible sur liseuse ? une copie fidèle de la page ? Les questions 3 et 5 tournent autour sans trancher ; tant que ce n'est pas tranché, l'architecture flottera.
La sonde : les vraies photos d'iPhone donnent des résultats mauvais partout ; une seule page bien droite donne un bon résultat. Or l'entrée choisie, ce sont des photos d'iPhone : la prise de vue est le vrai problème, avant la lecture.
« Erreurs invisibles » : la contre-lecture ne rattrape une erreur que si Marker lit juste au même endroit, alors qu'il écrase la structure ; comment aligner deux sorties de formes différentes ? Toute la promesse de qualité repose dessus.
Vocabulaire opaque (grill, sonde, bookdrop, voie B).
Verdict : non. D'abord faire un livre complet à la main avec des scripts, écrire en une phrase ce qu'est un livre réussi, puis décider ce qui mérite d'être automatisé.

**Réponse E :**
Non, parce qu'il ne répond pas à la bonne question. Qu'est-ce que Julien veut faire de ces livres ? Retrouver une recette, chercher un cocktail par ingrédient, feuilleter sur tablette. Pour un livre de cuisine/cocktails, la valeur est dans la page composée (photos, encadrés, deux colonnes). Un EPUB recomposé détruit cette valeur puis dépense des semaines à la reconstruire imparfaitement.
La ressource rare est l'attention de Julien par livre. La contre-lecture déplace les erreurs invisibles sans les résoudre : deux moteurs qui se trompent pareil passent ; deux structures différentes ne s'alignent pas mot à mot ; on construit une machine à fabriquer de la relecture.
Proposition : 1.0.0 = fac-similé fidèle : prise de vue iPhone, inventaire des pages manquantes et tâches « à prendre » (le vrai problème difficile, bien pensé), PDF des images de pages avec couche de texte cherchable (Mistral suffit), fiche ISBN, dépôt dans Grimmory. L'image fait foi, le texte sert à chercher : aucun mot inventé ne devient visible. Tranche les questions 3, 5, 7.
Avant toute recomposition, faire un livre entier à la main avec Mistral et chronométrer la correction. Recomposition = 2.0 facultative, livre par livre. L'appli devient assez petite pour une seule livraison.

## Relectures

Correspondance : A = L'Exécutant, B = L'Expansionniste, C = Le Contradicteur, D = Le Candide, E = Le Penseur des premiers principes.

Relecture 1 : Plus forte E (fac-similé, image fait foi, mot inventé jamais visible ; garde les pages manquantes ; tranche Q3, 5, 7 ; C même constat moins construit ; A concrète mais son script Pandoc produit justement l'EPUB recomposé). Angle mort B (élargit ; les fiches JSON tirées de Mistral enverraient des quantités inventées dans Mealie sans image pour vérifier). Raté : Mistral OCR rend du Markdown sans position de chaque mot (à vérifier) : un PDF cherchable calé sur l'image demande ces positions ; OCRmyPDF/Tesseract en local les produit (0.1 = une commande) ; vérifier que Grimmory et la liseuse cherchent dans cette couche ; personne n'a vérifié si ces livres existent déjà en numérique à acheter.

Relecture 2 : Plus forte E (même raisons ; A meilleur complément : script week-end, alignement difflib concret). Angle mort B ; D ne propose rien. Raté : Mistral sans coordonnées par mot → couche locale OCRmyPDF, lente sur le Celeron ; pages envoyées à un tiers contre l'esprit auto-hébergé ; Grimmory indexe-t-il la couche texte des PDF ?

Relecture 3 (sait que Julien a un PDF de 400 Mo incomplet à importer, pages manquantes à rescanner) : Plus forte E (seule à garder l'inventaire des pages manquantes et la reprise iPhone en 1.0, c'est le besoin immédiat ; A repousse les pages manquantes en 0.4 à l'inverse du cas réel). Angle mort B (fiches JSON sans contrôle dans Mealie = quantités inventées dans des recettes qu'on cuisine). Raté : le PDF de 400 Mo n'a pas été sondé (résolution, qualité, ce que Mistral en tire) alors que c'est le premier corpus de test tout trouvé ; les numéros imprimés ne repèrent pas les pages sans numéro → recouper avec le sommaire et confirmer l'inventaire à la main ; une page reprise à l'iPhone n'aura ni cadrage ni taille ni couleurs du scan d'origine → la redresser et la mettre au même format avant insertion.

Relecture 4 (usage réel : PC, iPhone, Kindle KOReader, Grimmory, assistant IA sans mémoire) : Plus forte A (teste le vrai usage : EPUB dans Grimmory lu pour de vrai ; étapes à la taille d'une séance ; protection à l'écran de relecture). Angle mort E et C : « l'image fait foi » oublie la Kindle : une page A5 de fiches denses à deux colonnes en image sur 6 pouces d'encre = zoomer et déplacer sans fin, pénible aussi sur iPhone ; le texte recomposé est ce qui rend ces livres lisibles sur KOReader. Raté : un jeu de pages de référence dans le dépôt (vraies pages + texte exact attendu, test qui mesure le taux d'erreur) pour qu'un assistant sans mémoire juge un changement contre des chiffres ; trajet Grimmory → KOReader (OPDS, reprise) ; PDF et EPUB du même livre : une fiche ou deux doublons dans Grimmory ? ; essayer le CSS de l'EPUB dans KOReader avant de coder l'assemblage.

Relecture 5 : Plus forte E (A bon complément). Angle mort B ; D sans chemin. Raté : droit d'auteur (livres protégés ; copie privée, pas de diffusion : la carte pour les clients de B serait de la contrefaçon ; vérifier si Mistral conserve les pages envoyées) ; coût négligeable, la vraie dépendance est la disponibilité de l'API ; le revirement « PC d'abord » → « tout chez Mistral » contre la logique auto-hébergée n'est pas questionné, et E et C abandonnent le « vrai livre recomposé » explicitement choisi.

## Verdict du président

**Accord** : pas prêt pour une 1.0.0 unique ; sonde trop mince (aucun taux d'erreur mesuré) ; la contre-lecture Mistral/Marker est un signal, pas une garantie ; l'écran de relecture protège ; voie B retirée ; archive des images de pages gardée.

**Divergence tranchée** : le président garde le livre recomposé (choix du grill, lecture sur Kindle KOReader et iPhone) contre le fac-similé proposé par E et C ; une page trop complexe reste en image dans l'EPUB ; pas d'EPUB à mise en page fixe ; pas de fiches JSON vers Mealie pour l'instant (quantités non vérifiées).

**Angles morts** : le PDF de 400 Mo est le vrai premier corpus, jamais sondé ; l'inventaire n'est testé que sur un PDF fabriqué et rate les pages sans numéro (recouper avec le sommaire, confirmer à la main) ; pages reprises à l'iPhone à mettre au format du scan ; positions des mots chez Mistral à vérifier (OCRmyPDF en local sinon) ; jeu de pages de référence dans le dépôt avec taux d'erreur mesuré ; trajet Grimmory → KOReader, doublons PDF/EPUB, CSS à essayer dans KOReader ; droit d'auteur : copie privée seulement, vérifier si Mistral conserve les pages.

**Recommandation** :
- « Mistral d'abord + contre-lecture PC » reste (choix de Julien) : alignement par bloc avec difflib ; Marker vide ou absurde = relecture obligatoire ; qualité jugée sur le taux d'erreur du jeu de référence.
- Trois livraisons :
  - **0.1** : import du PDF (découpé sur le PC), inventaire confirmé à la main, Mistral, EPUB recomposé minimal, Grimmory, lecture sur KOReader ;
  - **0.2** : écran de relecture, contre-lecture Marker, choix page par page recomposer / garder en image ;
  - **0.3** : prise iPhone page par page avec insertion, fiche ISBN, PDF A5 soigné.
- Coupés : double page, EPUB à mise en page fixe, voie B, Mealie. L'appel à Mistral est isolé dans une seule fonction.

**Première chose** : inventaire du PDF de 400 Mo vérifié à la main avec le sommaire. Puis vingt pages envoyées à Mistral et à Marker, deux pages denses corrigées à la main (premier jeu de référence, vrai taux d'erreur), un EPUB brut de ces vingt pages lu sur la Kindle.
