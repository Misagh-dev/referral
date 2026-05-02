# RIS Application Update Script
# Usage: .\update-ris.ps1

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "   RIS Application Update Script" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Navigate to RIS directory
Set-Location C:\Users\User\Desktop\ris\referral

# Show current status
Write-Host "Current Git Status:" -ForegroundColor Yellow
git status --short

Write-Host "`n--- Pulling Latest Changes ---" -ForegroundColor Green
git pull origin docker-self-hosted

if ($LASTEXITCODE -ne 0) {
    Write-Host "`nGit pull failed. Please resolve conflicts manually." -ForegroundColor Red
    exit 1
}

# Navigate to docker directory
Set-Location docker

Write-Host "`n--- Rebuilding Docker Image ---" -ForegroundColor Green
docker-compose build --no-cache

if ($LASTEXITCODE -ne 0) {
    Write-Host "`nDocker build failed!" -ForegroundColor Red
    exit 1
}

Write-Host "`n--- Restarting Container ---" -ForegroundColor Green
docker-compose down
Start-Sleep -Seconds 2
docker-compose up -d

Write-Host "`n--- Waiting for Container to Start ---" -ForegroundColor Green
Start-Sleep -Seconds 8

Write-Host "`n--- Container Status ---" -ForegroundColor Cyan
docker-compose ps

Write-Host "`n--- Recent Logs ---" -ForegroundColor Cyan
docker-compose logs --tail=20

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "   Update Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "`nRIS is accessible at:" -ForegroundColor Yellow
Write-Host "  Local:  http://localhost:8501" -ForegroundColor White
Write-Host "  Public: https://ris.radiology2u.com.au" -ForegroundColor White
Write-Host ""
