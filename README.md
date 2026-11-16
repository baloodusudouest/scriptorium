# Scriptorium

D'un livre scanné à un vrai livre en texte : PDF et EPUB recomposés, qui gardent la mise en forme et les illustrations.

État : **0.6.0** — import d'un PDF, inventaire des pages manquantes, lecture par Mistral et contre-lecture par le PC, fiche par l'ISBN, EPUB et PDF A5, dépôt dans Grimmory, réglages sauvegardés par l'Anneau. La conception est dans [`docs/dossier.md`](docs/dossier.md), le point du chantier dans [`REPRISE.md`](REPRISE.md).

## Principe

1. Les pages arrivent par l'iPhone (doubles pages, prise automatique) ou par l'import d'un PDF ou d'images.
2. Un PC de calcul vient chercher les pages, les redresse, analyse la mise en page et lit le texte.
3. Les mots et pages douteux passent en relecture. On les corrige à la main, ou on les fait relire par Mistral OCR sur un clic.
4. Le livre est assemblé en EPUB et en PDF, puis déposé dans le `bookdrop` de Grimmory.

## Installation

Voir `docker-compose.yml` et `.env.example`. Aucune vraie valeur ne figure dans le dépôt : le mot de passe commun (`MAISON_PASSWORD`), le jeton commun (`MAISON_JETON`), les chemins et les clés se saisissent dans les variables de la stack. Les réglages d'usage (recherche en ligne de la fiche, prix estimé par page, définition des pages) se changent dans l'écran Réglages ; l'Anneau les sauvegarde chaque nuit et « Restaurer les réglages » les reprend.

## Développement

```
pip install -r requirements.txt -r requirements-dev.txt
cd frontend && npm ci && npx vite build && cd ..
pytest                      # tests d'écran : python -m playwright install chromium
python -m tools.demo 8191   # serveur de démonstration (mot de passe demo-demo-demo)
```
