# Docker Compose Orchestration Guide (For Yugo)

**Author:** Finn
**Date:** 2025-10-31
**Branch:** `merge-nginx-volumes`
**Status:** ✅ COMPLETE - Full orchestration ready in `deploy/`

---

## Overview

**GOOD NEWS:** The docker-compose orchestration is complete and merged! This guide now documents what was built and how to test it.

The on-site deployment team will receive:
1. **`deploy/docker-compose.yml`** - Full orchestration (backend + db + nginx)
2. **`deploy/.env.example`** - Production environment template (Linux paths)
3. **`DEPLOYMENT.md`** - Step-by-step production deployment guide

**Key separation:**
- **`deploy/.env`** - Deployment configuration (for docker-compose)
- **Root `.env`** - Development configuration (for devcontainer)

---

## What's Been Built

### 1. Full Docker Compose Stack (`deploy/docker-compose.yml`)

**Services:**
- ✅ **backend** - Flask app running under Gunicorn
  - Uses production-ready Dockerfile
  - ML models baked into image (~2.5GB)
  - Mounts analysis data to `/data` via configurable bind mount
  - Platform: `linux/amd64` (for Mac M1/M2 testing compatibility)

- ✅ **db** - PostgreSQL 15
  - Docker-managed volume (no bind mount needed)
  - Healthcheck with retries
  - Credentials from `deploy/.env`

- ✅ **nginx** - Reverse proxy + static frontend
  - Multi-stage build (builds React frontend, serves via nginx)
  - Proxies `/api/*` requests to backend
  - Gzip compression and asset caching
  - Platform: `linux/amd64` (for Mac M1/M2 testing compatibility)

**Volumes:**
- `analyses-data` - Bind mount for videos/frames/reports (configurable via `DATA_VOLUME_PATH`)
- `pgdata` - Docker-managed volume for PostgreSQL (no host path needed)

### 2. Environment Configuration

**`deploy/.env.example` (Linux Production Template)**
- All required variables documented
- Uses Linux paths (`/var/lib/deepfake/data`)
- Includes security notes and password generation commands

**Root `.env.example` (Development)**
- SQLite database for local dev
- No deployment-specific vars (clean separation)

### 3. Documentation

**`DEPLOYMENT.md`**
- Step-by-step production deployment for on-site team
- Updated to reference `deploy/.env` (not root `.env`)
- All docker commands updated for `deploy/` directory context

---

## How to Test Locally (Mac)

The orchestration is ready to test! Here's how to run it on your Mac.

### Prerequisites
- Docker Desktop installed
- At least 8GB RAM allocated to Docker
- ~5GB free disk space (for images + volumes)

### Quick Start

```bash
# 1. Create host directory for analysis data
mkdir -p ~/deepfake-data

# 2. Navigate to deploy directory
cd deploy

# 3. Create .env from template (already done if you're on merge-nginx-volumes branch)
# The branch already has deploy/.env configured for Mac testing
# If you need to recreate it:
cp .env.example .env
# Then edit DATA_VOLUME_PATH=~/deepfake-data (or your home directory absolute path)

# 4. Build images (takes 5-10 minutes first time)
docker compose build

# 5. Start all services
docker compose up -d

# 6. Check status
docker compose ps
# Should show: db (healthy), backend (Up), nginx (Up)

# 7. Test frontend
open http://localhost
# Should load the React app

# 8. Test API
curl http://localhost/api/health
# Should return: {"status": "healthy"}
```

### Verify Everything Works

```bash
# Check logs
docker compose logs -f backend
docker compose logs -f nginx

# Test database connection
docker compose exec backend python -c "from backend.app import db; print('DB connected!')"

# Test ML models loaded
docker compose exec backend ls -lh /workspaces/deepfake_AI/ml/weights/

# Test data persistence
docker compose exec backend touch /data/test.txt
docker compose restart backend
docker compose exec backend ls /data/test.txt  # Should still exist
```

### Common Issues on Mac

**Issue: `platform linux/amd64` errors**
- Solution: Already handled in docker-compose.yml

**Issue: Bind mount permission denied**
- Solution: Use paths in your home directory (e.g., `~/deepfake-data`)
- macOS Docker Desktop handles permissions automatically for home directory

**Issue: Database volume not found**
- Solution: PostgreSQL uses Docker-managed volume (no host path needed)
- Just ensure deploy/.env has correct POSTGRES credentials

### Clean Up (When Done Testing)

```bash
# Stop services (keeps data)
docker compose down

# Stop and remove volumes (⚠️ DELETES ALL DATA)
docker compose down -v

# Remove images too
docker compose down --rmi all -v
```

---

## Architecture Decisions Explained

### Why Separate deploy/.env from Root .env?

**Problem:** Docker Compose looks for `.env` in the same directory as `docker-compose.yml`. Running `docker compose` from `deploy/` couldn't read the root `.env`.

**Solution:** Create two separate env files:
- **Root `.env`** - For devcontainer/local development (SQLite, localhost paths)
- **`deploy/.env`** - For Docker Compose deployment (PostgreSQL, production paths)

**Benefits:**
- Clean separation of concerns
- No confusion about which config is active
- Mac testing uses different paths than Linux production
- Development workflow unchanged

### Why Docker-Managed Volume for PostgreSQL?

**Considered:** Bind mount like analysis data (configurable host path)

**Chose:** Docker-managed volume (no host path needed)

**Reasoning:**
- Industry standard for databases in Docker
- Deployment team never needs direct filesystem access to DB files
- Backups via `pg_dump` (SQL export), not file copying
- Simpler setup (no `mkdir`, `chown` needed)
- Better performance (no mount overhead)
- Works identically on Mac/Linux/Windows

**Data safety:** Persists across container restarts/recreates. Only deleted with explicit `docker compose down -v`.

### Why platform: linux/amd64?

**Problem:** Mac M1/M2 chips use ARM64 architecture, but dlib library has compatibility issues with ARM64 builds.

**Solution:** Force x86_64 architecture for backend and nginx services.

**Impact:**
- Slower build and runtime on Mac (emulation overhead)
- Production Linux deployment unaffected (native x86_64)
- Alternative: Remove platform flag for production, add back for Mac testing

---

## Handover Checklist

When handing off to deployment team, ensure they have:

- [ ] `deploy/docker-compose.yml` - Full orchestration
- [ ] `deploy/.env.example` - Linux production template
- [ ] `DEPLOYMENT.md` - Step-by-step deployment guide
- [ ] Access to Docker registry (if using pre-built images)
- [ ] Git LFS setup instructions (for pulling ML model weights)

**Optional but recommended:**
- [ ] Pre-built images pushed to registry (skip build step)
- [ ] Sample test video for verification
- [ ] Monitoring/logging setup (not currently implemented)

---

## Questions or Updates Needed?

**The orchestration is complete and ready for production deployment!**

If you need to make changes:
1. Update `deploy/docker-compose.yml`
2. Update `deploy/.env.example` (production template)
3. Test locally following "How to Test Locally (Mac)" above
4. Update `DEPLOYMENT.md` if deployment steps change
5. Commit and push to branch

Good luck with deployment! 🚀
