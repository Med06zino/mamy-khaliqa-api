#!/usr/bin/env bash
# Commande de build Render. Ne supprime ni ne reinitialise jamais la base de donnees.
set -o errexit
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate --no-input
