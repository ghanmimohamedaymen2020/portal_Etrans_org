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

```powershell
docker-compose logs -f
```

**Utiliser la base distante (192.168.8.239/Dashboard)**

Si vous souhaitez que l'application utilise la base distante `Dashboard` comme base principale (afficher ses vues et totaux), suivez ces étapes :

- 1) Mettre à jour les variables d'environnement
	- Éditez `deploy\.env` (ou `./.env`) et définissez `DATABASE_URL` pour pointer sur la base distante. Exemple déjà fourni :

```env
DATABASE_URL=mssql+pyodbc://ITUser:ITUser2026%2A@192.168.8.239/Dashboard?driver=ODBC+Driver+17+for+SQL+Server&Encrypt=no&TrustServerCertificate=yes&Trusted_Connection=no
USERS_DATABASE_URL=mssql+pyodbc:///?odbc_connect=DRIVER%3D%7BODBC+Driver+17+for+SQL+Server%7D%3BSERVER%3D.%5CSQLEXPRESS%3BDATABASE%3Detrans%3BUID%3Dsa%3BPWD%3DQdg4d85Q
```

- 2) Charger ces variables comme variables Machine (optionnel, requis pour le service)
	- Ouvrez PowerShell en **Administrateur** et exécutez depuis le dossier `deploy` :

```powershell
cd "C:\Users\mohamed_ghanmi.GREENTNS\Documents\E_trans\E-trans-portal\deploy"
.\set-env.ps1
```

	- Le script écrit chaque paire clé=valeur dans les variables d'environnement Machine. Redémarrage du service ou du serveur peut être nécessaire.

- 3) Redémarrer le service Windows (NSSM) ou relancer l'application
	- Si vous avez installé le service via NSSM (script `service-install.ps1`), redémarrez-le en Administrateur :

```powershell
nssm restart EtransApp
# ou
Restart-Service -Name EtransApp
```

	- Si vous testez manuellement, lancez l'application depuis le projet :

```powershell
cd "C:\Users\mohamed_ghanmi.GREENTNS\Documents\E_trans\E-trans-portal"
.venv\Scripts\Activate.ps1
python run.py
```

- 4) Vérifier l'API du tableau de bord
	- Appeler l'endpoint qui alimente le widget (exemples) :

```powershell
curl http://localhost:5000/dashboard/api/stats/admin
curl http://localhost:5000/factures/aa-totals
```

- 5) Vérifier les logs si les valeurs ne s'affichent pas

```powershell
Get-Content .\logs\stdout.log -Tail 200
Get-Content .\logs\stderr.log -Tail 200
```

Remarques et dépannage
- Si `sqlcmd` ou `Test-NetConnection` échouent vers `192.168.8.239`, vérifiez :
	- accès réseau, firewall, port 1433 ouvert
	- protocole TCP activé sur l'instance SQL distante
	- utilisateur/mot de passe et droits sur la base `Dashboard`
- Si l'app continue d'afficher des zéros, appelez directement `/dashboard/api/stats/*` et vérifiez le JSON retourné — il indique souvent la cause (colonnes manquantes, exception SQL, etc.).

Rollback rapide
- Pour revenir à la configuration locale : remplacez `DATABASE_URL` par la valeur pointant sur `etrans` et rechargez les variables puis redémarrez le service.

