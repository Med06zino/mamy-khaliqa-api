#!/bin/bash
# Script pour configurer PostgreSQL pour Mamy Khaliqa

echo "=== Configuration PostgreSQL pour Mamy Khaliqa ==="
echo ""

# Vérifier si PostgreSQL est installé
if ! command -v psql &> /dev/null; then
    echo "❌ PostgreSQL n'est pas installé."
    echo "Veuillez suivre les instructions dans POSTGRES_SETUP.md"
    exit 1
fi

# Demander le mot de passe PostgreSQL
echo "Entrez votre mot de passe PostgreSQL (celui défini lors de l'installation):"
read -s POSTGRES_PASSWORD

# Mettre à jour le fichier .env
echo "Mise à jour du fichier .env..."
sed -i "s|DATABASE_URL=postgresql://postgres:.*@localhost:5432/mamy_khaliqa|DATABASE_URL=postgresql://postgres:${POSTGRES_PASSWORD}@localhost:5432/mamy_khaliqa|g" .env

# Créer la base de données
echo "Création de la base de données mamy_khaliqa..."
PGPASSWORD=$POSTGRES_PASSWORD psql -U postgres -c "CREATE DATABASE mamy_khaliqa;" 2>/dev/null || echo "⚠️  La base de données existe déjà ou nécessite des droits élevés"

# Exécuter les migrations
echo "Exécution des migrations Django..."
python manage.py migrate

# Restaurer les données (optionnel)
if [ -f "backup_sqlite_data.json" ]; then
    echo ""
    read -p "Voulez-vous restaurer les données depuis SQLite? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Restauration des données..."
        python manage.py loaddata backup_sqlite_data.json
    fi
fi

echo ""
echo "✅ Migration terminée avec succès!"
echo "Vous pouvez maintenant démarrer le serveur: python manage.py runserver"
