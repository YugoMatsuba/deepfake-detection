# Production Deployment Guide

**Target Audience:** On-site deployment team with access to production Linux VM
**Prerequisites:** Docker and Docker Compose installed on target machine
**Estimated Time:** 30-45 minutes for first deployment

---

## Overview

This guide walks through deploying the Deepfake Detection system on a production Linux VM. Follow these steps in order - they're designed to catch issues early.

**What you're deploying:**
- PostgreSQL 15 database (persistent storage via Docker-managed volume)
- Flask backend with Gunicorn (deepfake detection API)
- Nginx reverse proxy (serves React frontend + proxies API requests)

**What persists across restarts:**
- PostgreSQL database (Docker-managed volume - survives container restarts/recreates)
- Analysis data: uploaded videos, frames, forensic overlays (`/var/lib/deepfake/data` bind mount)

**Network exposure:**
- Nginx exposes port 80 (HTTP) on the host machine
- Backend and database are internal (not exposed to network)

---

## Important: Production Networking (Infrastructure Team)

**This guide covers application deployment only.** The following networking/security tasks are **outside the scope** of this guide and should be handled by your infrastructure/IT team:

- ✅ **HTTPS/SSL certificates** - Use Cloudflare, Let's Encrypt, or a reverse proxy
- ✅ **Firewall configuration** - Restrict access to port 80 (or use internal network only)
- ✅ **Domain/DNS setup** - Point your domain to the server IP
- ✅ **Load balancing** - If you need multiple instances
- ✅ **DDoS protection** - Cloudflare, AWS Shield, etc.

**Recommended architecture for internet-facing deployment:**
```
Internet → [Load Balancer/Cloudflare with HTTPS] → [Server Firewall] → Your Docker Stack (port 80)
```

**For internal-only deployment:**
- Server accessible only from company network
- No HTTPS needed if internal traffic is trusted
- Still recommend firewall rules to restrict access

**Ports exposed by this stack:**
- `80` (nginx) - Frontend + API proxy (exposed to host)
- `5050` (backend) - Internal only, not exposed
- `5432` (postgres) - Internal only, not exposed

---

## Pre-Deployment Checklist

Before starting, ensure you have:

- [ ] Root/sudo access to the Linux VM
- [ ] Docker Engine 20.10+ installed (`docker --version`)
- [ ] Docker Compose v2.0+ installed (`docker compose version`)
- [ ] Git installed (to clone repo) or deployment package provided
- [ ] Network access for pulling Docker images
- [ ] Firewall rules configured (if applicable)

---

## Step 1: Prepare Host Machine

### 1.1 Create Persistent Data Directory

```bash
# Create directory for analysis data (videos, frames, overlays)
sudo mkdir -p /var/lib/deepfake/data

# Set ownership to UID 1000 (first non-root user in container)
sudo chown -R 1000:1000 /var/lib/deepfake/data

# Verify permissions
ls -ld /var/lib/deepfake/data
# Should show: drwxr-xr-x ... 1000 1000 ... /var/lib/deepfake/data
```

**Why `/var/lib/deepfake/data`?**
- Standard Linux location for application state (FHS-compliant)
- Outside Docker's managed storage (easier to backup/migrate)
- Survives container and Docker upgrades

**Why `chown 1000:1000`?**
- Container runs as UID 1000 by default
- Prevents permission denied errors when writing files

### 1.2 Install Docker (if not already installed)

```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Log out and back in for group membership to take effect

# Verify
docker --version
docker compose version
```

---

## Step 2: Clone Repository or Extract Deployment Package

```bash
# Option A: Clone from git
git clone https://github.com/your-org/deepfake_AI.git
cd deepfake_AI

# Option B: Extract provided deployment package
tar -xzf deepfake-deployment.tar.gz
cd deepfake_AI
```

---

## Step 3: Generate Production Secrets

**CRITICAL:** Do not use default passwords or example secrets in production!

### 3.1 Generate Secret Key (Flask Session Signing)

```bash
# Generate cryptographically random 64-character hex string
python3 -c "import secrets; print(secrets.token_hex(32))"

# Example output: a7f3c2e1b9d4f6a8c3e5d7b9f1a3c5e7d9b1f3a5c7e9b2d4f6a8c1e3d5b7f9a1
# Save this - you'll add it to .env file
```

### 3.2 Generate PostgreSQL Password

```bash
# Generate strong random password
openssl rand -base64 32

# Example output: Xk9mN2pQ8rL5vF3wT6yH4bC1dE7gJ9sA2fK5nM8pR0qU=
# Save this - you'll add it to .env file
```

### 3.3 (Optional) Generate Owner Password

```bash
# For initial owner account creation
openssl rand -base64 16

# Example output: vH3xK9mL2pQ5rT8w
```

---

## Step 4: Configure Environment Variables

### 4.1 Create Production .env File

```bash
# Navigate to deploy directory
cd deploy

# Copy example template
cp .env.example .env

# Edit with your preferred editor
nano .env  # or vim .env
```

**Important:** The deployment configuration lives in `deploy/.env` (NOT the root `.env`). The root `.env` is for local development only.

### 4.2 Required Configuration

Edit `deploy/.env` and set these values (replace `CHANGE_ME` with your generated secrets):

```bash
# === SECURITY (REQUIRED - Generate with commands from Step 3) ===
SECRET_KEY=PASTE_GENERATED_SECRET_KEY_HERE

# === POSTGRESQL DATABASE (REQUIRED) ===
# Generate password with: openssl rand -base64 32
POSTGRES_USER=deepfake
POSTGRES_PASSWORD=PASTE_GENERATED_POSTGRES_PASSWORD_HERE
POSTGRES_DB=deepfake_prod

# Database connection string (update password to match above)
DATABASE_URL=postgresql+psycopg://deepfake:PASTE_GENERATED_POSTGRES_PASSWORD_HERE@db:5432/deepfake_prod

# === DATA STORAGE (REQUIRED) ===
# Container path (do not change)
DATA_DIR=/data

# Host path for analysis data bind mount (must match Step 1 directory)
DATA_VOLUME_PATH=/var/lib/deepfake/data

# NOTE: PostgreSQL data uses Docker-managed volume (no host path configuration needed)

# === PERFORMANCE ===
# Set to (total CPU cores - 2) to leave headroom for system
FORENSICS_WORKERS=6

# Device for ML inference
DEVICE=cpu  # or 'cuda' if you have NVIDIA GPU with drivers

# === ENVIRONMENT ===
ENVIRONMENT=production
PORT=5050

# === CORS (adjust for your domain) ===
# Include protocol (https://) and NO trailing slashes
CORS_ORIGINS=http://localhost

# === DATABASE BOOTSTRAP ===
# MUST be 0 in production (use migrations instead)
DB_BOOTSTRAP=0

# === OWNER ACCOUNT BOOTSTRAP (First Deployment Only) ===
# Set ALLOW_OWNER_TRANSFER=1 for initial deployment
# After first login, set ALLOW_OWNER_TRANSFER=0 and restart to prevent account takeover
OWNER_USERNAME=admin
OWNER_SEED_PASSWORD=PASTE_GENERATED_OWNER_PASSWORD_HERE
ALLOW_OWNER_TRANSFER=1
```

### 4.3 Secure the .env File

```bash
# Restrict permissions (only owner can read)
chmod 600 .env

# Verify
ls -l .env
# Should show: -rw------- ... .env
```

**Security Notes:**
- ✅ Never commit `.env` to git (already in `.gitignore`)
- ✅ Store backup of secrets securely (password manager, secrets vault)
- ✅ After first deployment, remove `OWNER_USERNAME` and `OWNER_SEED_PASSWORD` from `.env`

---

## Step 5: Build Docker Images

```bash
# Navigate to deploy directory (if not already there)
cd deploy

# Build all images (backend + nginx)
docker compose build

# This will take 5-10 minutes (downloads PyTorch, OpenCV, builds frontend)
# Backend image size: ~2.5GB (includes ML models)
# Nginx image size: ~50MB (frontend + nginx)
```

### 5.1 Verify Model Files Are Included

```bash
# Check ML weights (should show ~84MB each for xception/spsl, ~179MB for ucf)
docker compose run --rm backend ls -lh /workspaces/deepfake_AI/ml/weights/

# Check dlib model (should show ~19MB)
docker compose run --rm backend ls -lh /workspaces/deepfake_AI/ml/dlib/

# If files are missing or show small sizes (<1MB):
# - Check .dockerignore doesn't exclude them
# - Verify Git LFS pulled the files: git lfs pull (from repo root)
# - Rebuild image: docker compose build --no-cache
```

---

## Step 6: Initialize Database

**Important:** All commands from this point forward assume you are in the `deploy/` directory where `docker-compose.yml` is located. If you're not there: `cd deploy`

### 6.1 Start PostgreSQL Only

```bash
# Start just the database service (from deploy/ directory)
docker compose up -d db

# Wait for postgres to be ready (watch logs)
docker compose logs -f db

# Look for: "database system is ready to accept connections"
# Press Ctrl+C when you see it
```

### 6.2 Run Database Migrations

```bash
# Run Alembic migrations to create tables
docker compose run --rm backend bash -c "cd backend && alembic upgrade head"

# Expected output:
# INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
# INFO  [alembic.runtime.migration] Will assume transactional DDL.
# INFO  [alembic.runtime.migration] Running upgrade  -> abc123, initial tables
# ...
```

**If migrations fail:**
- Check DATABASE_URL in `deploy/.env` is correct
- Verify db service is running: `docker compose ps`
- Check db logs: `docker compose logs db`

---

## Step 7: Start All Services

```bash
# Start all services (backend, db, nginx)
docker compose up -d

# Verify all services are running
docker compose ps

# Should show:
# NAME                  STATUS
# deepfake_db          Up (healthy)
# deploy-backend-1     Up
# deploy-nginx-1       Up
```

### 7.1 Check Logs

```bash
# Watch backend logs for startup issues
docker compose logs -f backend

# Look for:
# ✓ Created owner user: admin  (if OWNER_USERNAME was set)
# [INFO] Starting gunicorn 20.1.0
# [INFO] Listening at: http://0.0.0.0:5050
```

**Common startup messages (normal):**
- "No owner bootstrap" - OK if `OWNER_USERNAME` not set
- "Owner already exists" - OK after first deployment

**Error messages to investigate:**
- "Connection refused" → postgres not ready, check `depends_on` in compose
- "Permission denied" → check `/var/lib/deepfake/data` ownership (Step 1.1)
- "Face detection model not found" → model files missing from image (Step 5.1)

---

## Step 8: Verify Deployment

### 8.1 Test Backend Health

```bash
# Test API is responding
curl http://localhost:5050/api/auth/me

# Expected response:
# {"authenticated": false}

# If you get connection refused:
# - Check backend is running: docker compose ps
# - Check backend logs: docker compose logs backend
# - Verify port 5050 is exposed in docker-compose.yml
```

### 8.2 Test Database Connection

```bash
# Check backend can connect to postgres
docker compose exec backend bash -c "cd backend && python -c \"
from api.db import init_engine, get_db
from api.models import User
init_engine()
with get_db() as db:
    count = db.query(User).count()
    print(f'Users in database: {count}')
\""

# Should print: Users in database: 1 (the owner account)
```

### 8.3 Test Volume Mount

```bash
# Verify /data is mounted correctly
docker compose exec backend ls -la /data

# Should show: drwxr-xr-x ... 1000 1000 ... analyses
# (or empty if no uploads yet)

# Test write permissions
docker compose exec backend touch /data/test.txt
ls /var/lib/deepfake/data/
# Should see test.txt

# Cleanup
docker compose exec backend rm /data/test.txt
```

### 8.4 Test Data Persistence

**Critical test - ensures data survives restarts:**

```bash
# 1. Create test file via backend
docker compose exec backend bash -c "echo 'persistence test' > /data/test-persist.txt"

# 2. Verify it exists on host
cat /var/lib/deepfake/data/test-persist.txt
# Should print: persistence test

# 3. Restart backend container
docker compose restart backend

# 4. Check file still exists
docker compose exec backend cat /data/test-persist.txt
# Should still print: persistence test

# 5. Stop and remove containers
docker compose down

# 6. File should STILL exist on host
cat /var/lib/deepfake/data/test-persist.txt
# Should still print: persistence test

# 7. Cleanup
rm /var/lib/deepfake/data/test-persist.txt
```

**If persistence test fails:**
- Check volume configuration in docker-compose.yml
- Verify `DATA_VOLUME_PATH` in `.env` matches Step 1 directory
- Check `docker volume inspect` output for mount point

---

## Step 9: Configure Firewall (if applicable)

```bash
# Allow HTTP (port 80) and HTTPS (port 443) if using nginx
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Or allow backend directly (not recommended for production)
sudo ufw allow 5050/tcp

# Verify rules
sudo ufw status
```

---

## Step 10: SSL/TLS Setup (HTTPS)

**If using nginx reverse proxy**, set up SSL certificates:

### Option A: Let's Encrypt (Free, Automated)

```bash
# Install certbot
sudo apt-get install certbot python3-certbot-nginx

# Generate certificate (interactive)
sudo certbot --nginx -d deepfake.your-domain.com

# Auto-renewal (certbot sets up cron job automatically)
sudo certbot renew --dry-run
```

### Option B: Existing Certificate

```bash
# Copy cert files to nginx volume
sudo cp your-cert.crt /path/to/nginx/ssl/
sudo cp your-key.key /path/to/nginx/ssl/

# Update nginx.conf to reference these files
# Restart nginx: docker compose restart nginx
```

---

## Step 11: Post-Deployment Configuration

### 11.1 Remove Bootstrap Secrets (Security)

After successful first deployment:

```bash
# Edit .env and comment out or remove:
nano .env

# Remove these lines (or comment with #):
# OWNER_USERNAME=admin
# OWNER_SEED_PASSWORD=...
# ALLOW_OWNER_TRANSFER=0

# Restart backend to apply
docker compose restart backend
```

### 11.2 Set Up Log Rotation (Optional)

```bash
# Docker logs can grow large over time
# Configure log rotation in docker-compose.yml:

# Add to each service:
#   logging:
#     driver: "json-file"
#     options:
#       max-size: "10m"
#       max-file: "3"

# Or configure Docker daemon globally:
sudo nano /etc/docker/daemon.json

# Add:
# {
#   "log-driver": "json-file",
#   "log-opts": {
#     "max-size": "10m",
#     "max-file": "3"
#   }
# }

# Restart Docker daemon
sudo systemctl restart docker
docker compose up -d  # Restart containers
```

---

## Operational Procedures

### Starting Services

```bash
cd /path/to/deepfake_AI
docker compose up -d
```

### Stopping Services

```bash
docker compose down

# To also remove volumes (DANGER - deletes data!):
# docker compose down -v
```

### Viewing Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f backend

# Last 100 lines
docker compose logs --tail=100 backend
```

### Restarting a Service

```bash
# Restart backend only
docker compose restart backend

# Restart all services
docker compose restart
```

### Updating the Application

```bash
# 1. Pull latest code
git pull origin main  # or extract new deployment package

# 2. Rebuild images (from deploy/ directory)
cd deploy
docker compose build

# 3. Stop services
docker compose down

# 4. Run any new migrations
docker compose up -d db
docker compose run --rm backend bash -c "cd backend && alembic upgrade head"

# 5. Start all services with new images
docker compose up -d

# 6. Verify
docker compose logs -f backend
docker compose logs -f nginx
```

---

## Backup Procedures

### Backing Up Analysis Data

```bash
# Create timestamped backup
sudo tar -czf deepfake-data-backup-$(date +%Y%m%d).tar.gz /var/lib/deepfake/data

# Copy to safe location
scp deepfake-data-backup-*.tar.gz user@backup-server:/backups/
```

### Backing Up PostgreSQL Database

```bash
# Backup database to file (adjust credentials to match deploy/.env)
docker compose exec db pg_dump -U deepfake deepfake_prod > deepfake-db-backup-$(date +%Y%m%d).sql

# Or as postgres user:
docker compose exec -u postgres db pg_dump deepfake_prod > backup.sql

# Copy to safe location
scp deepfake-db-backup-*.sql user@backup-server:/backups/
```

**Note:** PostgreSQL data is stored in a Docker-managed volume. Regular `pg_dump` backups are recommended over filesystem-level volume backups.

### Restoring from Backup

```bash
# Restore analysis data (from host directory backup)
sudo tar -xzf deepfake-data-backup-YYYYMMDD.tar.gz -C /

# Restore database (adjust credentials to match deploy/.env)
cat deepfake-db-backup-YYYYMMDD.sql | docker compose exec -T db psql -U deepfake deepfake_prod
```

---

## Troubleshooting

### Backend won't start

**Symptom:** `docker compose ps` shows backend as "Exited" or "Restarting"

**Solutions:**
```bash
# Check logs for error message
docker compose logs backend

# Common issues:
# 1. Can't connect to postgres
#    → Verify DATABASE_URL in .env
#    → Check postgres is healthy: docker compose ps

# 2. Permission denied on /data
#    → Check: ls -ld /var/lib/deepfake/data
#    → Fix: sudo chown -R 1000:1000 /var/lib/deepfake/data

# 3. Missing environment variables
#    → Verify .env file exists and is readable
#    → Check required vars are set (see Step 4)
```

### CORS Errors in Frontend

**Symptom:** Frontend shows "blocked by CORS policy"

**Solutions:**
```bash
# 1. Check CORS_ORIGINS in .env matches frontend URL exactly
#    - Include protocol (https://)
#    - No trailing slashes
#    - Both www and non-www if needed

# 2. Restart backend after changing .env
docker compose restart backend

# 3. Check backend logs confirm CORS origins
docker compose logs backend | grep CORS
```

### "Face detection model not found" Error

**Symptom:** Analysis fails with "PREDICTOR_NOT_FOUND"

**Solutions:**
```bash
# 1. Verify model files in image
docker run --rm deepfake:latest ls -lh /workspaces/deepfake_AI/ml/dlib/

# 2. If missing, rebuild image (Git LFS may not have pulled files)
git lfs pull
docker build -t deepfake:latest .

# 3. Restart backend
docker compose up -d backend
```

### Container Can't Write to /data

**Symptom:** "Permission denied" when uploading videos

**Solutions:**
```bash
# Fix host directory ownership
sudo chown -R 1000:1000 /var/lib/deepfake/data

# Verify permissions
ls -ld /var/lib/deepfake/data
# Should show: drwxr-xr-x ... 1000 1000

# Restart backend
docker compose restart backend
```

### PostgreSQL Container Won't Start

**Symptom:** postgres service stuck in "starting" or "unhealthy"

**Solutions:**
```bash
# Check logs
docker compose logs postgres

# Common issues:
# 1. Data directory corruption
#    → Nuclear option: docker compose down -v (DELETES DATA!)
#    → Then: docker compose up -d postgres

# 2. Port 5432 already in use
#    → Check: sudo lsof -i :5432
#    → Stop conflicting service or change port in compose
```

### Data Not Persisting After Restart

**Symptom:** Uploaded videos disappear after `docker compose restart`

**Solutions:**
```bash
# 1. Check volume mount
docker compose exec backend mount | grep /data

# 2. Verify volume configuration
docker volume inspect deepfake_ai_analyses-data

# 3. Check host directory wasn't deleted
ls -la /var/lib/deepfake/data/

# 4. Verify docker-compose.yml has volume mount:
#    volumes:
#      - analyses-data:/data
```

---

## System Requirements

**Minimum:**
- 4 CPU cores
- 8GB RAM
- 50GB disk space
- Ubuntu 20.04+ or CentOS 8+

**Recommended:**
- 8+ CPU cores
- 16GB RAM
- 100GB+ SSD
- NVIDIA GPU with CUDA 11.3+ (for ML acceleration)

---

## Security Checklist

Before going live:

- [ ] All default passwords changed (postgres, owner account)
- [ ] SECRET_KEY is random 64-character hex string
- [ ] `.env` file permissions set to 600
- [ ] `ALLOW_OWNER_TRANSFER=0` in production
- [ ] SSL/TLS enabled for HTTPS
- [ ] Firewall configured (only necessary ports open)
- [ ] Backups configured and tested
- [ ] Log rotation enabled
- [ ] `DB_BOOTSTRAP=0` (never 1 in production)
- [ ] Owner bootstrap secrets removed from `.env` after first deployment

---

## Support

If you encounter issues not covered in this guide:

1. Check logs: `docker compose logs -f`
2. Verify configuration: `cat .env` (redact secrets before sharing)
3. Test components individually (postgres, backend separately)
4. Contact development team with:
   - Error messages from logs
   - Output of `docker compose ps`
   - Output of `docker compose config` (redact secrets)

---

## Quick Reference Commands

```bash
# Start services
docker compose up -d

# Stop services
docker compose down

# View logs
docker compose logs -f backend

# Restart backend
docker compose restart backend

# Run migrations
docker compose run --rm backend bash -c "cd backend && alembic upgrade head"

# Backup database
docker compose exec postgres pg_dump -U deepfake_user deepfake_db > backup.sql

# Backup data
sudo tar -czf data-backup.tar.gz /var/lib/deepfake/data

# Check disk usage
docker system df
du -sh /var/lib/deepfake/data

# Clean up old images/containers
docker system prune -a
```

---

**Deployment Complete!** 🎉

Access the application at `http://your-server-ip:5050/api/auth/me` (or via nginx if configured).
