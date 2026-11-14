# Sonde de Scriptorium — mode d'emploi

But : passer 3 ou 4 pages difficiles d'un vrai livre dans chaque outil, puis comparer les résultats côte à côte. Le rapport dira quel outil Scriptorium utilisera, et si la carte graphique (voie B) vaut l'installation de LM Studio.

| Étape | Outil | Où ça tourne |
|---|---|---|
| `docling` | Docling (IBM) + Tesseract français | processeur, dans Docker |
| `marker` | Marker | processeur, dans Docker |
| `vision` | modèle de vision (Qwen VL) dans LM Studio | carte AMD RX 6700, hors de Docker |
| `mistral` | Mistral OCR | en ligne, avec ta clé |

Rien n'est envoyé sur GitHub : `pages/`, `resultats/`, `.env` et les modèles téléchargés restent sur le PC.

## 1. Récupérer la sonde

1. Sur https://github.com/baloodusudouest/scriptorium, clique sur **Code › Download ZIP**.
2. Décompresse l'archive, par exemple dans `Documents\scriptorium`.
3. Ouvre un **PowerShell** dans le dossier `sonde` : dans l'Explorateur, clic droit sur le dossier › « Ouvrir dans le Terminal ».

Docker Desktop doit être lancé.

## 2. Déposer les pages

Mets dans `sonde\pages\` 3 ou 4 pages qui posent problème, en photos (JPEG, HEIC de l'iPhone) ou en PDF :

- une page à **deux colonnes** ou avec un **encadré** ;
- une page avec un **tableau** ;
- une page avec une **photo ou une illustration** et sa légende ;
- une **double page** photographiée à l'iPhone, livre ouvert, pour juger la courbure près du pli.

### Tour 2 (après le premier essai)

- Garde les quatre photos du premier tour dans `pages\`.
- Ajoute **deux photos d'une seule page** de fiches denses : la même page qu'une des doubles pages, prise de près, téléphone tenu dans le sens de la page, page entière dans le cadre.
- Tu peux supprimer l'ancien dossier `resultats\`, pour que le rapport ne montre que le nouveau tour.

`preparer` fait maintenant trois choses :

- il remet chaque photo dans le bon sens ;
- il retire la table autour ;
- il coupe chaque double page au pli, en `-g` (page de gauche) et `-d` (page de droite).

Regarde les images dans `pages_prep\` avant de lancer les moteurs : si une coupe est fausse, dis-le-moi.

## 3. La clé Mistral

1. Copie `.env.example` en `.env`, dans le même dossier.
2. Ouvre `.env` avec le Bloc-notes et colle ta clé après `MISTRAL_API_KEY=`.

## 4. Lancer les étapes

Une commande à la fois, dans le PowerShell ouvert dans `sonde` :

```powershell
docker compose run --build --rm preparer
docker compose run --rm mistral
docker compose run --rm docling
docker compose run --rm marker
docker compose run --rm rapport
```

- `--build` sur `preparer` reconstruit l'image légère (elle a changé au tour 2) ; inutile ensuite.
- La **première** fois, `docling` et `marker` construisent leur image (2 à 3 Go chacune), puis téléchargent leurs modèles dans `.cache\`. Compte 10 à 20 minutes chacune. Les fois suivantes démarrent tout de suite.
- Sur le processeur, une page peut prendre de quelques secondes à quelques minutes. Le temps de chaque page est mesuré : c'est un des résultats.
- Une étape interrompue se relance telle quelle : les pages déjà lues ne sont pas refaites.
- Si `marker` ou `docling` s'arrête avec « Killed », Docker manque de mémoire : dans Docker Desktop, *Settings › Resources*, donne-lui au moins 12 Go.

## 5. La voie B : le modèle de vision sur la carte AMD (facultatif mais utile)

1. Installe **LM Studio** depuis https://lmstudio.ai et lance-le.
2. Dans les réglages (roue dentée) › **Runtime**, choisis le moteur **Vulkan** (llama.cpp). C'est celui qui utilise la RX 6700.
3. Onglet **Discover** (loupe) : cherche **Qwen2.5-VL-7B-Instruct**, ou **Qwen3-VL-8B** s'il est proposé. Prends une version **GGUF Q4_K_M**, avec le badge « Vision ». Le téléchargement fait environ 5 à 6 Go.
4. Charge le modèle : « GPU offload » au maximum, longueur de contexte **8192**.
5. Onglet **Developer** : **Start server**, sur le port 1234.
6. Vérifie dans le navigateur : http://localhost:1234/v1/models doit afficher le nom du modèle.
7. Puis :

```powershell
docker compose run --rm vision
docker compose run --rm rapport
```

Pendant le calcul, la colonne « GPU » du Gestionnaire des tâches doit monter. Si elle reste à 0 % et que le processeur s'emballe, la carte n'est pas utilisée : note-le, c'est un résultat de la sonde.

## 6. Le résultat

`resultats\rapport.html` s'ouvre dans le navigateur. Pour chaque page, il montre l'image d'origine puis le rendu de chaque outil, avec son temps. En haut, un tableau résume pages lues, temps moyen, erreurs et pages Mistral facturées.

Envoie-moi `rapport.html`, ou mieux, le dossier `resultats` zippé : je compare le texte mot à mot et j'écris le rapport de sonde.
