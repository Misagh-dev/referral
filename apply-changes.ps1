# Apply Changes from USB Drive
# Run this on PRODUCTION SERVER after transferring files from dev PC

param(
    [string]$UsbDrive = "E:",
    [switch]$Rebuild
)

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "   Apply Dev Changes to Production" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

$sourceDir = "$UsbDrive\ris-updates"
$targetDir = "C:\Users\User\Desktop\ris\referral"

if (-not (Test-Path $sourceDir)) {
    Write-Host "ERROR: USB drive updates folder not found: $sourceDir" -ForegroundColor Red
    Write-Host "Please insert USB drive and ensure ris-updates folder exists." -ForegroundColor Yellow
    exit 1
}

Write-Host "Files to copy from USB:" -ForegroundColor Yellow
Get-ChildItem $sourceDir -Recurse -File | Select-Object FullName

Write-Host "`nPress Enter to continue or Ctrl+C to cancel..." -ForegroundColor Yellow
Read-Host

# Backup current version
$backupDir = "C:\Users\User\Desktop\ris\backups\backup_$(Get-Date -Format 'yyyy-MM-dd_HHmmss')"
Write-Host "`nCreating backup at: $backupDir" -ForegroundColor Green
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null

# Backup files that will be replaced
Get-ChildItem $sourceDir -Recurse -File | ForEach-Object {
    $relativePath = $_.FullName.Replace($sourceDir, "").TrimStart('\')
    $targetFile = Join-Path $targetDir $relativePath
    if (Test-Path $targetFile) {
        $backupFile = Join-Path $backupDir $relativePath
        $backupFileDir = Split-Path $backupFile -Parent
        New-Item -ItemType Directory -Path $backupFileDir -Force | Out-Null
        Copy-Item $targetFile $backupFile -Force
        Write-Host "  Backed up: $relativePath" -ForegroundColor Gray
    }
}

# Copy new files
Write-Host "`nCopying files to production..." -ForegroundColor Green
Copy-Item "$sourceDir\*" $targetDir -Recurse -Force
Write-Host "Files copied successfully!" -ForegroundColor Green

# Navigate to docker directory
Set-Location "$targetDir\docker"

if ($Rebuild) {
    Write-Host "`nRebuilding Docker image..." -ForegroundColor Yellow
    docker-compose build
    Write-Host "`nRestarting container with new image..." -ForegroundColor Yellow
    docker-compose down
    docker-compose up -d
} else {
    Write-Host "`nRestarting container (hot reload)..." -ForegroundColor Yellow
    docker-compose restart
}

Start-Sleep -Seconds 5

Write-Host "`n--- Container Status ---" -ForegroundColor Cyan
docker-compose ps

Write-Host "`n--- Recent Logs ---" -ForegroundColor Cyan
docker-compose logs --tail=20

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "   Update Applied Successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "`nBackup location: $backupDir" -ForegroundColor Yellow
Write-Host "RIS accessible at: https://ris.radiology2u.com.au" -ForegroundColor White
Write-Host ""
