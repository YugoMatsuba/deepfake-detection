"""
Video storage and metadata extraction utilities.

Handles deterministic per-analysis video storage and metadata probing
via ffprobe (primary) with OpenCV fallback.
"""

from __future__ import annotations
import hashlib
import os
import shutil
import subprocess
import json
import logging
from pathlib import Path
from typing import Optional

import cv2

logger = logging.getLogger(__name__)

# Data root for all analysis artifacts
DATA_ROOT = Path(os.getenv("DATA_DIR", "/data")) / "analyses"


def save_video_for_analysis(tmp_path: Path, ext: str, analysis_id: str) -> tuple[Path, str]:
    """
    Save uploaded video to per-analysis directory and compute SHA-256.

    Args:
        tmp_path: Temporary upload path
        ext: File extension (e.g., ".mp4", ".mov")
        analysis_id: UUID of the analysis

    Returns:
        (absolute_path, sha256_hex)

    Storage structure:
        /data/analyses/{analysis_id}/video{ext}
    """
    # Create analysis directory
    out_dir = DATA_ROOT / analysis_id
    out_dir.mkdir(parents=True, exist_ok=True)

    # Destination path
    out = out_dir / f"video{ext.lower()}"

    # Move file from temp location
    shutil.move(str(tmp_path), str(out))

    # Compute SHA-256 of video bytes (streaming to avoid loading entire file in memory)
    hasher = hashlib.sha256()
    with out.open('rb') as f:
        while chunk := f.read(65536):  # 64KB chunks
            hasher.update(chunk)
    sha = hasher.hexdigest()

    return out, sha


def probe_video_metadata(path: Path) -> dict:
    """
    Extract video metadata using ffprobe (primary) with OpenCV fallback.

    Args:
        path: Absolute path to video file

    Returns:
        dict with keys: fps, frame_count, width, height
        Values are 0 if unknown/unavailable.

    Probing strategy:
    1. Try ffprobe (most reliable)
    2. Fall back to OpenCV VideoCapture if ffprobe fails
    3. Return zeros if both fail
    """
    # Try ffprobe first
    try:
        result = _probe_with_ffprobe(path)
        if result and all(v > 0 for v in result.values()):
            return result
    except Exception:
        pass  # Fall through to OpenCV

    # Fall back to OpenCV
    try:
        return _probe_with_opencv(path)
    except Exception:
        # Ultimate fallback: zeros
        return {
            "fps": 0.0,
            "frame_count": 0,
            "width": 0,
            "height": 0
        }


def _probe_with_ffprobe(path: Path) -> Optional[dict]:
    """
    Use ffprobe to extract video metadata.

    Returns None if ffprobe is unavailable or fails.
    """
    try:
        # Run ffprobe to get video stream info as JSON
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                str(path)
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=True
        )

        data = json.loads(result.stdout)

        # Find first video stream
        video_stream = None
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                video_stream = stream
                break

        if not video_stream:
            return None

        # Extract metadata
        width = int(video_stream.get("width", 0))
        height = int(video_stream.get("height", 0))

        # FPS can be in various forms: "30/1", "29.97", etc.
        fps_str = video_stream.get("r_frame_rate", "0/1")
        if "/" in fps_str:
            num, denom = fps_str.split("/")
            fps = float(num) / float(denom) if float(denom) > 0 else 0.0
        else:
            fps = float(fps_str)

        # Frame count from format section
        format_info = data.get("format", {})
        duration = float(format_info.get("duration", 0))
        frame_count = int(fps * duration) if fps > 0 and duration > 0 else 0

        return {
            "fps": fps,
            "frame_count": frame_count,
            "width": width,
            "height": height
        }

    except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
            FileNotFoundError, json.JSONDecodeError, ValueError, KeyError):
        return None


def _probe_with_opencv(path: Path) -> dict:
    """
    Use OpenCV VideoCapture to extract video metadata.

    Returns dict with fps, frame_count, width, height (zeros if unavailable).
    """
    cap = cv2.VideoCapture(str(path))

    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS)) or 0.0
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 0
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 0

        # Sanity check: OpenCV sometimes reports fps=0 for certain codecs
        # We accept zeros here since caller can handle missing data

        return {
            "fps": fps,
            "frame_count": frame_count,
            "width": width,
            "height": height
        }
    finally:
        cap.release()


def delete_analysis_files(analysis_id: str) -> bool:
    """
    Delete video files from disk while preserving database record.

    This is called when user finishes analyzing - we keep the
    analysis results in the database but free up disk space.

    Deletes:
    - /data/analyses/{analysis_id}/video.* (uploaded video)
    - /data/analyses/{analysis_id}/ (entire directory)

    Note: Frames are auto-cleaned via tempfile.TemporaryDirectory
    in traditional_integration.py, so no separate frame cleanup needed.

    Args:
        analysis_id: UUID of the analysis

    Returns:
        bool: True if deleted successfully, False if directory didn't exist
    """
    analysis_dir = DATA_ROOT / analysis_id

    if not analysis_dir.exists():
        logger.warning(f"Analysis directory not found: {analysis_dir}")
        return False

    try:
        shutil.rmtree(analysis_dir)
        logger.info(f"Deleted analysis files: {analysis_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete analysis files for {analysis_id}: {e}")
        return False
