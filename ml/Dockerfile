FROM --platform=linux/amd64 nvidia/cuda:11.3.1-cudnn8-runtime-ubuntu20.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1

# System dependencies kept minimal
RUN apt-get update && apt-get install -y --no-install-recommends \
    git git-lfs build-essential cmake libgl1 libglib2.0-0 ca-certificates \
    python3.9 python3.9-distutils python3.9-dev python3-pip && \
    rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.9 1

WORKDIR /workspaces/deepfake_AI

# Torch stack with CUDA 11.3 builds
RUN --mount=type=cache,target=/root/.cache/pip \
    python3.9 -m pip install --upgrade pip==22.3.1 && \
    python3.9 -m pip install \
    --extra-index-url https://download.pytorch.org/whl/cu113 \
    torch==1.12.1+cu113 \
    torchvision==0.13.1+cu113

# Remaining runtime dependencies
RUN --mount=type=cache,target=/root/.cache/pip \
    python3.9 -m pip install \
    numpy==1.21.6 \
    pillow==9.5.0 \
    opencv-python-headless==4.6.0.66 \
    dlib==19.24.0 \
    imutils==0.5.4 \
    imageio==2.9.0 \
    scikit-image==0.19.2 \
    tqdm==4.64.1 \
    pydantic==1.10.15

RUN mkdir -p /ml/weights /ml/dlib /ml/data

CMD ["/bin/bash"]
