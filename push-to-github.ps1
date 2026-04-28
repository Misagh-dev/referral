# Push RIS Changes to GitHub
# This script commits your safe code changes and pushes to a new branch

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "   Push RIS Changes to GitHub" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Navigate to RIS directory
Set-Location C:\Users\User\Desktop\ris\referral

# Check current status
Write-Host "Current Changes:" -ForegroundColor Yellow
git status --short

# Create a new branch for your production setup
$branchName = "production-setup"
Write-Host "`n--- Creating/Switching to branch: $branchName ---" -ForegroundColor Green

git checkout -b $branchName 2>$null
if ($LASTEXITCODE -ne 0) {
    # Branch exists, just switch to it
    git checkout $branchName
}

Write-Host "`n--- Adding Safe Changes ---" -ForegroundColor Green

# Add only safe files (NOT secrets!)
git add .gitignore
git add referral.py
git add docker/secrets.toml.example
git add update-ris.ps1

Write-Host "`nFiles staged for commit:" -ForegroundColor Yellow
git status --short

Write-Host "`n--- Files that will NOT be committed (secrets): ---" -ForegroundColor Red
Write-Host "  ✗ .streamlit/secrets.toml (contains Auth0 credentials)" -ForegroundColor Red
Write-Host "  ✗ docker/.env (contains database password)" -ForegroundColor Red

Write-Host "`n--- Creating Commit ---" -ForegroundColor Green
git commit -m "Production setup improvements

- Enhanced _user_email() function for better Streamlit compatibility
- Added docker/.env to .gitignore for security
- Added update script for easy deployments"

if ($LASTEXITCODE -ne 0) {
    Write-Host "`nNothing to commit (changes may already be committed)" -ForegroundColor Yellow
}

Write-Host "`n--- Pushing to GitHub ---" -ForegroundColor Green
git push -u origin $branchName

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n========================================" -ForegroundColor Green
    Write-Host "   Successfully Pushed to GitHub!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "`nBranch: $branchName" -ForegroundColor White
    Write-Host "You can now clone this on your dev PC and continue development." -ForegroundColor White
    Write-Host "`nIMPORTANT: Remember to recreate these files on your dev PC:" -ForegroundColor Yellow
    Write-Host "  - .streamlit/secrets.toml (copy from this PC or use template)" -ForegroundColor Yellow
    Write-Host "  - docker/.env (DATABASE_URL=your_supabase_connection)" -ForegroundColor Yellow
} else {
    Write-Host "`nPush failed. Check if you have push access to the repository." -ForegroundColor Red
}

Write-Host ""
