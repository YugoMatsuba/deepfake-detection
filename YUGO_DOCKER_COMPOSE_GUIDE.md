# Docker Compose Orchestration Guide (For Yugo)

**Author:** Finn
**Date:** 2025-10-31
**Branch:** `mount-disk`

---

## Overview

This guide is for **setting up the docker-compose orchestration** that the on-site deployment team will use. You are NOT deploying to production machines - you're building the compose file and testing it locally.

The on-site devs will receive:
1. The `docker-compose.yml` you create
2. A separate `DEPLOYMENT.md` with step-by-step deployment instructions
3. An `.env.example` file they'll customize for their environment

---

## What's Already Done (Data Persistence Setup)

I've set up the foundation for persistent data storage. Here's what was changed:

### 1. Dockerfile - Production Ready
- ✅ Added `COPY . /workspaces/deepfake_AI` to include application code in image
- ✅ Created `/data` directory as volume mount point
- ✅ Added `VOLUME ["/data"]` declaration
- ✅ ML model files (`.pth` and `.dat`) are baked into the image (~400MB total)

### 2. .env.example - Configuration Template
- ✅ Added `DATA_VOLUME_PATH=/var/lib/deepfake/data` with setup instructions
- ✅ Documents all required environment variables
- ✅ Includes comments explaining host vs container paths

### 3. docker-compose.volumes.yml - Minimal Volume Example
- ✅ Shows data volume configuration using named volumes
- ✅ Uses `/var/lib/deepfake/data` (standard Linux FHS location)
- ✅ Configurable via `DATA_VOLUME_PATH` env var with sensible default
- ✅ **This is your starting point - merge into full compose file**

### 4. README.md - Updated
- ✅ Production deployment section with prerequisites
- ✅ Removed all SQLite references (PostgreSQL only)

---

## Your Task: Build Full Docker Compose Stack

Take `docker-compose.volumes.yml` and expand it into a complete orchestration with:
- PostgreSQL database service
- Backend service (Flask + Gunicorn)
- Nginx reverse proxy (optional but recommended)
- Networks and health checks

### Key Requirements

**Environment Configuration:**
- ✅ All config via `.env` file (use `--env-file .env`)
- ✅ No hardcoded secrets in docker-compose.yml
- ✅ Support for configurable `FORENSICS_WORKERS` (multiprocessing)
- ✅ Support for `OWNER_USERNAME`/`OWNER_SEED_PASSWORD` (initial setup)
- ✅ All variables documented in `.env.example`

**Data Persistence:**
- ✅ Named volume for analysis data (`/data` in container)
- ✅ Named volume for PostgreSQL data
- ✅ Volumes survive container restarts

**Networking:**
- ✅ Internal network for backend ↔ postgres communication
- ✅ Backend uses service name `postgres:5432` for DATABASE_URL
- ✅ Only expose necessary ports (nginx: 80/443, or backend: 5050 for testing)

---

## Step 1: Understand What's in docker-compose.volumes.yml

```yaml
services:
  backend:
    image: deepfake:latest
    volumes:
      - analyses-data:/data  # This is the key volume mount
    environment:
      - DATA_DIR=/data  # Container path (don't change)
      - DATABASE_URL=postgresql+psycopg://user:pass@postgres:5432/db
      # ... other env vars

volumes:
  analyses-data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: ${DATA_VOLUME_PATH:-/var/lib/deepfake/data}  # Host path
```

**Key Points:**
- `analyses-data` is a named volume that wraps a bind mount
- Host path comes from `DATA_VOLUME_PATH` env var (defaults to `/var/lib/deepfake/data`)
- Container always sees it at `/data` (via `DATA_DIR` env var)

---

## Step 2: Add PostgreSQL Service

```yaml
services:
  postgres:
    image: postgres:16
    container_name: deepfake_postgres
    volumes:
      - postgres-data:/var/lib/postgresql/data
    environment:
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=${POSTGRES_DB}
    networks:
      - app-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres-data:
    driver: local
```

**Important:**
- Use env vars for credentials (never hardcode)
- Add healthcheck so backend waits for postgres to be ready
- Postgres volume is Docker-managed (not bind mount) - simpler for DB files

---

## Step 3: Complete Backend Service

Expand the backend service from `docker-compose.volumes.yml`:

```yaml
services:
  backend:
    image: deepfake:latest
    container_name: deepfake_backend
    depends_on:
      postgres:
        condition: service_healthy  # Wait for postgres healthcheck
    volumes:
      - analyses-data:/data
    environment:
      # Database
      - DATABASE_URL=postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      - DB_BOOTSTRAP=0  # MUST be 0 in production (use Alembic migrations)

      # Data storage
      - DATA_DIR=/data

      # Flask config
      - SECRET_KEY=${SECRET_KEY}
      - ENVIRONMENT=production
      - CORS_ORIGINS=${CORS_ORIGINS}

      # Performance
      - FORENSICS_WORKERS=${FORENSICS_WORKERS:-6}
      - DEVICE=${DEVICE:-cpu}

      # Owner bootstrap (optional - only for initial setup)
      - OWNER_USERNAME=${OWNER_USERNAME:-}
      - OWNER_SEED_PASSWORD=${OWNER_SEED_PASSWORD:-}
      - ALLOW_OWNER_TRANSFER=${ALLOW_OWNER_TRANSFER:-0}

    ports:
      - "5050:5050"  # Expose directly, or remove if behind nginx

    networks:
      - app-network

    restart: unless-stopped

    command: gunicorn --config backend/gunicorn.conf.py --chdir backend wsgi:app

networks:
  app-network:
    driver: bridge
```

**Key Points:**
- `depends_on` with `condition: service_healthy` ensures postgres is ready
- DATABASE_URL uses service name `postgres:5432` (not `localhost`)
- `DB_BOOTSTRAP=0` - migrations handled separately (see DEPLOYMENT.md)
- All sensitive config comes from `.env` file
- `restart: unless-stopped` for automatic recovery

---

## Step 4: Add Nginx (Optional but Recommended)

If you want nginx as reverse proxy:

```yaml
services:
  nginx:
    image: nginx:alpine
    container_name: deepfake_nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro  # SSL certs (if using HTTPS)
    depends_on:
      - backend
    networks:
      - app-network
    restart: unless-stopped
```

**Note:** If using nginx:
- Remove `ports` from backend service (keep it internal)
- Backend only accessible via nginx proxy
- On-site devs will need to set up SSL certs

---

## Step 5: Update .env.example

Make sure `.env.example` documents ALL variables used in compose:

```bash
# === PostgreSQL Database ===
POSTGRES_USER=deepfake_user
POSTGRES_PASSWORD=CHANGE_ME_STRONG_PASSWORD
POSTGRES_DB=deepfake_db

# === Database Connection (for backend) ===
# NOTE: Uses 'postgres:5432' (service name) in docker-compose
DATABASE_URL=postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}

# === Flask Security ===
# IMPORTANT: Generate random key for production!
# Run: python3 -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=GENERATE_RANDOM_64_CHAR_HEX

# === Environment ===
ENVIRONMENT=production

# === CORS (frontend domains) ===
# Comma-separated list of allowed origins
CORS_ORIGINS=https://your-frontend-domain.com,https://www.your-frontend-domain.com

# === Data Storage ===
DATA_DIR=/data  # Container path (don't change)
DATA_VOLUME_PATH=/var/lib/deepfake/data  # Host path (on-site devs may customize)

# === Performance ===
# Number of CPU cores for parallel forensics processing
# Recommendation: total_cores - 2 (leave headroom for Gunicorn)
FORENSICS_WORKERS=6

# Device for ML inference (cpu or cuda)
DEVICE=cpu

# === Database Bootstrap ===
# MUST be 0 in production (use Alembic migrations)
DB_BOOTSTRAP=0

# === Owner Account Bootstrap (OPTIONAL) ===
# Only needed for initial deployment or to change owner
# Leave empty for normal operation
OWNER_USERNAME=
OWNER_SEED_PASSWORD=
ALLOW_OWNER_TRANSFER=0  # Security: prevent ownership hijacking
```

---

## Step 6: Testing Locally (Mac)

Before handing off to deployment team, test your compose file locally.

### Build the Image

```bash
# From project root
docker build --platform linux/amd64 -t deepfake:latest .
```

**Note:** Use `--platform linux/amd64` on Apple Silicon Macs to avoid dlib/libpng ARM issues.

### Create Local .env File

```bash
# Copy example and customize for local testing
cp .env.example .env.local

# Edit .env.local:
# - Set SECRET_KEY to any value (e.g., "local-test-key")
# - Set POSTGRES_PASSWORD to "localpass123"
# - Set CORS_ORIGINS to "http://localhost:5173,http://127.0.0.1:5173"
# - Leave OWNER_USERNAME empty (already have owner in DB)
```

### Create Local Data Directory

```bash
# Mac uses ~/deepfake-data for testing (not /var/lib)
mkdir -p ~/deepfake-data

# Update .env.local:
DATA_VOLUME_PATH=~/deepfake-data  # Mac path
```

### Start the Stack

```bash
docker-compose --env-file .env.local up -d

# Watch logs
docker-compose logs -f
```

### Run Migrations (First Time Only)

```bash
docker-compose --env-file .env.local run --rm backend bash -c "cd backend && alembic upgrade head"
```

### Verify Everything Works

```bash
# Check all services are running
docker-compose ps

# Test backend health
curl http://localhost:5050/api/auth/me
# Should return: {"authenticated": false}

# Check volume mount
docker-compose exec backend ls -la /data
# Should show empty directory (or analyses/ if you uploaded videos)

# Upload a test video via frontend and verify:
ls ~/deepfake-data/analyses/
# Should see UUID directories with video files
```

### Cleanup

```bash
docker-compose down
# Or to remove volumes too:
docker-compose down -v
```

---

## Step 7: What NOT to Include in Docker Compose

These belong in DEPLOYMENT.md for on-site devs:

**Don't include in compose:**
- ❌ Host directory creation commands (`sudo mkdir`, `sudo chown`)
- ❌ Secret generation commands
- ❌ SSL certificate setup
- ❌ Firewall configuration
- ❌ Production `.env` file (only provide `.env.example`)

**Do include in compose:**
- ✅ Service definitions (postgres, backend, nginx)
- ✅ Volume declarations
- ✅ Network configuration
- ✅ Health checks and dependencies
- ✅ Restart policies

---

## Step 8: Handoff Checklist

Before giving to deployment team, ensure:

- [ ] `docker-compose.yml` uses `--env-file` pattern (no hardcoded secrets)
- [ ] `.env.example` documents all required variables with comments
- [ ] Tested locally on Mac with `.env.local`
- [ ] All services start and communicate correctly
- [ ] Volumes persist data across restarts
- [ ] README.md updated with any changes
- [ ] `DEPLOYMENT.md` exists with on-site deployment instructions

---

## Common Issues & Solutions

### Issue: Backend can't connect to postgres

**Solution:**
- Use `postgres:5432` (service name), not `localhost`
- Add `depends_on` with `service_healthy` condition
- Verify `app-network` is shared between services

### Issue: "Face detection model not found"

**Solution:**
- Verify `.dockerignore` doesn't exclude `ml/dlib/*.dat`
- Check model files exist in image: `docker run --rm deepfake:latest ls /workspaces/deepfake_AI/ml/dlib/`

### Issue: CORS errors in frontend

**Solution:**
- Set `CORS_ORIGINS` to match frontend domain exactly
- Include both `http://` and `https://` if needed
- No trailing slashes in URLs

### Issue: Permission denied for /var/lib/deepfake/data

**Solution:**
- This is for on-site devs to fix (see DEPLOYMENT.md)
- They need to run: `sudo chown -R 1000:1000 /var/lib/deepfake/data`

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `POSTGRES_USER` | Yes | - | PostgreSQL username |
| `POSTGRES_PASSWORD` | Yes | - | PostgreSQL password (generate strong random) |
| `POSTGRES_DB` | Yes | - | PostgreSQL database name |
| `SECRET_KEY` | Yes | - | Flask session signing key (64-char hex) |
| `CORS_ORIGINS` | Yes | - | Comma-separated frontend URLs |
| `DATA_VOLUME_PATH` | No | `/var/lib/deepfake/data` | Host directory for analysis data |
| `FORENSICS_WORKERS` | No | `6` | CPU cores for parallel processing |
| `DEVICE` | No | `cpu` | ML device (`cpu` or `cuda`) |
| `OWNER_USERNAME` | No | - | Initial owner account username |
| `OWNER_SEED_PASSWORD` | No | - | Initial owner password |
| `ALLOW_OWNER_TRANSFER` | No | `0` | Allow changing owner (security risk) |
| `DB_BOOTSTRAP` | No | `0` | Auto-create tables (MUST be 0 in prod) |
| `ENVIRONMENT` | No | `production` | Environment mode |

---

## Next Steps

1. **Build `docker-compose.yml`** from the examples above
2. **Test locally** on your Mac with `.env.local`
3. **Commit** to `mount-disk` branch:
   ```bash
   git add docker-compose.yml .env.example
   git commit -m "Add production docker-compose orchestration"
   ```
4. **Verify DEPLOYMENT.md exists** with on-site deployment instructions
5. **Hand off to deployment team** with:
   - `docker-compose.yml`
   - `.env.example`
   - `DEPLOYMENT.md`
   - This guide for reference

---

## Questions?

Contact Finn if anything is unclear. Focus on building a clean compose file that:
- Uses environment variables for all config
- Has no hardcoded secrets
- Works seamlessly with the volume setup already in place
- Can be deployed by following DEPLOYMENT.md step-by-step

Good luck! 🚀
