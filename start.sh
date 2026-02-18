#!/bin/bash

# Script de démarrage du projet E-Trans (Linux/Mac)

echo "========================================"
echo " E-Trans - Projet de Gestion des Avis"
echo "========================================"
echo ""

# Usage: ./start.sh [development|production]
ENV_ARG=${1:-development}
export FLASK_ENV=${ENV_ARG}

# Créer l'environnement virtuel s'il n'existe pas
if [ ! -d "venv" ]; then
    echo "[*] Création de l'environnement virtuel..."
    python3 -m venv venv
fi

# Activer l'environnement virtuel
echo "[*] Activation de l'environnement virtuel..."
source venv/bin/activate

# Installer les dépendances
echo "[*] Installation des dépendances..."
pip install -r requirements.txt

# Initialiser la base de données
echo "[*] Initialisation de la base de données..."
python init_db.py

echo "" 
echo "[✓] Démarrage de l'application (ENV=${FLASK_ENV})..."
echo "[*] Accédez à http://localhost:5000"
echo "" 

python run.py
