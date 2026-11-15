# Contre-lecture sur le PC

Le PC relit chaque page avec **Marker**, sur le processeur. Scriptorium compare ensuite cette lecture à celle de Mistral : les mots qui diffèrent deviennent les mots à relire, surlignés dans l'écran de relecture.

## Mise en route (une fois)

1. **Créer un jeton** : 32 caractères au hasard. Par exemple, dans PowerShell :
   `-join ((48..57)+(65..90)+(97..122) | Get-Random -Count 32 | % {[char]$_})`
2. **Côté NAS** : dans la stack Portainer, donner ce jeton à `SCRIPTORIUM_JETON_CALCUL` (variable d'environnement de la stack), puis redéployer.
3. **Côté PC** : copier ce dossier `pc/` (les fichiers `calcul.yml` et `.env.exemple` suffisent), renommer `.env.exemple` en `.env`, et le remplir :
   - `SCRIPTORIUM_URL` : l'adresse du NAS et le port 8091 ;
   - `SCRIPTORIUM_JETON_CALCUL` : le même jeton.
4. Dans ce dossier : `docker compose -f calcul.yml up -d`.
5. Suivre le premier lancement : `docker compose -f calcul.yml logs -f`. Les modèles (environ 2 Go) se téléchargent une fois, dans un volume Docker.

Dans Scriptorium, la tuile **PC de calcul** (écran Connexion) dit quand le PC est passé pour la dernière fois et combien de pages attendent.

## Au quotidien

- Rien à faire : le conteneur redémarre avec Docker Desktop et demande du travail toutes les 30 secondes.
- Compter de 10 à 20 secondes par page sur le processeur : un livre de 300 pages se relit en une à deux heures.
- PC éteint : rien n'est bloqué. Les pages attendent, et la relecture reste possible sans les mots surlignés.
- Une page prise par le PC et jamais rendue (PC éteint en route) est reproposée au bout de 15 minutes.

## Mettre à jour

`docker compose -f calcul.yml pull && docker compose -f calcul.yml up -d`
