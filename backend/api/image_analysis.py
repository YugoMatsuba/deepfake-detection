# backend/api/image_analysis.py
"""
Image analysis orchestrator.

Coordinates ML inference, traditional forensics, and EXIF analysis for single images.
"""
from __future__ import annotations
import os
import shutil
from pathlib import Path
from typing import Any, Optional
import logging

from storage import DATA_ROOT
from api.metadata_utils import run_image_exif_analysis
from api.traditional_forensics_utils.ela_analysis import run_ela
from api.traditional_forensics_utils.noise_analysis import run_noise_analysis
from api.traditional_forensics_utils.lbp_analysis import run_lbp_analysis

logger = logging.getLogger(__name__)


def run_image_analysis(
    image_path: str,
    image_sha256: str,
    ml_modules: list[str],
    traditional_modules: list[str],
    analysis_id: str
) -> dict[str, Any]:
    """
    Orchestrate image analysis pipeline.

    Args:
        image_path: Absolute path to image file
        image_sha256: SHA-256 hash of image (for EXIF chain-of-custody)
        ml_modules: List of ML models to run (e.g., ["xception", "spsl", "ucf"])
        traditional_modules: List of forensics methods (e.g., ["ela", "noise", "lbp"])
        analysis_id: Analysis UUID for persistent storage

    Returns:
        {
            "ml": {
                "xception": {"score": 0.87},
                "spsl": {"score": 0.82},
                "ucf": {"score": 0.91}
            },
            "traditional": {
                "ela": {
                    "score": 2.34,
                    "raw_score": 2.34,
                    "frame_number": 0,
                    "overlay_url": "/api/analyses/{id}/forensics/ela/frames/0/overlay"
                },
                "noise": {...},
                "lbp": {...}
            },
            "exif": {
                "analyzed_at": "2024-01-15T14:30:00Z",
                "file_hash": "abc123...",
                "metadata": {
                    "raw": {...},
                    "anomalies": {...}
                }
            }
        }
    """
    results = {
        "ml": {},
        "traditional": {},
        "exif": {}
    }

    # 1. ML Analysis (if requested)
    if ml_modules:
        results["ml"] = _run_ml_on_image(image_path, ml_modules, analysis_id)

    # 2. Traditional Forensics (if requested)
    if traditional_modules:
        results["traditional"] = _run_traditional_on_image(
            image_path, traditional_modules, analysis_id
        )

    # 3. EXIF Analysis (always included)
    results["exif"] = run_image_exif_analysis(image_path, image_sha256)

    return results


def _run_ml_on_image(image_path: str, ml_modules: list[str], analysis_id: str) -> dict:
    """
    Run ML inference on a single image.

    Uses ml/runner.py::analyze_single_frame but passes image directly (not video+frame).

    Returns:
        {
            "xception": {"score": 0.87},
            "spsl": {"score": 0.82},
            "ucf": {"score": 0.91}
        }

        OR if no face detected:
        {
            "error": "No face detected in image"
        }
    """
    try:
        # Import here to avoid circular dependencies
        from ml.runner import analyze_single_frame

        # Call ML analysis using frame_number=0 convention for images
        # The function expects a video_path and frame_number, but for images
        # we can pass the image path directly with frame_number=0
        result = analyze_single_frame(
            video_path=image_path,
            frame_number=0,
            device=None,  # Auto-detect
            models=ml_modules,
            weights=None  # Use defaults
        )

        # Check for errors
        if result.get("error"):
            logger.warning(f"ML analysis failed: {result['error']}")
            return {"error": result["error"].get("message", "ML analysis failed")}

        # Transform result format from per-frame to per-model scores
        models_result = result.get("models", {})
        ml_scores = {}

        for model_name, model_data in models_result.items():
            score = model_data.get("score")
            if score is not None:
                ml_scores[model_name] = {"score": score}

        return ml_scores if ml_scores else {"error": "No ML results"}

    except Exception as e:
        logger.error(f"ML analysis error: {e}")
        return {"error": str(e)}


def _run_traditional_on_image(
    image_path: str,
    traditional_modules: list[str],
    analysis_id: str
) -> dict:
    """
    Run traditional forensics (ELA, Noise, LBP) on a single image.

    Strategy:
    1. Copy image to frames/frame_0.jpg
    2. Run forensics on that frame
    3. Save overlays to forensics/{method}/frames/frame_0.jpg
    4. Return results with frame_number=0

    Returns:
        {
            "ela": {
                "score": 2.34,
                "raw_score": 2.34,
                "frame_number": 0,
                "overlay_url": "/api/analyses/{id}/forensics/ela/frames/0/overlay"
            },
            ...
        }
    """
    results = {}

    # Create frames directory and copy image as frame_0
    frames_dir = DATA_ROOT / analysis_id / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    frame_path = frames_dir / "frame_0.jpg"

    try:
        # Copy image to frame_0.jpg (convert to JPG if needed)
        from PIL import Image
        img = Image.open(image_path)
        # Convert to RGB if necessary (handles RGBA, grayscale, etc.)
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.save(frame_path, "JPEG", quality=95)

    except Exception as e:
        logger.error(f"Failed to prepare image for forensics: {e}")
        return {"error": f"Failed to prepare image: {str(e)}"}

    # Create forensics output directory
    forensics_dir = DATA_ROOT / analysis_id / "forensics"
    forensics_dir.mkdir(parents=True, exist_ok=True)

    # Run each forensics method
    for method_name in traditional_modules:
        try:
            method_dir = forensics_dir / method_name
            method_dir.mkdir(parents=True, exist_ok=True)

            # Run the appropriate forensics function
            if method_name == "ela":
                # ELA expects a folder, but we only have one frame
                raw_result = run_ela(
                    str(frames_dir),  # Folder containing frame_0.jpg
                    top_percent=100,  # Get result for our single frame
                    output_dir=str(method_dir),
                    analysis_id=analysis_id
                )

                # Extract the single frame result
                if raw_result and raw_result.get("frames"):
                    frame_result = raw_result["frames"][0]  # Only one frame
                    results["ela"] = {
                        "score": frame_result.get("score", 0),
                        "raw_score": frame_result.get("raw_score", 0),
                        "frame_number": 0,
                        "overlay_url": f"/api/analyses/{analysis_id}/forensics/ela/frames/0/overlay"
                    }

            elif method_name == "noise":
                raw_result = run_noise_analysis(
                    str(frames_dir),
                    top_percent=100,
                    output_dir=str(method_dir),
                    analysis_id=analysis_id
                )

                if raw_result and raw_result.get("frames"):
                    frame_result = raw_result["frames"][0]
                    results["noise"] = {
                        "score": frame_result.get("score", 0),
                        "confidence": frame_result.get("confidence", 0),
                        "raw_score": frame_result.get("raw_score", 0),
                        "frame_number": 0,
                        "overlay_url": f"/api/analyses/{analysis_id}/forensics/noise/frames/0/overlay"
                    }

            elif method_name == "lbp":
                raw_result = run_lbp_analysis(
                    str(frames_dir),
                    top_percent=100,
                    output_dir=str(method_dir),
                    analysis_id=analysis_id
                )

                if raw_result and raw_result.get("frames"):
                    frame_result = raw_result["frames"][0]
                    results["lbp"] = {
                        "score": frame_result.get("score", 0),
                        "raw_score": frame_result.get("raw_score", 0),
                        "frame_number": 0,
                        "overlay_url": f"/api/analyses/{analysis_id}/forensics/lbp/frames/0/overlay"
                    }

        except Exception as e:
            logger.error(f"Traditional forensics error for {method_name}: {e}")
            results[method_name] = {"error": str(e)}

    return results
