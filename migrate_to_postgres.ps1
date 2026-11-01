# Script PowerShell pour configurer PostgreSQL pour Mamy Khaliqa

Write-Host "=== Configuration PostgreSQL pour Mamy Khaliqa ===" -ForegroundColor Cyan
Write-Host ""

# Vérifier si PostgreSQL est installé
$psqlPath = Get-Command psql -ErrorAction SilentlyContinue
if (-not $psqlPath) {
    Write-Host "❌ PostgreSQL n'est pas installé ou n'est pas dans le PATH." -ForegroundColor Red
    Write-Host "Veuillez suivre les instructions dans POSTGRES_SETUP.md" -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ PostgreSQL détecté: $($psqlPath.Source)" -ForegroundColor Green
Write-Host ""

# Demander le mot de passe PostgreSQL
Write-Host "Entrez votre mot de passe PostgreSQL (celui défini lors de l'installation):" -ForegroundColor Yellow
$POSTGRES_PASSWORD = Read-Host -AsSecureString
$POSTGRES_PASSWORD_TEXT = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto([System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($POSTGRES_PASSWORD))

# Mettre à jour le fichier .env
Write-Host "Mise à jour du fichier .env..." -ForegroundColor Cyan
$envContent = Get-Content .env
$envContent = $envContent -replace "DATABASE_URL=postgresql://postgres:.*@localhost:5432/mamy_khaliqa", "DATABASE_URL=postgresql://postgres:${POSTGRES_PASSWORD_TEXT}@localhost:5432/mamy_khaliqa"
$envContent | Set-Content .env

# Créer la base de données
Write-Host "Création de la base de données mamy_khaliqa..." -ForegroundColor Cyan
$env:PGPASSWORD = $POSTGRES_PASSWORD_TEXT
psql -U postgres -c "CREATE DATABASE mamy_khaliqa;" 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Base de données créée avec succès" -ForegroundColor Green
} else {
    Write-Host "⚠️  La base de données existe déjà ou nécessite des droits élevés" -ForegroundColor Yellow
}

# Exécuter les migrations
Write-Host "Exécution des migrations Django..." -ForegroundColor Cyan
python manage.py migrate

# Restaurer les données (optionnel)
if (Test-Path "backup_sqlite_data.json") {
    Write-Host ""
    $response = Read-Host "Voulez-vous restaurer les données depuis SQLite? (y/n)"
    if ($response -eq "y" -or $response -eq "Y") {
        Write-Host "Restauration des données..." -ForegroundColor Cyan
        python manage.py loaddata backup_sqlite_data.json
    }
}

Write-Host ""
Write-Host "✅ Migration terminée avec succès!" -ForegroundColor Green
Write-Host "Vous pouvez maintenant démarrer le serveur: python manage.py runserver" -ForegroundColor Cyan
