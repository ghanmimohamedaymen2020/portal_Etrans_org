@echo off
REM Script de démarrage du projet E-Trans

echo ========================================
echo  E-Trans - Projet de Gestion des Avis
echo ========================================
echo.

REM Usage: start.bat [development|production]
SET ENV_ARG=%1
IF "%ENV_ARG%"=="" SET ENV_ARG=development
SET FLASK_ENV=%ENV_ARG%

REM Créer l'environnement virtuel s'il n'existe pas
if not exist venv (
    echo [*] Création de l'environnement virtuel...
    python -m venv venv
)

REM Activer l'environnement virtuel
echo [*] Activation de l'environnement virtuel...
call venv\Scripts\activate.bat

REM Installer les dépendances
echo [*] Installation des dépendances...
pip install -r requirements.txt

REM Initialiser la base de données
echo [*] Initialisation de la base de données...
python init_db.py

echo.
echo [✓] Démarrage de l'application (ENV=%FLASK_ENV%)...
echo [*] Accédez à http://localhost:5000
echo.

python run.py

pause
