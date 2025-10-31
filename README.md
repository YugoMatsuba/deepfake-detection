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

### Development:
```bash
cd frontend
npm install
npm run dev  # Runs on port 5173
```

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
- **CORS**: Configured for frontend development at localhost:5173
- **Security**: Environment-based secret keys and session configuration
- **File Storage**: Volume-mounted persistent storage at `/data` (production)

### Development:
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python app.py  # Runs on port 5050
```

---

## 🧱 Deepfake AI Backend Setup Guide

Follow these steps if you want to run the Flask API against PostgreSQL locally or inside the dev container.

### 1️⃣ Start the PostgreSQL Database
```bash
docker run --name deepfake-db \
  -p 5431:5432 \
  -e POSTGRES_USER=deepfake \
  -e POSTGRES_PASSWORD=secret \
  -e POSTGRES_DB=deepfake_dev \
  -d postgres:16
```

### 2️⃣ Open the Dev Container
In VS Code, open the project and reopen it in the provided container  
`⇧⌘P → Dev Containers: Reopen in Container`

### 3️⃣ Install Dependencies
Inside the dev container shell:
```bash
pip install -r requirements.txt
```

### 4️⃣ Set Environment Variables
```bash
cd backend
export DATABASE_URL="postgresql+psycopg://deepfake:secret@host.docker.internal:5431/deepfake_dev"
export TEST_DATABASE_URL="postgresql+psycopg://deepfake:secret@host.docker.internal:5431"
```

### 5️⃣ Apply Database Migrations
```bash
alembic upgrade head
```

### 6️⃣ Start the Flask Server
```bash
python app.py
```

The API will be available at http://localhost:5050 and connected to PostgreSQL.

### 🚀 Production: Run with Gunicorn

For production or containerized runs, use Gunicorn with the provided WSGI entrypoint and config:

```bash
# From repo root
pip install -r requirements.txt  # ensures gunicorn is installed
gunicorn --config backend/gunicorn.conf.py --chdir backend wsgi:app
```

Notes:
- Configure port via `PORT` env var (defaults to 5050)
- Set worker/threads via `WEB_CONCURRENCY` and `GUNICORN_THREADS`
- Gunicorn is Linux/macOS oriented; use Docker/WSL on Windows

### 🧭 Optional: pgAdmin Setup

1. Install pgAdmin 4 from https://www.pgadmin.org/download/  
2. In pgAdmin, create a new server with:
   - **Name**: `it-project`  
   - **Host**: `localhost`  
   - **Port**: `5431`  
   - **Username**: `deepfake`  
   - **Password**: `secret`
3. Expand `Servers → localhost → Databases → deepfake_dev` to inspect tables and run queries.

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

### Quick Start (Dev Container)

The ML module runs in a containerized environment for dependency isolation and GPU support.

**1. Open in VS Code Dev Container:**
   - Open project in VS Code
   - Command palette: "Dev Containers: Reopen in Container"
   - Container builds from `ml/Dockerfile` (CUDA 11.3 + PyTorch 1.12.1)
   - **Git LFS automatically pulls weights** in dev container

**2. Run Inference:**
```bash
cd /workspaces/deepfake_AI/ml

# Analyze a video with all three models
python runner.py data/your_video.mp4 \
  --models xception,spsl,ucf \
  --json-out results.json

# Or use default weights (auto-detected from ml/weights/)
python runner.py data/your_video.mp4
```

### CLI Options:
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

### Testing:

Run tests inside the dev container:
```bash
cd /workspaces/deepfake_AI
pytest tests/test_checkpoint_loader_pr4.py -v
pytest tests/test_pr5.py -v
pytest tests/ -v  # Run all ML tests
```

Tests validate architecture compatibility without requiring weight files.

---

## 🚀 Quick Start

### Prerequisites:
- **Node.js 18+** (frontend)
- **Python 3.9+** (backend & ML)
- **Docker** (ML inference, optional)
- **CUDA 11.3+** (ML GPU acceleration, optional)

### Development Setup:

1. **Clone Repository**:
```bash
git clone <repository-url>
cd deepfake_AI
```

2. **Backend Setup**:
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python app.py  # Runs on port 5050
```

3. **Frontend Setup**:
```bash
cd frontend
npm install
npm run dev  # Runs on port 5173
```

4. **ML Inference** (Dev Container):
```bash
# Open in VS Code, then reopen in dev container
cd /workspaces/deepfake_AI/ml
python runner.py data/sample.mp4  # Run inference
pytest tests/ -v  # Run test suite
```

### Owner Bootstrap:
The system uses environment variable-based owner account creation instead of hardcoded credentials.

**First-time setup:**
```bash
# Set owner credentials via environment variables
export OWNER_USERNAME=admin
export OWNER_SEED_PASSWORD=your_secure_password

# Run backend - owner account will be created automatically
cd backend
python app.py
```

**Environment Variables:**
- `OWNER_USERNAME` - Username for the owner account
- `OWNER_SEED_PASSWORD` - Password for owner (only needed on first boot or password reset)
- `ALLOW_OWNER_TRANSFER` - Set to "1" to allow changing owner (default "0" for security)

---

## 🔐 Environment Configuration

Create `.env` files for configuration:

### Backend `.env`:
```bash
SECRET_KEY=your-production-secret-key
DATABASE_URL=postgresql://user:pass@localhost/deepfake_db
ENVIRONMENT=production
CORS_ORIGINS=https://your-frontend-domain.com
```

### ML `.env`:
```bash
ML_WEIGHTS_DIR=/path/to/model/weights
ML_DLIB_DIR=/path/to/dlib/models
ML_DATA_DIR=/path/to/input/videos
XCEPTION_WEIGHTS=/weights/xception_best.pth
SPSL_WEIGHTS=/weights/spsl_best.pth
UCF_WEIGHTS=/weights/ucf_best.pth
```

---

## 🧪 Testing

### ML Tests *(feature/ml branch)*:
```bash
cd ml
pytest tests/ -v
# Tests run without .pth weights (architecture validation only)
```

---

## 🏭 Production Deployment

### Prerequisites

**⚠️ IMPORTANT: Create host directories before first deployment:**

```bash
# On your Linux VM, create persistent data directory
sudo mkdir -p /var/lib/deepfake/data
sudo chown -R 1000:1000 /var/lib/deepfake/data

# This directory will store:
# - Uploaded videos
# - Extracted frames
# - Forensic analysis overlays (ELA, Noise, LBP)
```

**Why this matters:** Without a mounted volume, all analysis data is lost when the container restarts. The host directory at `/var/lib/deepfake/data` persists data independently of the container lifecycle.

### Environment Configuration

Configure deployment via `.env` file:

```bash
# PostgreSQL connection (required - SQLite not supported in production)
DATABASE_URL=postgresql+psycopg://deepfake_user:password@postgres:5432/deepfake_db

# Host directory for persistent data (must exist before deployment)
DATA_VOLUME_PATH=/var/lib/deepfake/data

# Application config
ENVIRONMENT=production
SECRET_KEY=your-production-secret-key-here
FORENSICS_WORKERS=6  # CPU cores - 2 (leave headroom for Gunicorn)
```

### Docker Compose Example

See `docker-compose.volumes.yml` for the minimal volume configuration. Your deployment orchestrator should merge this into the full stack:

```yaml
version: '3.8'

services:
  backend:
    image: deepfake:latest
    volumes:
      # Persistent storage for analysis data
      - analyses-data:/data
    environment:
      - DATABASE_URL=postgresql+psycopg://user:pass@postgres:5432/deepfake_db
      - DATA_DIR=/data
      - ENVIRONMENT=production
    # Add: ports, depends_on (postgres), networks, restart policy

  postgres:
    image: postgres:16
    volumes:
      - postgres-data:/var/lib/postgresql/data
    environment:
      - POSTGRES_USER=deepfake_user
      - POSTGRES_PASSWORD=secure_password
      - POSTGRES_DB=deepfake_db

volumes:
  # Analysis data: videos, frames, forensic overlays
  analyses-data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: ${DATA_VOLUME_PATH:-/var/lib/deepfake/data}

  # PostgreSQL database
  postgres-data:
    driver: local
```

**Key Points:**
- ✅ Named volumes persist data across container restarts
- ✅ PostgreSQL required (SQLite not supported in production)
- ✅ Host path `/var/lib/deepfake/data` must exist before `docker compose up`
- ✅ Configure `DATA_VOLUME_PATH` in `.env` to override default location

### Infrastructure Requirements:
- **CPU**: 4+ cores for API handling
- **RAM**: 8GB+ (16GB+ recommended for ML)
- **GPU**: NVIDIA GPU with CUDA 11.3+ support (ML inference)
- **Storage**: SSD recommended for video processing; plan for analysis data growth



## 📚 Research & Citations

This project implements methods from:
- **DeepfakeBench**: A Comprehensive Benchmark of Deepfake Detection (NeurIPS 2023)
- **Xception**: Deep Learning with Depthwise Separable Convolutions
- **SPSL**: Spatial-Phase Shallow Learning for real-time deepfake detection
- **UCF**: Uncovering Common Features in deepfake videos

---

*Built with ❤️ for video forensics and authenticity verification*
