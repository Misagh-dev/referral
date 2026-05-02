# Production Setup Documentation

This branch (`production-setup`) contains the working production configuration for the RIS application deployed on your Windows server with Cloudflare Tunnel.

## What Changed from Original Repo

### Code Improvements
1. **referral.py**: Enhanced `_user_email()` function for better Streamlit 1.56.0 compatibility
   - Added fallback for both attribute and dict-like access
   - Handles different Streamlit user object formats

### Infrastructure
1. **docker-compose.yml**: Simplified configuration (no IPv6 network needed)
2. **.gitignore**: Added `docker/.env` to prevent committing database credentials
3. **update-ris.ps1**: Automated update script for pulling changes

## Files NOT in Repository (Must Recreate)

These files contain sensitive credentials and are excluded from git:

### 1. `.streamlit/secrets.toml`
Contains Auth0 authentication and allowed users:

```toml
allowed_emails = ["your.email@example.com"]

[auth]
redirect_uri  = "https://ris.radiology2u.com.au/oauth2callback"
cookie_secret = "generate_random_32_char_string"

[auth.auth0]
client_id           = "YOUR_AUTH0_CLIENT_ID"
client_secret       = "YOUR_AUTH0_CLIENT_SECRET"
server_metadata_url = "https://YOUR_DOMAIN.au.auth0.com/.well-known/openid-configuration"
```

**For localhost development**, change:
```toml
redirect_uri = "http://localhost:8501/oauth2callback"
```

### 2. `docker/.env`
Contains database connection string:

```env
DATABASE_URL=postgresql://postgres.xxx:PASSWORD@aws-1-ap-southeast-2.pooler.supabase.com:6543/postgres
```

## Production Server Setup

### Current Configuration
- **Server**: Windows PC (sometimes powered off)
- **Database**: Supabase PostgreSQL (cloud, always available)
- **File Storage**: Docker volume `ris_storage` (local persistent)
- **Public Access**: Cloudflare Tunnel
  - Local: http://localhost:8501
  - Public: https://ris.radiology2u.com.au

### Services Running
```powershell
# RIS Docker container
docker-compose up -d  # in C:\Users\User\Desktop\ris\referral\docker

# Cloudflare Tunnel (routes both PACS and RIS)
cloudflared tunnel --config C:\Users\User\.cloudflared\config.yml run pacs
```

### Cloudflare Tunnel Config
Located at: `C:\Users\User\.cloudflared\config.yml`

```yaml
tunnel: c3e666b9-eeea-4f51-b0e1-d21e64ac67a6
credentials-file: C:\Users\user\.cloudflared\c3e666b9-eeea-4f51-b0e1-d21e64ac67a6.json

ingress:
  - hostname: ris.radiology2u.com.au
    service: http://127.0.0.1:8501
  - hostname: pacs.radiology2u.com.au
    service: http://127.0.0.1:80
  - service: http_status:404
```

## Development Workflow

### On Dev PC

1. **Clone the repository**:
   ```powershell
   git clone https://github.com/Misagh-dev/referral.git
   cd referral
   git checkout production-setup
   ```

2. **Create secrets files**:
   ```powershell
   # Copy template
   Copy-Item docker/secrets.toml.example .streamlit/secrets.toml
   
   # Edit with your credentials
   code .streamlit/secrets.toml
   
   # For dev, use localhost callback
   # redirect_uri = "http://localhost:8501/oauth2callback"
   ```

3. **Create .env file**:
   ```powershell
   # Create docker/.env
   echo "DATABASE_URL=postgresql://postgres.xxx:PASSWORD@aws-1-ap-southeast-2.pooler.supabase.com:6543/postgres" > docker/.env
   ```

4. **Run locally**:
   ```powershell
   cd docker
   docker-compose up
   ```

5. **Make changes and test**

6. **Commit and push**:
   ```powershell
   git add <changed-files>
   git commit -m "Description of changes"
   git push origin production-setup
   ```

### On Production Server

1. **Pull updates**:
   ```powershell
   C:\Users\User\Desktop\ris\referral\update-ris.ps1
   ```

   Or manually:
   ```powershell
   cd C:\Users\User\Desktop\ris\referral
   git pull origin production-setup
   cd docker
   docker-compose build
   docker-compose down
   docker-compose up -d
   ```

## Auth0 Configuration

**Dashboard**: https://manage.auth0.com/

### Allowed Callback URLs
```
https://ris.radiology2u.com.au/oauth2callback, http://localhost:8501/oauth2callback
```

### Allowed Logout URLs
```
https://ris.radiology2u.com.au, http://localhost:8501
```

### Allowed Web Origins
```
https://ris.radiology2u.com.au, http://localhost:8501
```

## Data Persistence

✅ **Safe during container rebuilds**:
- Patient records (Supabase PostgreSQL)
- Referral metadata (Supabase PostgreSQL)
- Uploaded PDF files (Docker volume: `ris_storage`)
- Settings (Supabase PostgreSQL)

⚠️ **Replaced during updates**:
- Application code
- Python packages
- UI components

## Troubleshooting

### RIS not accessible after update
```powershell
cd C:\Users\User\Desktop\ris\referral\docker
docker-compose logs --tail=50
docker-compose restart
```

### Cloudflare Tunnel not routing
```powershell
# Check if tunnel is running
Get-Process cloudflared

# Restart tunnel
Stop-Process -Name cloudflared -Force
cloudflared tunnel --config C:\Users\User\.cloudflared\config.yml run pacs
```

### Database connection issues
- Verify `docker/.env` has correct Supabase connection string
- Check Supabase pooler endpoint: `aws-1-ap-southeast-2.pooler.supabase.com:6543`
- Ensure using transaction pooler (port 6543, not 5432)

## Important Notes

1. **Never commit secrets**: `.streamlit/secrets.toml` and `docker/.env` are in `.gitignore`
2. **Database is cloud-based**: Data persists even when server is off
3. **File storage is local**: Uploaded files only available when server is running
4. **Dual access**: Works both locally (localhost:8501) and publicly (ris.radiology2u.com.au)

## Contact

Original repository: https://github.com/Misagh-dev/referral
Branch: `docker-self-hosted` (upstream)
Production branch: `production-setup` (this branch)
