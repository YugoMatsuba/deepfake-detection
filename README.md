# Deepfake AI Forensics Tool

A comprehensive video forensics platform that combines traditional computer vision techniques with cutting-edge machine learning models for deepfake detection and video authenticity analysis. This project is developed as part of the University of Melbourne IT Project capstone subject.

## 🏗️ Architecture Overview

The system consists of four main components:

1. **🎨 Frontend** - React-based web interface for video upload and analysis visualization
2. **🔧 Backend** - Flask API handling authentication, file management, and analysis orchestration
3. **🔍 Traditional Forensics** - Classical computer vision techniques for tampering detection
4. **🤖 ML Branch** - Deep learning models for advanced deepfake detection *(in development)*

## 📁 Project Structure

```
├── frontend/           # React + Vite + Tailwind UI
├── backend/            # Flask API + SQLite database
├── ml/                 # ML inference pipeline (feature/ml branch)
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
- `FileUploader.jsx` - Multi-format video upload with validation
- `FrameViewer.jsx` - Interactive video frame analysis viewer
- `Analysis.jsx` - Results dashboard with multiple analysis methods
- `Dashboard.jsx` - Main user interface after login

### Routes:
- `/` - Protected dashboard (requires authentication)
- `/login` - User authentication
- `/signup` - New user registration
- `/upload` - Video file upload interface
- `/analysis` - Analysis results and visualization
- `/frame-viewer` - Detailed frame-by-frame inspection

### Development:
```bash
cd frontend
npm install
npm run dev  # Runs on port 5173
```

---

## 🔧 Backend Component

**Technology Stack:** Flask + SQLAlchemy + SQLite (dev) / PostgreSQL (prod)

### Core Features:
- **RESTful API**: Clean API design with proper error handling
- **Session-based Authentication**: Secure user sessions with CSRF protection
- **File Management**: Video upload, storage, and metadata tracking
- **Analysis Orchestration**: Coordinates traditional forensics and ML inference
- **Database Management**: User accounts, analysis history, and audit logs

### API Endpoints:

#### Authentication (`/api/auth`)
- `POST /login` - User authentication
- `POST /logout` - Session termination
- `GET /me` - Current user info

#### Traditional Forensics (`/api/forensics`)
- `POST /extract_frames` - Extract frames from uploaded video
- `POST /ela_analysis` - Error Level Analysis for compression artifacts
- `POST /noise_analysis` - Statistical noise pattern analysis
- `POST /lbp_analysis` - Local Binary Pattern texture analysis
- `POST /cmfd_analysis` - Copy-Move Forgery Detection
- `POST /temporal_analysis` - Temporal consistency analysis

#### Video Management
- `POST /api/upload` - Video file upload and validation
- `GET /api/videos` - List user's uploaded videos

### Configuration:
- **Database**: SQLite (dev) with planned PostgreSQL migration
- **CORS**: Configured for frontend development at localhost:5173
- **Security**: Environment-based secret keys and session configuration
- **File Storage**: Local filesystem with configurable upload directory

### Development:
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python app.py  # Runs on port 5050
```

---

## 🔍 Traditional Forensics Component

**Technology Stack:** OpenCV + PIL + NumPy + scikit-image

### Analysis Methods:

#### 1. **Error Level Analysis (ELA)**
- **Purpose**: Detects JPEG compression inconsistencies
- **Method**: Compares original vs. recompressed images to find editing artifacts
- **Output**: ELA heatmap images + anomaly scores
- **Use Case**: Identifies areas that have been digitally manipulated

#### 2. **Noise Analysis**
- **Purpose**: Analyzes statistical noise patterns across video frames
- **Method**: Computes noise variance, SNR, and pattern consistency
- **Output**: Noise level metrics and temporal consistency scores
- **Use Case**: Detects frame insertion, replacement, or generation artifacts

#### 3. **Local Binary Pattern (LBP) Analysis**
- **Purpose**: Examines texture patterns for manipulation detection
- **Method**: Computes LBP histograms and texture uniformity metrics
- **Output**: Texture consistency scores and pattern analysis
- **Use Case**: Identifies texture inconsistencies from face swapping or generation

#### 4. **Copy-Move Forgery Detection (CMFD)**
- **Purpose**: Detects duplicated or moved regions within frames
- **Method**: SIFT feature matching to find copied areas
- **Output**: Similarity maps highlighting duplicated regions
- **Use Case**: Identifies copy-paste manipulations and object removal

#### 5. **Temporal Analysis**
- **Purpose**: Analyzes frame-to-frame consistency over time
- **Method**: Optical flow, frame differencing, and motion analysis
- **Output**: Temporal consistency metrics and anomaly detection
- **Use Case**: Detects frame insertion, deletion, or temporal manipulations

#### 6. **Frame Extraction**
- **Purpose**: Extracts individual frames from video files
- **Method**: OpenCV-based video processing with metadata preservation
- **Output**: Individual frame images with temporal information
- **Use Case**: Prepares video data for frame-level analysis

### Integration:
All traditional forensics methods are exposed through the Flask API and can be chained together for comprehensive analysis. Results are aggregated and presented through the frontend dashboard.

---

## 🤖 ML Branch Component *(Feature Branch - Not Yet Merged)*

**Technology Stack:** PyTorch + OpenCV + dlib + Docker

The ML branch contains a sophisticated deep learning pipeline for advanced deepfake detection, following **DeepfakeBench** standards for research reproducibility.

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

### CLI Interface:
```bash
# Run inference on video with all models
python ml/runner.py video.mp4 \
  --models xception,spsl,ucf \
  --device cuda \
  --json-out results.json

# Environment-based weight configuration
export XCEPTION_WEIGHTS=/path/to/xception_best.pth
export SPSL_WEIGHTS=/path/to/spsl_best.pth
export UCF_WEIGHTS=/path/to/ucf_best.pth
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

### Development Status:
- ✅ **Current**: Schema validation, runner orchestration, SPSL implementation
- 🚧 **Target for end of sprint**: Full weight loading, UCF dual encoders, production deployment

### Docker Environment:
```dockerfile
FROM nvidia/cuda:11.3.1-cudnn8-runtime-ubuntu20.04
# PyTorch 1.12.1+cu113, OpenCV headless, dlib 19.24.0
# Mount points: /ml/weights, /ml/dlib, /ml/data
```

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

4. **ML Development** *(feature/ml branch)*:
```bash
git checkout feature/ml
cd ml
# See ml/plan for detailed setup instructions
pytest tests/ -v  # Run test suite
```

### Default Credentials:
- **Username**: `admin`
- **Password**: `testpass123`

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

### Docker Compose (Recommended):
```yaml
version: '3.8'
services:
  frontend:
    build: ./frontend
    ports: ["80:80"]

  backend:
    build: ./backend
    environment:
      - DATABASE_URL=postgresql://...
      - ENVIRONMENT=production

  ml-inference:
    build: ./ml
    runtime: nvidia
    volumes:
      - ./weights:/ml/weights
      - ./dlib:/ml/dlib
```

### Infrastructure Requirements:
- **CPU**: 4+ cores for API handling
- **RAM**: 8GB+ (16GB+ recommended for ML)
- **GPU**: NVIDIA GPU with CUDA 11.3+ support (ML inference)
- **Storage**: SSD recommended for video processing



## 📚 Research & Citations

This project implements methods from:
- **DeepfakeBench**: A Comprehensive Benchmark of Deepfake Detection (NeurIPS 2023)
- **Xception**: Deep Learning with Depthwise Separable Convolutions
- **SPSL**: Spatial-Phase Shallow Learning for real-time deepfake detection
- **UCF**: Uncovering Common Features in deepfake videos

---

*Built with ❤️ for video forensics and authenticity verification*
