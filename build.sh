#!/usr/bin/env bash
# Script de build Render pour Mamy Khaliqa (Backend Django & PostgreSQL)
set -o errexit

echo "==> Installation des dependances Python..."
pip install -r requirements.txt

echo "==> Collecte des fichiers statiques (WhiteNoise)..."
python manage.py collectstatic --no-input

echo "==> Application des migrations sur PostgreSQL..."
python manage.py migrate --no-input

echo "==> Restauration / initialisation du catalogue produits..."
python manage.py restore_catalog_media || true

echo "==> Build termine avec succes !"
