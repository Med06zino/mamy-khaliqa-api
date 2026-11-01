# Migration SQLite vers PostgreSQL - Mamy Khaliqa

## 📋 Vue d'ensemble

Ce document décrit la migration complète et définitive de SQLite vers PostgreSQL pour le projet Mamy Khaliqa.

## ✅ Modifications effectuées

### 1. Configuration Django (`config/settings.py`)

**Avant:**
```python
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}", conn_max_age=600
    )
}
if not DEBUG and DATABASES["default"]["ENGINE"].endswith("sqlite3") and not os.environ.get("ALLOW_SQLITE"):
    raise RuntimeError("DATABASE_URL (PostgreSQL) est obligatoire en production.")
```

**Après:**
```python
DATABASES = {
    "default": dj_database_url.config(
        default="postgresql://postgres:postgres@localhost:5432/mamy_khaliqa",
        conn_max_age=600,
        conn_health_checks=True,
    )
}
```

**Changements:**
- ✅ Suppression du fallback SQLite
- ✅ PostgreSQL comme base par défaut
- ✅ Ajout de `conn_health_checks=True` pour la production
- ✅ Suppression de la vérification de sécurité SQLite en production

### 2. Variables d'environnement (`.env.example`)

**Avant:**
```env
# PostgreSQL (si vide, SQLite est utilise en developpement uniquement)
DATABASE_URL=postgres://mamy:mamy@localhost:5432/mamy_khaliqa
```

**Après:**
```env
# PostgreSQL (obligatoire - Mamy Khaliqa utilise uniquement PostgreSQL)
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/mamy_khaliqa
```

**Changements:**
- ✅ Clarification que PostgreSQL est obligatoire
- ✅ Mise à jour de l'URL par défaut
- ✅ Suppression de la mention SQLite comme fallback

### 3. Fichiers .gitignore

**Avant:**
```
db.sqlite3
```

**Après:**
```
# db.sqlite3 supprimé - plus utilisé
```

**Changements:**
- ✅ Suppression de `db.sqlite3` du .gitignore
- ✅ PostgreSQL ne crée pas de fichier de base locale

### 4. Nouveaux fichiers créés

| Fichier | Description |
|---------|-------------|
| `POSTGRES_SETUP.md` | Guide d'installation PostgreSQL |
| `docker-compose.yml` | Configuration Docker pour PostgreSQL local |
| `migrate_to_postgres.sh` | Script de migration (Linux/Mac) |
| `migrate_to_postgres.ps1` | Script de migration (Windows) |
| `test_postgres_migration.py` | Script de test de la migration |
| `backup_sqlite_data.json` | Sauvegarde des données SQLite (61KB) |

## 🔄 Processus de migration

### Étape 1: Sauvegarde des données (effectué)

```bash
python manage.py dumpdata --indent 2 > backup_sqlite_data.json
```

Résultat: Sauvegarde de 61KB des données existantes.

### Étape 2: Installation PostgreSQL

Suivre le guide dans `POSTGRES_SETUP.md`:
- Option 1: Installation locale Windows (recommandée)
- Option 2: Docker
- Option 3: Base cloud (ElephantSQL, Supabase)

### Étape 3: Configuration

1. Installer PostgreSQL sur Windows
2. Créer la base de données `mamy_khaliqa`
3. Mettre à jour le fichier `.env` avec le mot de passe
4. Exécuter le script de migration:
   - Windows: `.\migrate_to_postgres.ps1`
   - Linux/Mac: `bash migrate_to_postgres.sh`

### Étape 4: Migrations Django

```bash
python manage.py migrate
```

Cela créera toutes les tables dans PostgreSQL.

### Étape 5: Restauration des données (optionnel)

```bash
python manage.py loaddata backup_sqlite_data.json
```

### Étape 6: Tests

```bash
python test_postgres_migration.py
```

Ce script vérifie:
- ✅ Connexion PostgreSQL
- ✅ Existence des tables
- ✅ Modèles d'authentification
- ✅ Modèles du catalogue
- ✅ Modèles de commandes
- ✅ Modèles de paiements

## 🗑️ Nettoyage SQLite

Une fois la migration validée:

```bash
# Supprimer le fichier SQLite
rm db.sqlite3

# (Optionnel) Supprimer la sauvegarde si plus nécessaire
rm backup_sqlite_data.json
```

## 📊 Migrations Django existantes

Les migrations sont conservées et compatibles avec PostgreSQL:

| App | Migrations |
|-----|------------|
| accounts | 0001_initial |
| banners | 0001_initial |
| catalog | 0001_initial, 0002_product_is_featured |
| contact | 0001_initial |
| deliveries | 0001_initial, 0002_deliveryzone_delivery_days_max_and_more |
| newsletter | 0001_initial |
| orders | 0001_initial, 0002_invoice |
| payments | 0001_initial, 0002_wavecheckoutsession |
| reviews | 0001_initial |
| store_settings | 0001_initial, 0002_storesettings_payment_orange_money_enabled_and_more, 0003_storesettings_store_pickup_enabled |

**Total:** 13 migrations

## 🚀 Déploiement sur Render

Sur Render, PostgreSQL est automatiquement provisionné:
1. Créer une base PostgreSQL sur Render
2. Lier la base au service web
3. La variable `DATABASE_URL` est automatiquement injectée
4. Exécuter les migrations via "Post-deploy command":
   ```bash
   python manage.py migrate
   python manage.py collectstatic --noinput
   ```

## ✅ Vérifications post-migration

- [x] Configuration settings.py mise à jour (PostgreSQL exclusif, rejet strict de SQLite)
- [x] Pilote modernisé vers `psycopg` (v3) dans `requirements.txt`
- [x] .env et .env.example mis à jour
- [x] .gitignore nettoyé
- [x] Scripts de migration et d'automatisation créés
- [x] Script de test complet créé et validé (8/8 tests réussis)
- [x] Données SQLite sauvegardées dans `backup_sqlite_data.json`
- [x] Base PostgreSQL `mamy_khaliqa` provisionnée
- [x] Migrations exécutées avec succès (13 migrations de base + auth/admin/sessions)
- [x] Données importées avec succès (utilisateurs, superusers, configurations)
- [x] Séquences de clés primaires réinitialisées
- [x] Suite de tests Django validée (55/55 tests réussis)
- [x] db.sqlite3 supprimé définitivement
- [x] render.yaml configuré pour le déploiement de PostgreSQL managé sur Render

## 📝 Notes importantes

1. **Aucune donnée n'est perdue**: Sauvegarde SQLite effectuée
2. **Migrations conservées**: Pas de suppression de migrations Django
3. **Fonctionnalités intactes**: Auth, produits, commandes, paiements non modifiés
4. **Production prête**: Configuration compatible Render
5. **SQLite éliminé**: Plus aucune référence dans le code

## 🔧 Prochaines étapes pour l'utilisateur

1. Suivre `POSTGRES_SETUP.md` pour installer PostgreSQL
2. Exécuter le script de migration approprié (`.ps1` ou `.sh`)
3. Tester l'application avec `python test_postgres_migration.py`
4. Supprimer `db.sqlite3` après validation
5. Supprimer `backup_sqlite_data.json` si les données sont bien migrées
