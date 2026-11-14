# Sonde — compte rendu

## Tour 1 (14/11/2026)

**Pages** : quatre photos iPhone de doubles pages, toutes du même livre de cocktails. Le téléphone était tenu en hauteur et le livre ouvert en travers : le texte arrive donc tourné de 90°, avec la table, d'autres livres et des doigts autour. Elles ont été passées **sans redressement** (préparation de la première version).

| Photo | Contenu |
|---|---|
| 1 | Texte courant (avec une liste numérotée) + photo pleine page |
| 2 | Fiches de recettes très denses : petits caractères, gras, verres illustrés, étoiles, deux colonnes par page |
| 3 | Même type de fiches denses |
| 4 | Texte courant en corps moyen, intertitres + photo |

**Temps par photo (double page), sur le PC** :

| Moteur | Temps | Remarque |
|---|---|---|
| Docling (processeur) | 60 à 97 s | |
| Marker (processeur) | 6 à 14 s | |
| Mistral OCR (en ligne) | 5 à 21 s | 4 pages facturées |
| Modèle de vision (RX 6700) | non lancé | |

**Constats** :

- **Docling est inutilisable sur ces photos.** Ordre de lecture brouillé, texte de l'arrière-plan lu (titre d'un autre livre sur la table), mots posés un par ligne.
- **Marker** a totalement échoué sur la photo 1 (9 caractères). Sur les trois autres, il lit les mots le mieux (noms propres justes, marques justes), mais la structure des fiches s'écrase : les ingrédients se retrouvent en paragraphe, et un tableau a été tenté à tort.
- **Mistral** supporte la rotation et rend la meilleure structure : titres, listes, illustrations découpées. Mais il fait **beaucoup d'erreurs de mots sur le petit texte dense** (« whole » pour « whisky », « VASP » pour « VSOP »). Sur la photo 3, sa sortie dérive même vers des **mots inventés et plausibles** (« jus d'oreilles », une marque de voiture à la place d'un vin). C'est le cas le plus dangereux : une erreur qui ne ressemble pas à une erreur, et aucune confiance par mot pour la repérer.
- Sur la **photo 4** (texte courant en corps moyen), Marker comme Mistral sont bons, avec quelques fautes par page.

**Conclusions provisoires** :

1. **La préparation de l'image compte plus que le choix du moteur.** Une page tournée de 90°, avec la table autour, fait échouer deux moteurs sur trois. → Préparation refaite (version 2) :
   - sens de lecture trouvé par Tesseract dans les quatre sens ;
   - recadrage sur le papier ;
   - coupe au pli. Le pli est une bande sombre des deux côtés : une photo sombre pleine page ne l'attire pas.
2. **Une double page ne suffit sans doute pas pour les fiches denses.** Chaque page n'a qu'environ la moitié des pixels de la photo, et le petit texte s'y perd chez tous les moteurs. À mesurer au tour 2 : la même page de fiches en double page, puis seule.
3. **Mistral ne peut pas être cru sur parole.** Il invente sur les pages difficiles, justement celles qu'on lui enverrait en secours. La relecture devra comparer sa sortie à une lecture locale, et signaler les mots qui diffèrent, plutôt que remplacer le texte local par le sien.
4. La voie B (modèle de vision sur la carte AMD) reste à mesurer.

## Tour 1 bis (14/11/2026) : une page scannée à plat

**Page** : une seule page de fiches denses du même livre, à plat et bien droite, sans table autour. C'est une capture d'écran d'environ 560 × 770 px : petite, mais nette.

| Moteur | Temps | Résultat |
|---|---|---|
| Mistral OCR | 6 s | **Très bon.** Titres, étoiles, ingrédients ligne à ligne, texte suivi. Quelques erreurs plausibles : « abriant » pour « abricot », « Xocolail » pour « Xocolatl », « Chef Gray Thunder » pour « Crazy », « il tira sur le mur » pour « le mari » |
| Marker | 18 s | Mots souvent justes, mais la structure s'effondre : quantités séparées de leurs ingrédients, faux tableau, lettres de marge mêlées au texte |
| Docling | 44 s | Nombreuses fautes de lecture, ordre en partie brouillé, 15 morceaux d'image découpés |

**Constat clé** : là où Mistral se trompe de façon plausible, Marker et Docling lisent juste (« mari », « Crazy »). Comparer deux lectures fait ressortir exactement les mots faux de Mistral, sans relire toute la page.

**Conclusions provisoires (après les tours 1 et 1 bis)** :

1. Sur une page propre, Mistral est nettement au-dessus des moteurs locaux sur processeur, pour la structure comme pour les mots.
2. Les moteurs locaux sur processeur ne suffisent pas comme lecture principale pour ce type de livre, mais ils servent de **contre-lecture** : un mot qui diffère entre Mistral et Marker devient un mot à relire.
3. La qualité de la prise compte toujours autant : page droite, seule, sans table.
4. La voie B (modèle de vision sur la carte AMD) n'est toujours pas mesurée.

## Tour 2 (à faire)

Mêmes photos, repassées par la préparation version 2. En plus :

- deux photos d'**une seule page** de fiches denses, prises de près, téléphone tenu dans le sens de la page ;
- le modèle de vision dans LM Studio.
