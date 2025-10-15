# syntax=docker/dockerfile:1.4
#
# Unified Dockerfile for Deepfake Detection ML + Backend API
# Supports both CPU (default, for dev laptops) and CUDA (optional, for GPU deployment)
#
# Build args:
#   DEVICE=cpu (default) | cuda
#   PYTHON_VERSION=3.9
#   CUDA_IMAGE_TAG=11.3.1-cudnn8-runtime-ubuntu20.04
#   TORCH_VER=1.12.1
#   TV_VER=0.13.1
#
# Usage:
#   CPU build (devcontainer default):
#     docker build --build-arg DEVICE=cpu -t deepfake:cpu .
#
#   CUDA build (GPU deployment):
#     docker build --build-arg DEVICE=cuda -t deepfake:cuda .
#

# ----- Build-time arguments -----
ARG DEVICE=cpu
ARG PYTHON_VERSION=3.9
ARG CUDA_IMAGE_TAG=11.3.1-cudnn8-runtime-ubuntu20.04
ARG TORCH_VER=1.12.1
ARG TV_VER=0.13.1

############################
# CPU base (for dev laptops)
############################
FROM python:${PYTHON_VERSION}-slim-bullseye AS base-cpu

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    git-lfs \
    build-essential \
    cmake \
    pkg-config \
    libgl1 \
    libglib2.0-0 \
    libjpeg62-turbo-dev \
    ca-certificates \
    ffmpeg \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /workspaces/deepfake_AI

# Upgrade pip
RUN python -m pip install --upgrade pip==22.3.1

# Install PyTorch CPU wheels
ARG TORCH_VER
ARG TV_VER
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install \
    torch==${TORCH_VER} \
    torchvision==${TV_VER}

# Copy requirements and install remaining dependencies
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install -r requirements.txt

# Create ML directories
RUN mkdir -p /ml/weights /ml/dlib /ml/data

# Default command
CMD ["/bin/bash"]

############################
# CUDA base (for GPU servers)
############################
FROM nvidia/cuda:${CUDA_IMAGE_TAG} AS base-cuda

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1

# Install system dependencies including Python 3.9
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    git-lfs \
    build-essential \
    cmake \
    pkg-config \
    libgl1 \
    libglib2.0-0 \
    libjpeg62-turbo-dev \
    ca-certificates \
    ffmpeg \
    python3.9 \
    python3.9-distutils \
    python3.9-dev \
    python3-pip \
  && rm -rf /var/lib/apt/lists/*

# Set python3.9 as default python
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.9 1

WORKDIR /workspaces/deepfake_AI

# Upgrade pip
RUN python -m pip install --upgrade pip==22.3.1

# Install PyTorch CUDA 11.3 wheels
ARG TORCH_VER
ARG TV_VER
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install \
    --extra-index-url https://download.pytorch.org/whl/cu113 \
    torch==${TORCH_VER}+cu113 \
    torchvision==${TV_VER}+cu113

# Copy requirements and install remaining dependencies
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install -r requirements.txt

# Create ML directories
RUN mkdir -p /ml/weights /ml/dlib /ml/data

# Default command
CMD ["/bin/bash"]

############################
# Select final stage based on DEVICE arg
############################
ARG DEVICE=cpu
FROM base-${DEVICE} AS runtime

# Default paths for ML assets (works for both bind mount and COPY deployments)
ENV ML_WEIGHTS_DIR=/workspaces/deepfake_AI/ml/weights \
    XCEPTION_WEIGHTS=/workspaces/deepfake_AI/ml/weights/xception_best.pth \
    SPSL_WEIGHTS=/workspaces/deepfake_AI/ml/weights/spsl_best.pth \
    UCF_WEIGHTS=/workspaces/deepfake_AI/ml/weights/ucf_best.pth

# Expose Flask port
EXPOSE 5050

# The VS Code devcontainer will bind-mount the repo into /workspaces/deepfake_AI
# For standalone deployment, you would COPY the application code here:
# COPY . /workspaces/deepfake_AI

# Default command (override as needed for ML runner or Flask app)
CMD ["/bin/bash"]
