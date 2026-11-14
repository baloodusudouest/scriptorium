# Reprise — Scriptorium

Fichier à lire en premier dans une nouvelle session. Le mettre à jour à chaque fin de session, dans le même commit que le code.

## État (14/11/2026)

- **0.1.0** : squelette copié du socle 0.3.2. Nom, variables (`SCRIPTORIUM_…`), port 8091, couleur sépia `#c4a07a` ; l'écran « Composants » a été retiré. Aucune fonction propre à Scriptorium pour l'instant ; les 9 tests du socle passent.
- Conception : [`docs/dossier.md`](docs/dossier.md), en six sections, issu du grill du 14/11/2026. Le conseil n'a pas encore eu lieu.
- **Jamais essayé sur la vraie installation** : rien. Le service n'est pas dans la stack.

## Prochaine étape

1. **Sonde** (dossier, § 6 étape 0), sur 3 ou 4 pages riches d'un vrai livre, dont une double page prise à l'iPhone. Comparer les candidats de la voie A (processeur, Docker), un modèle de vision de la voie B (LM Studio ou Ollama sur la carte AMD RX 6700) et Mistral OCR. En attente : les pages et une clé Mistral.
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

- La carte du PC est une AMD : Docker Desktop sous Windows ne la voit pas. Le calcul dans un conteneur se fait sur le processeur.
- Dépôt public : aucune page de livre sous droits, aucun chemin réel. Les valeurs réelles passent par les variables de la stack.
- Port 8091 : vérifier dans Portainer qu'il est libre avant d'ajouter le service à la stack (8090 et 8093 à 8098 sont pris).
- Port Tailscale Serve de la caméra : vérifier `tailscale serve status` avant d'en choisir un.
- Hérités du socle : `pages/Services.svelte` est l'écran « Connexion », et `pages/Connexion.svelte` la page du mot de passe.

## Non-objectifs

- Pas d'envoi des illustrations dans Immich.
- Pas de dossier surveillé.
- Pas de lien avec Home Assistant en 1.0.
