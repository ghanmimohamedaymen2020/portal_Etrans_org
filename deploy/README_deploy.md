# Déploiement propre du projet

Ce dossier contient une copie minimale des fichiers nécessaires pour déployer l'application avec Docker.

Fichiers:
- `Dockerfile` : image de l'application
- `docker-compose.yml` : compose avec le service `web` et `mssql`
- `.env.example` : valeurs d'environnement à copier dans `.env` et personnaliser

Instructions rapides

1. Copier `.env.example` en `.env` et remplir les valeurs sensibles.
2. Construire et lancer les services depuis ce dossier:

```powershell
cd "C:\Users\mohamed_ghanmi.GREENTNS\Documents\E_trans\E-trans-portal\deploy"
docker-compose up --build -d
```

3. Initialiser la base de données si nécessaire:

```powershell
# Exécuter un script d'init si présent (adapter le nom du service si différent)
docker-compose exec web python init_db.py
```

4. Voir les logs:

**Déploiement (résumé)**

- Copier `deploy/.env.example` → `deploy/.env` et remplir les valeurs.
- Pour Windows service : ouvrir PowerShell en Administrateur, depuis `deploy` exécuter `.
set-env.ps1` (écrit les variables en scope Machine) puis redémarrer le service `EtransApp`.
- Pour test rapide sans service : activer le venv et lancer `python run.py` depuis la racine.

Vérifications utiles :
- Tester la connexion SQL : `sqlcmd -S 192.168.8.239 -U ITUser -P "ITUser2026*" -d Dashboard -Q "SELECT 1"`
- Tester l'API (auth) : POST `/login` puis GET `/api/factures/aa-totals` (ou réutiliser le cookie `session`).
- Logs : `Get-Content .\logs\stderr.log -Tail 200` et `Get-Content .\logs\stdout.log -Tail 200`.

Si besoin, je peux raccourcir davantage ou ajouter un script `deploy/restart-service.ps1` (élévation). 
```

