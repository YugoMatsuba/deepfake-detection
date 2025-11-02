# Deepfake AI Forensics Tool

A comprehensive video forensics platform that combines traditional computer vision techniques with cutting-edge machine learning models for deepfake detection and video authenticity analysis. This project is developed as part of the University of Melbourne IT Project capstone subject.

## 🏗️ Architecture Overview

The system consists of four main components:

1. **🎨 Frontend** - React-based web interface for video upload and analysis visualization
2. **🔧 Backend** - Flask API handling authentication, file management, and analysis orchestration
3. **🔍 Traditional Forensics** - Classical computer vision techniques for tampering detection
4. **🤖 ML Detection** - Deep learning models (Xception, SPSL, UCF) for advanced deepfake detection

## 📁 Project Structure

```
├── frontend/           # React + Vite + Tailwind UI
├── backend/            # Flask API + PostgreSQL database
├── ml/                 # ML inference pipeline (PyTorch + CUDA)
└── tests/              # Test suites for all components
```

---

## 🎨 Frontend Component

**Technology Stack:** React + Vite + Tailwind CSS + shadcn/ui

### Core Features:
- **Authentication System**: Secure login/signup with session management
- **Video Upload Interface**: Drag-and-drop file uploader with progress tracking
- **Analysis Dashboard**: Real-time visualization of forensic analysis results
- **Frame Viewer**: Interactive frame-by-frame analysis with anomaly highlighting
- **Responsive Design**: Mobile-friendly interface using Tailwind CSS

### Key Components:
- `App.jsx` - Main application routing and layout
- `AuthProvider.jsx` - Authentication context and state management
- `AnalysisProvider.jsx` - Analysis state management and context
- `FileUploader.jsx` - Multi-format video upload with validation
- `FrameViewer.jsx` - Interactive video frame analysis viewer with timeline markers
- `FrameViewerRetrieval.jsx` - Frame viewer data fetching wrapper
- `Analysis.jsx` - Analysis results dashboard with ML scores
- `Landing.jsx` - Main user landing page after login
- `AdminDashboard.jsx` - Admin user management interface
- `PastReports.jsx` - Historical analysis reports browser
- `MetadataResults.jsx` - Metadata forensics results display

### Routes:
- `/` - Landing page (requires authentication)
- `/login` - User authentication
- `/signup` - New user registration
- `/upload` - Video file upload interface
- `/analysis` - Analysis results and ML scores visualization
- `/frame-viewer` - Detailed frame-by-frame inspection with forensics overlays
- `/reports` - Past analysis reports (requires authentication)
- `/admin` - Admin dashboard (requires admin/owner role)
- `/role-select` - User role management (requires admin/owner role)

---

## 🔧 Backend Component

**Technology Stack:** Flask + SQLAlchemy + PostgreSQL

### Core Features:
- **RESTful API**: Clean API design with proper error handling
- **Session-based Authentication**: Secure user sessions with CSRF protection
- **File Management**: Video upload, storage, and metadata tracking
- **Analysis Orchestration**: Coordinates traditional forensics and ML inference
- **Database Management**: User accounts, analysis history, and audit logs

### API Endpoints:

#### Authentication (`/api/auth`)
- `POST /login` - User authentication
- `POST /signup` - User registration
- `POST /logout` - Session termination
- `GET /me` - Current user info

#### Video Upload (`/api/videos`)
- `POST /videos` - Upload video and create analysis record

#### Analysis (`/api/analyses`)
- `POST /analyses/<id>/start` - Run full analysis (ML + traditional + metadata)
- `GET /analyses/<id>` - Get analysis status and results
- `POST /analyses/<id>/frames/<frame>/forensics` - On-demand traditional forensics for single frame (ELA, noise, LBP)
- `POST /analyses/<id>/frames/<frame>/ml` - On-demand ML analysis for single frame
- `DELETE /analyses/<id>` - Delete analysis and associated files

#### Reports (`/api/reports`)
- `GET /reports/<id>/pdf` - Generate PDF forensics report

#### Admin (`/api/admin`)
- `GET /admin/users` - List all users (admin/owner only)
- `POST /admin/users/<id>/approve` - Approve pending user (admin/owner only)
- `POST /admin/users/<id>/role` - Change user role (owner only)

### Configuration:
- **Database**: PostgreSQL (required for all environments)
- **CORS**: Configured via `CORS_ORIGINS` environment variable
- **Security**: Environment-based secret keys and session configuration
- **File Storage**: Volume-mounted persistent storage at `/data`

---

## 🔍 Traditional Forensics Component

**Technology Stack:** OpenCV + PIL + NumPy + scikit-image

### Analysis Methods:

#### 1. **Error Level Analysis (ELA)**
- **Purpose**: Detects JPEG compression inconsistencies
- **Method**: Compares original vs. recompressed images to find editing artifacts
- **Output**: ELA heatmap overlay + anomaly scores per frame
- **Use Case**: Identifies areas that have been digitally manipulated
- **Location**: `backend/api/traditional_forensics_utils/ela_analysis.py`

#### 2. **Noise Analysis**
- **Purpose**: Analyzes statistical noise patterns across video frames
- **Method**: Computes noise variance, SNR, and pattern consistency
- **Output**: Noise level metrics and temporal consistency scores
- **Use Case**: Detects frame insertion, replacement, or generation artifacts
- **Location**: `backend/api/traditional_forensics_utils/noise_analysis.py`

#### 3. **Local Binary Pattern (LBP) Analysis**
- **Purpose**: Examines texture patterns for manipulation detection
- **Method**: Computes LBP histograms and texture uniformity metrics
- **Output**: Texture consistency scores and pattern analysis
- **Use Case**: Identifies texture inconsistencies from face swapping or generation
- **Location**: `backend/api/traditional_forensics_utils/lbp_analysis.py`

#### 4. **Metadata Forensics Analysis**
- **Purpose**: Validates video file metadata and structural integrity
- **Method**: ExifTool extraction, FFmpeg integrity checks, frame hash generation
- **Techniques**:
  - EXIF/metadata extraction and validation
  - Missing metadata detection (device info, timestamps)
  - Timestamp consistency analysis
  - Editing software detection
  - GPS coordinate validation
  - Container structural integrity (FFmpeg error detection)
  - Per-frame MD5 hash generation
  - Duplicate frame detection
  - Whole-file SHA-256 hash for chain of custody
- **Output**: Metadata anomalies, integrity status, frame hashes, duplicates
- **Use Case**: Detects metadata tampering, file corruption, and basic forgery indicators
- **Location**: `backend/api/metadata_utils/metadata_analysis.py`

### Integration:
Traditional forensics and metadata analysis run automatically during full analysis (`POST /analyses/<id>/start`). Individual methods can also be invoked on-demand for specific frames via the frame analysis endpoints. Results are stored in the database and presented through the frontend dashboard.

---

## 🤖 ML Deepfake Detection Component

**Technology Stack:** PyTorch 1.12.1 + CUDA 11.3 + OpenCV + dlib + Docker

The ML module provides a production-ready deep learning pipeline for advanced deepfake detection, following **DeepfakeBench** standards for research reproducibility.

### Architecture:
- **DeepfakeBench Alignment**: Exact preprocessing and model architectures from the academic benchmark
- **Three Model Ensemble**: Xception, SPSL, and UCF detectors for comprehensive analysis
- **Docker-based Deployment**: CUDA-enabled containers for GPU acceleration
- **Structured Output**: JSON schema with validation and provenance tracking

### Model Components:

#### 1. **Xception Model** (`ml/models/xception_infer.py`)
- **Architecture**: DeepfakeBench-aligned Xception CNN
- **Input**: RGB face crops (256×256 pixels)
- **Output**: Per-frame deepfake probabilities
- **Specialty**: Spatial artifact detection in generated faces

#### 2. **SPSL Model** (`ml/models/spsl_infer.py`)
- **Architecture**: Spatial-Phase Shallow Learning with 4-channel input
- **Input**: RGB + FFT phase channel (256×256 pixels)
- **Output**: Enhanced deepfake detection with frequency domain analysis
- **Specialty**: Frequency artifact detection in generated content

#### 3. **UCF Model** (`ml/models/ucf_infer.py`)
- **Architecture**: Uncovering Common Features with dual encoders
- **Input**: RGB frames with shared feature extraction
- **Output**: Common manipulation pattern detection
- **Specialty**: Cross-dataset generalization and shared forgery features

### Pipeline Components:

#### Video Processing (`ml/video_io.py`)
- **Frame Sampling**: Uniform 32-frame sampling via `np.linspace`
- **Face Detection**: dlib 81-point landmark detection
- **Face Alignment**: 5-point similarity transform with scale=1.3
- **Padding Strategy**: Repeat last valid crop for videos <32 frames

#### Preprocessing (`ml/transforms.py`)
- **Normalization**: DeepfakeBench standard (mean=0.5, std=0.5)
- **Tensor Conversion**: RGB uint8 → float32 normalized tensors
- **Batch Processing**: Efficient GPU memory management

#### Schema Validation (`ml/schema.py`)
- **TypedDict Contracts**: Structured output with validation
- **Version Control**: Schema versioning for API compatibility
- **Error Handling**: Graceful failure with structured error envelopes
- **Provenance Tracking**: Weight file hashing and timing metadata

### ⚠️ Important: Git LFS Required

This module uses **Git LFS** for storing large model weights (~382MB total).

**First-time setup (one-time):**
```bash
# Install Git LFS
brew install git-lfs        # macOS
# OR: apt-get install git-lfs  # Linux
# OR: https://git-lfs.github.com/  # Windows

# Enable LFS
git lfs install

# Download weight files
git lfs pull
```

**Verify weights downloaded:**
```bash
ls -lh ml/weights/ucf_best.pth
# Should show ~179MB, not 133 bytes
```

If you see small file sizes (~100 bytes), you have LFS pointer files instead of actual weights. Run `git lfs pull`.

### Integration with Backend

The ML module is **integrated into the backend API** and runs automatically during video analysis. You don't need to run the ML module separately - it's invoked by the backend when you upload a video and start analysis via the web interface.

**How it works:**
1. User uploads video via frontend
2. Backend calls ML inference via `ml/runner.py`
3. ML module processes video: face detection → alignment → model inference
4. Results returned to backend and stored in database
5. Frontend displays results with per-frame scores

**Direct CLI usage (optional, for testing):**

If you want to test ML inference directly (without the full backend):

```bash
# Run inside backend container
docker compose exec backend bash

# Run ML inference on a video
cd /workspaces/deepfake_AI/ml
python runner.py data/sample_video.mp4 --models xception,spsl,ucf --json-out results.json
```

**CLI Options:**
- `video` (positional): Path to input video
- `--models`: Comma-separated list (default: all three)
- `--json-out`: Output JSON path (default: stdout)
- `--device`: `cuda` or `cpu` (auto-detects GPU)
- `--xception-weights`, `--spsl-weights`, `--ucf-weights`: Override weight paths
- `--no-hash`: Skip SHA-256 hashing of weights

### Directory Structure:
```
ml/
├── weights/                     # Pretrained model checkpoints (committed)
│   ├── xception_best.pth       # 84MB - Xception detector
│   ├── spsl_best.pth           # 84MB - SPSL detector
│   └── ucf_best.pth            # 179MB - UCF detector
├── dlib/                        # Face detection models (committed)
│   └── shape_predictor_81_face_landmarks.dat  # 19MB
├── data/                        # Input videos / output JSON (gitignored)
├── models/                      # Model architectures & inference adapters
├── runner.py                    # Main inference orchestrator
├── video_io.py                  # Video decode + face alignment
├── transforms.py                # Preprocessing (normalize, SPSL phase)
└── schema.py                    # JSON output schema
```

### Input/Output:

**Input:**
- Place videos in `ml/data/` or specify any path
- Supported formats: `.mp4`, `.avi`, `.mov`, `.mkv`

**Output:**
Structured JSON with per-model scores and per-frame probabilities (schema v1.0.0)

### Environment Variables (Optional):
```bash
export XCEPTION_WEIGHTS=/custom/path/xception.pth
export SPSL_WEIGHTS=/custom/path/spsl.pth
export UCF_WEIGHTS=/custom/path/ucf.pth
```

### Output Format:
```json
{
  "schema_version": "1.0.0",
  "video": {
    "path": "input.mp4",
    "fps": 30.0,
    "frame_count": 900,
    "duration_sec": 30.0
  },
  "frames": [
    {"index": 0, "time": 0.0},
    {"index": 29, "time": 0.97}
  ],
  "models": [
    {
      "name": "Xception",
      "score": 0.847,
      "frames": [
        {"index": 0, "time": 0.0, "score": 0.834},
        {"index": 29, "time": 0.97, "score": 0.861}
      ],
      "weights_hash": "sha256:3a1e5f..."
    }
  ],
  "timing_ms": {
    "decode_align": 1250.0,
    "normalize": 45.2,
    "load_models": 890.1,
    "inference_total": 2340.8
  },
  "error": null
}
```

### ML Module Testing:

ML tests validate model architectures without requiring weight files:

```bash
# Run ML architecture tests
docker compose run --rm backend bash -c "pytest tests/test_checkpoint_loader_pr4.py -v"
docker compose run --rm backend bash -c "pytest tests/test_pr5.py -v"
```

These tests ensure DeepfakeBench model architectures are correctly implemented for weight loading.

---

## 🚀 Quick Start (Local Development)

### Prerequisites:
- **Docker** and **Docker Compose** v2.0+
- **Git** with **Git LFS** installed (`git lfs install`)
- 8GB+ RAM recommended

### Setup Steps:

#### 1. Clone Repository and Pull ML Weights
```bash
git clone <repository-url>
cd deepfake_AI

# Pull ML model weights via Git LFS (required - ~382MB total)
git lfs pull
```

#### 2. Configure Environment
```bash
# Copy local development environment template
cp .env.local.example .env

# The default values in .env.local.example work out of the box for local development
# Key settings:
# - PostgreSQL database via Docker (port 5431)
# - Backend on port 5050
# - CORS enabled for localhost
# - Owner account: admin / changeme123
```

#### 3. Start All Services
```bash
# Start backend, frontend, PostgreSQL, and nginx with docker-compose
docker compose up -d

# Wait for services to be ready (watch logs)
docker compose logs -f
```

#### 4. Initialize Database
```bash
# Run database migrations to create tables
docker compose run --rm backend bash -c "cd backend && alembic upgrade head"
```

#### 5. Access the Application
```
Frontend: http://localhost (served via nginx)
Backend API: http://localhost/api

Default login:
- Username: admin
- Password: changeme123
```

### Common Commands:

```bash
# View logs
docker compose logs -f backend
docker compose logs -f nginx

# Restart a service
docker compose restart backend

# Stop all services
docker compose down

# Rebuild after code changes
docker compose build backend
docker compose up -d

# Run backend tests
docker compose run --rm backend bash -c "cd backend && pytest tests/ -v"
```

### Development Workflow:

**For Frontend changes:**
- Frontend runs in development mode with hot reload
- Edit files in `frontend/src/` and changes appear immediately
- No rebuild needed

**For Backend changes:**
- Backend uses volume mount for live code reload (via Gunicorn --reload)
- Edit files in `backend/` and Gunicorn will auto-reload
- For dependency changes: `docker compose build backend && docker compose restart backend`

**For ML changes:**
- ML code is volume-mounted read-only
- Changes to `ml/` require backend restart: `docker compose restart backend`

---

## 🔐 Environment Configuration

The application uses a `.env` file in the root directory for all configuration.

### Local Development
```bash
# Copy the local development template
cp .env.local.example .env
```

**Default configuration (works out of the box):**
- PostgreSQL via Docker Compose (localhost:5431)
- Backend API on port 5050
- Frontend dev server on port 5173 (served via nginx on port 80)
- Owner account: admin / changeme123
- CORS enabled for localhost

### Production Deployment
```bash
# Copy the production template
cp .env.production.example .env

# Generate secrets and edit:
# - SECRET_KEY (generate: python3 -c "import secrets; print(secrets.token_hex(32))")
# - POSTGRES_PASSWORD (generate: openssl rand -base64 32)
# - OWNER_SEED_PASSWORD (for initial admin account)
# - CORS_ORIGINS (match your deployment URL)
# - DATA_VOLUME_PATH=/var/lib/deepfake/data (Linux host path for analysis data)
```

**See [DEPLOYMENT.md](DEPLOYMENT.md) for complete production deployment guide.**

### Key Environment Variables

| Variable | Description | Local Default | Production |
|----------|-------------|---------------|------------|
| `ENVIRONMENT` | Runtime mode | `development` | `production` |
| `DATABASE_URL` | PostgreSQL connection | `postgresql+psycopg://deepfake:secret@db:5432/deepfake_dev` | Set in .env |
| `SECRET_KEY` | Flask session signing | `dev-insecure` | **Must generate** |
| `CORS_ORIGINS` | Allowed origins | `http://localhost:5173,http://localhost` | Your domain |
| `DEVICE` | ML inference device | `cpu` | `cpu` or `cuda` |
| `FORENSICS_WORKERS` | CPU cores for analysis | `4` | CPU cores - 2 |
| `OWNER_USERNAME` | Initial admin username | `admin` | Your choice |
| `OWNER_SEED_PASSWORD` | Initial admin password | `changeme123` | **Must generate** |

**Important:** PostgreSQL is required for all environments. SQLite is not supported.

### Database Initialization

The system uses Alembic migrations to create and update database tables. After copying your `.env` file, you must run migrations:

```bash
docker compose run --rm backend bash -c "cd backend && alembic upgrade head"
```

**Note:** Keep `DB_BOOTSTRAP=0` in your `.env` file. Setting it to 1 bypasses migration history and is not recommended for any environment.

---

## 🧪 Testing

### Backend Tests
```bash
# Run all backend tests
docker compose run --rm backend bash -c "cd backend && pytest tests/ -v"

# Run specific test file
docker compose run --rm backend bash -c "cd backend && pytest tests/test_auth.py -v"

# Run with coverage
docker compose run --rm backend bash -c "cd backend && pytest tests/ --cov=api --cov-report=term-missing"
```

### Frontend Tests
```bash
# Run frontend tests
docker compose run --rm nginx npm --prefix /usr/share/nginx/html test

# Run integration tests
cd frontend
npm run test:integration
```

### ML Tests
```bash
# Tests validate architecture without requiring weight files
docker compose run --rm backend bash -c "pytest tests/test_xception_pr1.py -v"
docker compose run --rm backend bash -c "pytest tests/ -k 'ml' -v"
```

---

## 🏭 Production Deployment

**For complete production deployment instructions, see [DEPLOYMENT.md](DEPLOYMENT.md).**

The deployment guide covers:
- ✅ Step-by-step production setup on Linux VM
- ✅ Environment configuration and secret generation
- ✅ Docker Compose orchestration (backend + frontend + PostgreSQL + nginx)
- ✅ Database migrations and initialization
- ✅ Persistent volume setup for analysis data
- ✅ SSL/TLS configuration with Let's Encrypt
- ✅ CUDA/GPU setup for ML acceleration
- ✅ Troubleshooting and operational procedures
- ✅ Backup and restore procedures

### Quick Production Overview

**Prerequisites:**
- Linux VM with Docker and Docker Compose installed
- 8GB+ RAM (16GB+ recommended)
- 50GB+ disk space
- NVIDIA GPU with CUDA 11.3+ (optional, for ML acceleration)

**Deployment Steps:**
```bash
# 1. Clone repository
git clone <repo-url>
cd deepfake_AI
git lfs pull

# 2. Create persistent data directory
sudo mkdir -p /var/lib/deepfake/data
sudo chown -R 1000:1000 /var/lib/deepfake/data

# 3. Configure environment
cp .env.production.example .env
# Edit .env and set all required values (see DEPLOYMENT.md)

# 4. Build and start services
docker compose build
docker compose up -d

# 5. Run migrations
docker compose run --rm backend bash -c "cd backend && alembic upgrade head"

# 6. Verify deployment
curl http://localhost/api/auth/me
# Should return: {"authenticated": false}
```

**Access:** Application runs on port 80 (HTTP). For production, configure HTTPS via reverse proxy (Cloudflare, nginx, etc.) - see DEPLOYMENT.md for details.



## 📚 Research & Citations

This project implements methods from:
- **DeepfakeBench**: A Comprehensive Benchmark of Deepfake Detection (NeurIPS 2023)
- **Xception**: Deep Learning with Depthwise Separable Convolutions
- **SPSL**: Spatial-Phase Shallow Learning for real-time deepfake detection
- **UCF**: Uncovering Common Features in deepfake videos

---

*Built with ❤️ for video forensics and authenticity verification*
