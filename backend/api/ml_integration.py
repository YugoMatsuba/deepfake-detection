# backend/api/ml_integration.py
"""
ML analysis integration wrapper.

Bridges Flask backend with ML runner module.
Handles ML module execution and output transformation for API responses.
"""
from __future__ import annotations
import os
import sys
from pathlib import Path
from typing import Any

# Add repo root to path for imports
REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))


def run_ml_analysis(video_path: str, modules: list[str], device: str | None = None) -> dict[str, Any]:
    """
    Run ML deepfake detection on video.

    Args:
        video_path: Absolute path to video file
        modules: List of ML module names (e.g., ["xception", "spsl", "ucf"])
        device: Device override ("cpu" or "cuda"), or None to use env var/auto-detect

    Returns:
        {
            "models": {
                "xception": {
                    "score": 0.871,
                    "frames": [
                        {"index": 0, "time": 0.00, "score": 0.903},
                        ...
                    ],
                    "weights_hash": "sha256..."
                },
                ...
            },
            "video": {
                "path": "...",
                "fps": 29.97,
                ...
            },
            "frames": [...],
            "timing_ms": {...}
        }

    Raises:
        Exception: If ML analysis fails
    """
    # Determine device
    if device is None:
        device = os.getenv("DEVICE", "cpu")  # Default to cpu

    # Import ML runner
    from ml.runner import run

    # Run inference
    results = run(
        video_path=video_path,
        models=modules,
        device=device,
        weights=None,  # Will use defaults from constants
        compute_hashes=True
    )

    # Check for errors
    if results.get("error"):
        error = results["error"]
        raise Exception(f"ML inference failed at stage '{error['stage']}': {error['message']}")

    # Transform output format for API
    # ML runner returns: {"models": [{"name": "Xception", "score": 0.87, "frames": [...]}, ...], ...}
    # We need structured output with model dict plus metadata.

    api_results = {}
    for model in results.get("models", []):
        model_name = model["name"].lower()

        api_results[model_name] = {
            "score": model.get("score"),
            "frames": model.get("frames", []),
            "weights_hash": model.get("weights_hash")
        }

    return {
        "models": api_results,
        "video": results.get("video"),
        "frames": results.get("frames", []),
        "timing_ms": results.get("timing_ms"),
    }


def run_single_frame_ml_analysis(
    video_path: str,
    frame_number: int,
    models: list[str],
    device: str | None = None
) -> dict[str, Any]:
    """
    Run ML deepfake detection on a single frame.

    Args:
        video_path: Absolute path to video file
        frame_number: 0-indexed frame number to analyze
        models: List of ML module names (e.g., ["xception", "spsl", "ucf"])
        device: Device override ("cpu" or "cuda"), or None to use env var/auto-detect

    Returns:
        {
            "frame_number": 42,
            "time": 1.4,
            "xception": {
                "score": 0.856,
                "index": 42,
                "time": 1.4
            },
            "spsl": { ... },
            "ucf": { ... }
        }

    Raises:
        Exception: If ML analysis fails
    """
    # Determine device
    if device is None:
        device = os.getenv("DEVICE", "cpu")  # Default to cpu

    # Import ML runner
    from ml.runner import analyze_single_frame

    # Run single frame inference
    results = analyze_single_frame(
        video_path=video_path,
        frame_number=frame_number,
        models=models,
        device=device,
        weights=None  # Will use defaults from constants
    )

    # Check for errors
    if results.get("error"):
        error = results["error"]
        raise Exception(f"ML single frame analysis failed: {error.get('message', 'Unknown error')}")

    # Transform output format for API
    # ML runner returns: {"frame_number": 42, "time": 1.4, "models": {"xception": {"score": 0.856}, ...}, ...}
    # We need flattened structure with model results at top level

    api_results = {
        "frame_number": results.get("frame_number"),
        "time": results.get("time")
    }

    for model_name, model_data in results.get("models", {}).items():
        api_results[model_name] = {
            "score": model_data.get("score"),
            "index": results.get("frame_number"),
            "time": results.get("time")
        }

    return api_results
