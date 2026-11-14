# Reprise — Scriptorium

Fichier à lire en premier dans une nouvelle session. Le mettre à jour à chaque fin de session, dans le même commit que le code.

## État (14/11/2026)

- **0.1.0** : squelette copié du socle 0.3.2. Nom, variables (`SCRIPTORIUM_…`), port 8091, couleur sépia `#c4a07a` ; l'écran « Composants » a été retiré. Aucune fonction propre à Scriptorium pour l'instant ; les 9 tests du socle passent.
- **Sonde prête** (`sonde/`, 14/11/2026) : à lancer sur le PC, voir `sonde/LISEZMOI.md`. Docling et Marker sur le processeur dans Docker, modèle de vision par LM Studio (Vulkan, RX 6700), Mistral OCR, rapport côte à côte. Partie légère testée (7 tests) ; Docling, Marker et LM Studio jamais lancés (modèles injoignables depuis l'environnement de Claude).
- Conception : [`docs/dossier.md`](docs/dossier.md), en six sections, issu du grill du 14/11/2026. Le conseil n'a pas encore eu lieu.
- **Jamais essayé sur la vraie installation** : rien. Le service n'est pas dans la stack.

## Prochaine étape

0. **Décisions du 14/11/2026 après la sonde** (fin de `docs/dossier.md`) : Mistral d'abord avec contre-lecture Marker sur le PC, prise page par page, import d'un gros PDF avec inventaire des pages manquantes (`sonde/outils/inventaire.py`, testé sur un PDF synthétique). Prochaine étape : le conseil sur le dossier.

1. **Sonde, tour 2** : compte rendu du tour 1 dans [`docs/sonde.md`](docs/sonde.md). Ce qu'il a montré : la préparation de l'image prime sur le moteur, la double page est sans doute trop juste pour les fiches denses, et Mistral invente sur les pages difficiles. La préparation version 2 (sens, recadrage, coupe au pli) a été essayée sur des réductions des photos du tour 1 : les huit pages sont bien coupées. Tour 2 : les mêmes photos et deux photos d'une seule page, plus la voie B.
1. (rappel) **Sonde** (dossier, § 6 étape 0) : l'utilisateur la lance sur son PC avec 3 ou 4 pages riches (dont une double page iPhone) et renvoie `resultats/`. Clé Mistral créée (14/11/2026). Ensuite, rapport de sonde (`docs/sonde.md`), qui choisit le moteur et la voie. MinerU et PaddleOCR n'y sont pas : à ajouter seulement si Docling et Marker déçoivent.
2. Passage du dossier et du rapport de sonde au conseil.
3. Code de la 1.0.0, livrée d'un bloc.

## Décisions tranchées

Voir le dossier, § 1. Pour mémoire :

- Pages prises à l'iPhone (doubles pages) et import de PDF ou d'images.
- Sortie en PDF et EPUB recomposés.
- Calcul sur le PC d'abord ; Mistral OCR seulement sur un clic.
- Relecture ciblée.
- Dépôt dans le `bookdrop` de Grimmory.
- Rien vers Home Assistant.

## Pièges

- Sonde : le registre de modèles (Hugging Face) et l'API Mistral sont injoignables depuis l'environnement de Claude. Les moteurs lourds ne se testent que sur le PC.
- `docling` (2.150) a déprécié `force_full_page_ocr` : il faut écrire `mode=OcrMode.FULL_PAGE`.

- La carte du PC est une AMD : Docker Desktop sous Windows ne la voit pas. Le calcul dans un conteneur se fait sur le processeur.
- Dépôt public : aucune page de livre sous droits, aucun chemin réel. Les valeurs réelles passent par les variables de la stack.
- Port 8091 : vérifier dans Portainer qu'il est libre avant d'ajouter le service à la stack (8090 et 8093 à 8098 sont pris).
- Port Tailscale Serve de la caméra : vérifier `tailscale serve status` avant d'en choisir un.
- Hérités du socle : `pages/Services.svelte` est l'écran « Connexion », et `pages/Connexion.svelte` la page du mot de passe.

## Non-objectifs

- Pas d'envoi des illustrations dans Immich.
- Pas de dossier surveillé.
- Pas de lien avec Home Assistant en 1.0.
