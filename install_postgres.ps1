# Script PowerShell pour vérifier et aider à l'installation de PostgreSQL sur Windows

Write-Host "=== Vérification de l'installation PostgreSQL ===" -ForegroundColor Cyan
Write-Host ""

# Vérifier si PostgreSQL est installé
$psqlPath = Get-Command psql -ErrorAction SilentlyContinue
if ($psqlPath) {
    Write-Host "✅ PostgreSQL est déjà installé!" -ForegroundColor Green
    Write-Host "   Chemin: $($psqlPath.Source)" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Vous pouvez maintenant configurer la base de données." -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Commandes à exécuter:" -ForegroundColor Yellow
    Write-Host "1. Ouvrir SQL Shell (psql) ou pgAdmin" -ForegroundColor White
    Write-Host "2. Exécuter: CREATE DATABASE mamy_khaliqa;" -ForegroundColor White
    Write-Host "3. Mettre à jour .env avec votre mot de passe" -ForegroundColor White
    Write-Host "4. Exécuter: .venv\Scripts\python.exe manage.py migrate" -ForegroundColor White
    exit 0
}

Write-Host "❌ PostgreSQL n'est pas installé" -ForegroundColor Red
Write-Host ""
Write-Host "=== Options d'installation ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Option 1: Installation manuelle (recommandée)" -ForegroundColor Yellow
Write-Host "1. Télécharger PostgreSQL depuis: https://www.postgresql.org/download/windows/" -ForegroundColor White
Write-Host "2. Choisir la version 16.x" -ForegroundColor White
Write-Host "3. Pendant l'installation:" -ForegroundColor White
Write-Host "   - Port: 5432 (par défaut)" -ForegroundColor White
Write-Host "   - Mot de passe superutilisateur: postgres (ou votre propre mot de passe)" -ForegroundColor White
Write-Host "   - Cocher 'Stack Builder' (optionnel)" -ForegroundColor White
Write-Host ""
Write-Host "Option 2: Utiliser Chocolatey (si installé)" -ForegroundColor Yellow
Write-Host "   choco install postgresql" -ForegroundColor White
Write-Host ""
Write-Host "Option 3: Utiliser Docker (si Docker Desktop est installé)" -ForegroundColor Yellow
Write-Host "   docker compose up -d" -ForegroundColor White
Write-Host "   (Le fichier docker-compose.yml est déjà configuré)" -ForegroundColor White
Write-Host ""
Write-Host "Après installation, exécutez à nouveau ce script pour vérifier." -ForegroundColor Cyan
