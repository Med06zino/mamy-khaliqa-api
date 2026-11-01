# Installation et Configuration PostgreSQL pour Mamy Khaliqa

## Option 1: Installation locale (Recommandée pour le développement)

### Étape 1: Télécharger et installer PostgreSQL sur Windows

1. Télécharger PostgreSQL depuis: https://www.postgresql.org/download/windows/
2. Choisir la version 16.x (la plus récente stable)
3. Pendant l'installation:
   - Port: 5432 (par défaut)
   - Mot de passe superutilisateur: `postgres` (ou votre propre mot de passe)
   - Cocher "Stack Builder" (optionnel, pas nécessaire)

### Étape 2: Créer la base de données

Ouvrir SQL Shell (psql) ou pgAdmin et exécuter:

```sql
-- Créer la base de données
CREATE DATABASE mamy_khaliqa;

-- Vérifier la création
\l
```

### Étape 3: Mettre à jour le fichier .env

Modifier `backend/.env` avec vos identifiants:

```env
DATABASE_URL=postgresql://postgres:VOTRE_MOT_DE_PASSE@localhost:5432/mamy_khaliqa
```

Remplacez `VOTRE_MOT_DE_PASSE` par le mot de passe défini lors de l'installation.

---

## Option 2: Utiliser Docker (Alternative)

Si Docker Desktop est installé:

```bash
cd backend
docker compose up -d
```

Le fichier `docker-compose.yml` est déjà configuré.

---

## Option 3: Base PostgreSQL Cloud (Alternative pour tests rapides)

Utiliser un service gratuit comme:
- ElephantSQL: https://www.elephantsql.com/
- Supabase: https://supabase.com/

Créer une base, obtenir l'URL et mettre à jour `DATABASE_URL` dans `.env`.

---

## Étape 4: Exécuter les migrations

Une fois PostgreSQL configuré:

```bash
cd backend
python manage.py migrate
```

---

## Étape 5: Restaurer les données (optionnel)

Si vous avez des données de SQLite à migrer:

```bash
cd backend
python manage.py loaddata backup_sqlite_data.json
```

---

## Étape 6: Tester la connexion

```bash
cd backend
python manage.py dbshell
```

Si vous obtenez un prompt PostgreSQL, la connexion fonctionne!

---

## Configuration Production (Render)

Sur Render, PostgreSQL est automatiquement provisionné. Il suffit de:
1. Créer une base PostgreSQL sur Render
2. Lier la base au service web
3. La variable `DATABASE_URL` sera automatiquement injectée
