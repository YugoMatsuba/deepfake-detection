# backend/api/routes/analysis.py
"""
Analysis lifecycle endpoints.

Routes:
- POST /api/analyses/<id>/start - Start analysis (synchronous, returns full results)
- GET /api/analyses/<id> - Fetch analysis status/results (scores only from DB)
- POST /api/analyses/<id>/frames/<frame_number>/forensics - On-demand frame analysis
"""
from __future__ import annotations
import copy
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import cv2
import numpy as np
from flask import Blueprint, jsonify, request, session
from sqlalchemy import update
from werkzeug.exceptions import HTTPException

from api import get_db
from api.auth_utils import require_user, check_analysis_ownership_or_admin
from models import Analysis
from storage import delete_analysis_files
from api.ml_integration import run_ml_analysis, run_single_frame_ml_analysis
from api.traditional_integration import (
    run_traditional_forensics,
    transform_ela_result,
    transform_noise_result,
    transform_lbp_result,
)
from api.traditional_forensics_utils.frame_extraction import extract_single_frame
from api.traditional_forensics_utils.ela_analysis import run_ela
from api.traditional_forensics_utils.noise_analysis import run_noise_analysis
from api.traditional_forensics_utils.lbp_analysis import run_lbp_analysis
from api.metadata_utils import run_metadata_analysis
import logging

logger = logging.getLogger(__name__)

# Import ML schema version for traceability
try:
    import sys
    from pathlib import Path
    # Add ml directory to path if not already present
    ml_dir = Path(__file__).parent.parent.parent / "ml"
    if ml_dir.exists() and str(ml_dir) not in sys.path:
        sys.path.insert(0, str(ml_dir))
    from schema import SCHEMA_VERSION
except ImportError:
    SCHEMA_VERSION = "unknown"

analysis_bp = Blueprint("analysis", __name__)


def _capture_ml_provenance(device: Optional[str] = None) -> Dict[str, Any]:
    """
    Capture ML traceability metadata for transparency and reproducibility.

    Returns:
        Dictionary with:
        - schema_version: ML output schema version
        - commit_hash: Git commit SHA (or 'unknown' if not available)
        - device: Device used for inference (cpu/cuda)
        - timestamp: ISO8601 timestamp of analysis
    """
    # Capture git commit hash
    commit_hash = "unknown"
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).parent.parent.parent,  # Project root
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            commit_hash = result.stdout.strip()
    except Exception:
        pass  # Silently fall back to 'unknown'

    # Determine device (will be set from env or auto-detected by ML module)
    device_used = device or os.environ.get("DEVICE", "auto-detect")

    return {
        "schema_version": SCHEMA_VERSION,
        "commit_hash": commit_hash,
        "device": device_used,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@analysis_bp.post("/analyses/<analysis_id>/start")
@require_user
def start_analysis(analysis_id: str):
    """
    Start synchronous analysis (blocking, 1-2 min).

    Request body:
    {
      "modules": ["xception", "spsl", "ucf"],  // ML modules
      "traditional": ["ela", "noise"]           // Traditional forensics
    }

    Response (200): Same structure as GET /analyses/<id>
    {
      "analysis_id": "uuid",
      "status": "succeeded",
      "result": {
        "video": {"fps": 29.97, "frame_count": 300, ...},
        "ml": {
          "xception": {
            "score": 0.87,
            "frames": [{"index": 0, "time": 0.00, "score": 0.903}, ...],
            "weights_hash": "sha256..."
          },
          ...
        },
        "traditional": {
          "ela": {
            "score": 0.65,
            "frames": [{"frame_number": 1, "score": 0.65, "overlay_url": "/api/analyses/{id}/forensics/ela/frames/1/overlay"}]
          },
          ...
        }
      },
      "created_at": "2025-10-14T...",
      "completed_at": "2025-10-14T..."
    }

    Response (400/403/404/500): error message
    """
    try:
        with get_db() as db:
            # Check access (ownership or admin)
            analysis = check_analysis_ownership_or_admin(db, analysis_id)

            # Parse request
            body = request.get_json() or {}
            ml_modules = body.get("modules", [])
            traditional_modules = body.get("traditional", [])

            if not ml_modules and not traditional_modules:
                return jsonify(error="No modules specified"), 400

            # Validate modules against whitelist
            VALID_ML_MODULES = {"xception", "spsl", "ucf"}
            VALID_TRADITIONAL = {"ela", "noise", "lbp", "cmfd", "temporal"}

            invalid_ml = set(ml_modules) - VALID_ML_MODULES
            invalid_trad = set(traditional_modules) - VALID_TRADITIONAL

            if invalid_ml or invalid_trad:
                invalid_all = invalid_ml | invalid_trad
                return jsonify(error=f"Invalid modules: {', '.join(sorted(invalid_all))}"), 400

            # Optimistic UPDATE to prevent race condition (must be status="created")
            stmt = (
                update(Analysis)
                .where(Analysis.id == analysis_id, Analysis.status == "created")
                .values(status="running", updated_at=datetime.now(timezone.utc))
            )
            result = db.execute(stmt)
            # Don't commit yet - let context manager handle it

            if result.rowcount == 0:
                # Another request already started or analysis is not in "created" state
                db.refresh(analysis)
                return jsonify(error=f"Analysis already {analysis.status}"), 409

            # Collect baseline video metadata (used even if ML modules are skipped)
            video_meta = _get_video_metadata(analysis.video_path)

            # Run analyses (BLOCKING)
            ml_results = {}
            traditional_results = {}
            ml_provenance = None

            try:
                # Run ML analysis
                ml_frames_meta = []
                ml_timing_meta = None

                if ml_modules:
                    # Capture provenance metadata before running analysis
                    ml_provenance = _capture_ml_provenance(device=None)

                    ml_output = run_ml_analysis(
                        video_path=analysis.video_path,
                        modules=ml_modules,
                        device=None  # Will use env var DEVICE or auto-detect
                    )
                    ml_results = ml_output.get("models", {})
                    # Prefer ML runner's video metadata (same source as baseline, but validated through pipeline)
                    video_meta = ml_output.get("video") or video_meta
                    ml_frames_meta = ml_output.get("frames", [])
                    ml_timing_meta = ml_output.get("timing_ms")

                    # Log completion
                    print(f"✓ ML analysis completed for {analysis.id} ({', '.join(ml_modules)})")

                    # Filter frames based on average score across all models > 0.5
                    if ml_results:
                        filtered_frames = []

                        for frame in ml_frames_meta:
                            frame_index = frame["index"]

                            # Collect scores for this frame from all models
                            scores = []
                            for model_name, model_data in ml_results.items():
                                model_frames = model_data.get("frames", [])
                                frame_score = next(
                                    (f["score"] for f in model_frames if f["index"] == frame_index),
                                    None
                                )
                                if frame_score is not None:
                                    scores.append(frame_score)

                            # Calculate average score for this frame
                            if scores:
                                avg_score = sum(scores) / len(scores)
                                if avg_score > 0.5:  # 50% threshold
                                    filtered_frames.append(frame)

                        ml_frames_meta = filtered_frames  # Replace with filtered list

                # Run traditional forensics
                if traditional_modules:
                    print(f"[Analysis] Starting traditional forensics: {', '.join(traditional_modules)}")
                    traditional_results = run_traditional_forensics(
                        video_path=analysis.video_path,
                        modules=traditional_modules,
                        analysis_id=analysis.id
                    )
                    print(f"✓ Traditional forensics completed for {analysis.id}")

                # Run metadata forensics analysis (always run, fast ~1-3s)
                metadata_result = {}
                try:
                    metadata_result = run_metadata_analysis(
                        video_path=analysis.video_path,
                        video_sha256=analysis.video_sha256
                    )
                except Exception as e:
                    logger.error(f"Metadata analysis failed for {analysis.id}: {e}")
                    metadata_result = {
                        "error": f"Metadata analysis failed: {str(e)}",
                        "analyzed_at": None,
                        "file_hash": analysis.video_sha256
                    }

                # Build result_json for DB storage
                result_json = {
                    "metadata": metadata_result,  # Forensic metadata (EXIF, integrity, frame hashes)
                    "video": video_meta,  # Video playback metadata (fps, frame_count, duration, resolution)
                    "ml": {},
                    "traditional": {}
                }

                # ML results: Store ALL 32 frames in database
                # Mark all frames with requested_adhoc=False (initial analysis, not user-requested)
                # Frontend will filter to show only: (score > 0.5) OR (requested_adhoc == True)
                for model_name, model_data in ml_results.items():
                    all_frames = model_data.get("frames", [])

                    # Mark ALL frames as not requested by user (initial auto-analysis)
                    frames_with_flag = [
                        {**frame, "requested_adhoc": False}
                        for frame in all_frames
                    ]

                    result_json["ml"][model_name] = {
                        "score": model_data.get("score"),
                        "frames": frames_with_flag,  # Store ALL 32 frames
                        "weights_hash": model_data.get("weights_hash")
                    }

                # Traditional results: save scores and frame metadata
                for method_name, method_data in traditional_results.items():
                    result_json["traditional"][method_name] = {
                        "score": method_data.get("score"),
                        "confidence": method_data.get("confidence"),  # for noise
                        "frames": method_data.get("frames", [])
                        # NOTE: overlay URLs are included, overlays persisted to disk
                    }

                # Update Analysis record with scores and provenance metadata
                analysis.status = "succeeded"
                analysis.result_json = result_json
                analysis.updated_at = datetime.now(timezone.utc)

                # Store ML provenance metadata in meta_json for traceability
                if ml_provenance:
                    current_meta = analysis.meta_json or {}
                    current_meta["ml_provenance"] = ml_provenance
                    analysis.meta_json = current_meta

                # Commit happens automatically in context manager

            except Exception as e:
                error_msg = str(e)
                analysis.status = "failed"
                analysis.error = error_msg
                analysis.updated_at = datetime.now(timezone.utc)
                # Commit happens automatically in context manager
                return jsonify(error=f"Analysis failed: {error_msg}"), 500

            # Build response payload matching GET endpoint structure
            response = {
                "analysis_id": analysis.id,
                "status": "succeeded",
                "result": analysis.result_json,  # Same as GET endpoint
                "created_at": analysis.created_at.isoformat(),
                "completed_at": analysis.updated_at.isoformat()
            }

            return jsonify(response), 200

    except HTTPException:
        raise  # Re-raise HTTP exceptions (401/403/404) from check_analysis_ownership_or_admin
    except Exception as e:
        return jsonify(error=str(e)), 500


def _get_video_metadata(video_path: str) -> Dict[str, Any]:
    """
    Extract basic metadata (fps, frame count, duration, resolution) from a video.
    Falls back to sensible defaults if the file cannot be probed.
    """
    metadata: Dict[str, Any] = {
        "path": video_path,
        "fps": None,
        "frame_count": None,
        "duration_sec": None,
        "width": None,
        "height": None,
    }

    if not os.path.exists(video_path):
        return metadata

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return metadata

    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0
        width = cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0.0
        height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0.0

        duration_sec = frame_count / fps if fps > 0 else 0.0

        metadata.update(
            {
                "fps": float(fps) if fps else None,
                "frame_count": int(frame_count) if frame_count else None,
                "duration_sec": float(duration_sec) if duration_sec else None,
                "width": int(width) if width else None,
                "height": int(height) if height else None,
            }
        )
    finally:
        cap.release()

    return metadata


@analysis_bp.post("/analyses/<analysis_id>/start-image")
@require_user
def start_image_analysis(analysis_id: str):
    """
    Start synchronous image analysis (blocking).

    Request body:
    {
      "modules": ["xception", "spsl", "ucf"],  // ML modules
      "traditional": ["ela", "noise", "lbp"]   // Traditional forensics
    }

    Response (200):
    {
      "analysis_id": "uuid",
      "status": "succeeded",
      "result": {
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
          ...
        },
        "exif": {
          "analyzed_at": "2024-01-15T14:30:00Z",
          "file_hash": "abc123...",
          "metadata": {...}
        }
      },
      "created_at": "2025-10-28T...",
      "completed_at": "2025-10-28T..."
    }

    Response (400/403/404/500): error message
    """
    try:
        with get_db() as db:
            # Check access (ownership or admin)
            analysis = check_analysis_ownership_or_admin(db, analysis_id)

            # Verify this is an image analysis
            if analysis.media_type != "image":
                return jsonify(error="This endpoint is for images only. Use /start for videos."), 400

            # Parse request
            body = request.get_json() or {}
            ml_modules = body.get("modules", [])
            traditional_modules = body.get("traditional", [])

            if not ml_modules and not traditional_modules:
                return jsonify(error="No modules specified"), 400

            # Validate modules
            VALID_ML_MODULES = {"xception", "spsl", "ucf"}
            VALID_TRADITIONAL = {"ela", "noise", "lbp"}

            invalid_ml = set(ml_modules) - VALID_ML_MODULES
            invalid_trad = set(traditional_modules) - VALID_TRADITIONAL

            if invalid_ml or invalid_trad:
                invalid_all = invalid_ml | invalid_trad
                return jsonify(error=f"Invalid modules: {', '.join(sorted(invalid_all))}"), 400

            # Optimistic UPDATE to prevent race condition
            stmt = (
                update(Analysis)
                .where(Analysis.id == analysis_id, Analysis.status == "created")
                .values(status="running", updated_at=datetime.now(timezone.utc))
            )
            result = db.execute(stmt)

            if result.rowcount == 0:
                db.refresh(analysis)
                return jsonify(error=f"Analysis already {analysis.status}"), 409

            # Run image analysis (BLOCKING)
            try:
                from api.image_analysis import run_image_analysis

                results = run_image_analysis(
                    image_path=analysis.video_path,  # Still named video_path for consistency
                    image_sha256=analysis.video_sha256,
                    ml_modules=ml_modules,
                    traditional_modules=traditional_modules,
                    analysis_id=analysis.id
                )

                # Mark as succeeded and store results
                analysis.status = "succeeded"
                analysis.result_json = results
                analysis.updated_at = datetime.now(timezone.utc)

                print(f"✓ Image analysis completed for {analysis.id}")

                return jsonify({
                    "analysis_id": analysis.id,
                    "status": "succeeded",
                    "result": results,
                    "created_at": analysis.created_at.isoformat(),
                    "completed_at": analysis.updated_at.isoformat()
                }), 200

            except Exception as e:
                # Mark as failed
                analysis.status = "failed"
                analysis.error = str(e)
                analysis.updated_at = datetime.now(timezone.utc)

                print(f"✗ Image analysis failed for {analysis.id}: {e}")

                return jsonify(error=f"Image analysis failed: {str(e)}"), 500

    except HTTPException:
        raise
    except Exception as e:
        return jsonify(error=str(e)), 500


@analysis_bp.get("/analyses/<analysis_id>")
@require_user
def get_analysis(analysis_id: str):
    """
    Fetch analysis status and results (scores + overlay URLs from DB).

    Response (200):
    {
      "analysis_id": "uuid",
      "status": "created|running|succeeded|failed",
      "result": {
        "video": {
          "fps": 29.97,
          "frame_count": 300,
          "duration_sec": 10.0,
          "width": 1920,
          "height": 1080
        },
        "ml": {
          "xception": {
            "score": 0.87,
            "frames": [{"index": 0, "time": 0.00, "score": 0.903}, ...],
            "weights_hash": "sha256..."
          },
          ...
        },
        "traditional": {
          "ela": {
            "score": 0.65,
            "frames": [{"frame_number": 1, "score": 0.65, "overlay_url": "/api/analyses/{id}/forensics/ela/frames/1/overlay"}]
          },
          ...
        }
      },
      "error": "error message if failed",
      "created_at": "2025-10-14T...",
      "updated_at": "2025-10-14T..."
    }

    Response (403/404): error message
    """
    with get_db() as db:
        analysis = check_analysis_ownership_or_admin(db, analysis_id)

        response = {
            "analysis_id": analysis.id,
            "status": analysis.status,
            "result": analysis.result_json,  # Scores + overlay URLs
            "error": analysis.error,
            "created_at": analysis.created_at.isoformat(),
            "updated_at": analysis.updated_at.isoformat()
        }

        return jsonify(response), 200


def _merge_and_recompute_traditional(
    method_name: str,
    new_frame_result: dict,
    existing_data: dict,
    frame_number: int,
    analysis_id: str
) -> dict:
    """
    Merge new frame analysis with existing data and recompute z-scores across ALL frames.

    This ensures z-scores are computed with full statistical context, not just single-frame isolation.

    Args:
        method_name: "ela", "noise", or "lbp"
        new_frame_result: Single-frame result from run_ela/run_noise_analysis/run_lbp_analysis
                         e.g. {"mode": "single_frame", "frame": "...", "confidence": 2.8}
        existing_data: Current data from DB (analysis.result_json["traditional"][method])
                      e.g. {"score": 1.5, "frames": [{...}, {...}]}
        frame_number: The frame number being analyzed
        analysis_id: Analysis UUID for overlay URL generation

    Returns:
        Updated method data with recalculated z-scores for ALL frames (initial + ad-hoc)

    Algorithm:
        1. Extract raw score from new frame result
        2. Merge new frame into existing frames list (replace if exists)
        3. Collect all raw scores from all frames
        4. Recompute z-scores: z = (raw - mean) / std for EVERY frame
        5. Update overall score (mean of top N z-scores)
    """
    # 1. Extract raw score from new frame
    if method_name == "noise":
        raw_score = new_frame_result.get("confidence")
    else:
        raw_score = new_frame_result.get("score")

    if raw_score is None:
        raise ValueError(f"No score found in new frame result for {method_name}")

    # 2. Build list of ALL frames (existing + new)
    existing_frames = list(existing_data.get("frames", []))

    # Check if frame already exists (replace if so)
    frame_index = None
    for idx, frame in enumerate(existing_frames):
        if frame.get("frame_number") == frame_number:
            frame_index = idx
            break

    # Create new frame entry
    new_frame_entry = {
        "frame_number": frame_number,
        "raw_score": float(raw_score),
        "overlay_url": f"/api/analyses/{analysis_id}/forensics/{method_name}/frames/{frame_number}/overlay",
        "flagged": True  # Ad-hoc frames are explicitly requested by user, so flagged
    }

    if frame_index is not None:
        # Replace existing frame
        existing_frames[frame_index] = new_frame_entry
    else:
        # Add new frame
        existing_frames.append(new_frame_entry)

    # 3. Collect all raw scores
    all_raw_scores = [frame["raw_score"] for frame in existing_frames]

    # 4. Recompute z-scores across ALL frames
    mean_score = float(np.mean(all_raw_scores))
    std_score = float(np.std(all_raw_scores)) + 1e-6  # Avoid division by zero

    for frame in existing_frames:
        raw = frame["raw_score"]
        z_score = (raw - mean_score) / std_score
        frame["score"] = float(z_score)

        # Noise also uses "confidence" field
        if method_name == "noise":
            frame["confidence"] = float(z_score)

    # 5. Compute overall score (MAX z-score = most suspicious frame)
    z_scores = [f["score"] for f in existing_frames]
    overall_score = float(max(z_scores))

    # 6. Return updated structure
    result = {
        "score": overall_score,
        "frames": existing_frames
    }

    # Noise also has "confidence" at top level
    if method_name == "noise":
        result["confidence"] = overall_score

    return result


def _merge_analysis_results_with_dedup(
    existing_data: dict,
    new_results: dict,
    method_name: str
) -> dict:
    """
    Merge new full-sampling analysis results with existing data, deduplicating frames.

    Used for retroactive full analysis feature where user runs full sampling analysis
    on a method that may already have some ad-hoc frames.

    Args:
        existing_data: Existing method data from DB (may be empty or have ad-hoc frames)
        new_results: New results from full sampling analysis
        method_name: "ela", "noise", or "lbp"

    Returns:
        Merged data with recalculated z-scores across ALL frames (existing + new unique)
    """
    # Step 1: Extract frames
    existing_frames = list(existing_data.get("frames", []))
    new_frames = list(new_results.get("frames", []))

    # Step 2: Build deduplication set
    existing_frame_numbers = {f.get("frame_number") for f in existing_frames}

    # Step 3: Filter out duplicates from new frames
    unique_new_frames = [
        f for f in new_frames
        if f.get("frame_number") not in existing_frame_numbers
    ]

    print(f"[MERGE DEBUG] {method_name}: {len(existing_frames)} existing, {len(new_frames)} new, {len(unique_new_frames)} unique new")

    # Step 4: Merge frames
    all_frames = existing_frames + unique_new_frames

    if not all_frames:
        # No frames at all - return empty result
        return {
            "score": 0.0,
            "confidence": 0.0 if method_name == "noise" else None,
            "frames": []
        }

    # Step 5: Recalculate z-scores across ALL frames
    raw_scores = [f["raw_score"] for f in all_frames]
    mean_score = float(np.mean(raw_scores))
    std_score = float(np.std(raw_scores)) + 1e-6  # Avoid division by zero

    for frame in all_frames:
        raw = frame["raw_score"]
        z_score = (raw - mean_score) / std_score
        frame["score"] = float(z_score)

        # Noise also uses "confidence" field
        if method_name == "noise":
            frame["confidence"] = float(z_score)

    # Step 6: Recalculate overall score (MAX z-score)
    z_scores = [f["score"] for f in all_frames]
    overall_score = float(max(z_scores))

    # Step 7: Return merged structure
    result = {
        "score": overall_score,
        "frames": all_frames
    }

    # Noise also has "confidence" at top level
    if method_name == "noise":
        result["confidence"] = overall_score

    return result


@analysis_bp.post("/analyses/<analysis_id>/frames/<int:frame_number>/forensics")
@require_user
def analyze_frame(analysis_id: str, frame_number: int):
    """
    Run on-demand traditional forensics analysis on a specific frame.

    Request body:
    {
      "methods": ["ela", "noise", "lbp"]
    }

    Response (200):
    {
      "analysis_id": "uuid",
      "frame_number": 42,
      "results": {
        "ela": {
          "score": 0.73,
          "frames": [{"frame_number": 42, "score": 0.73, "overlay_url": "/api/analyses/{id}/forensics/ela/frames/42/overlay"}]
        },
        "noise": {
          "confidence": 0.68,
          "frames": [{"frame_number": 42, "confidence": 0.68, "overlay_url": "/api/analyses/{id}/forensics/noise/frames/42/overlay"}]
        },
        "lbp": {
          "score": 0.81,
          "frames": [{"frame_number": 42, "score": 0.81, "overlay_url": "/api/analyses/{id}/forensics/lbp/frames/42/overlay"}]
        }
      }
    }

    Response (400/403/404/500): error message
    """
    try:
        with get_db() as db:
            # Check access (ownership or admin)
            analysis = check_analysis_ownership_or_admin(db, analysis_id)

            # Parse request
            body = request.get_json() or {}
            methods = body.get("methods", [])

            if not methods:
                return jsonify(error="No methods specified"), 400

            # Validate methods
            VALID_METHODS = {"ela", "noise", "lbp"}
            invalid_methods = set(methods) - VALID_METHODS
            if invalid_methods:
                return jsonify(
                    error=f"Invalid methods: {', '.join(sorted(invalid_methods))}"
                ), 400

            # Extract frame to persistent directory
            from storage import DATA_ROOT
            frames_dir = DATA_ROOT / analysis.id / "frames"
            frames_dir.mkdir(parents=True, exist_ok=True)
            frame_path = str(frames_dir / f"frame_{frame_number}.jpg")

            try:
                # Only extract if frame doesn't already exist (avoid JPEG re-encoding variance)
                if not os.path.exists(frame_path):
                    extract_single_frame(
                        video_path=analysis.video_path,
                        frame_number=frame_number,
                        output_path=frame_path
                    )

                # Fetch current result_json from DB (deep copy to trigger SQLAlchemy change detection)
                current_json = copy.deepcopy(analysis.result_json) if analysis.result_json else {}
                if "traditional" not in current_json:
                    current_json["traditional"] = {}

                # Check if frame already analyzed for ALL requested methods (short-circuit if so)
                all_methods_exist = True
                for method in methods:
                    method_data = current_json["traditional"].get(method, {})
                    existing_frames = method_data.get("frames", [])
                    frame_exists = any(f.get("frame_number") == frame_number for f in existing_frames)
                    if not frame_exists:
                        all_methods_exist = False
                        break

                if all_methods_exist:
                    # Frame already analyzed for all requested methods - return cached results
                    results = {}
                    for method in methods:
                        method_data = current_json["traditional"].get(method, {})
                        existing_frames = method_data.get("frames", [])
                        frame_data = next((f for f in existing_frames if f.get("frame_number") == frame_number), None)
                        if frame_data:
                            results[method] = {
                                "score": frame_data.get("score"),
                                "frame_number": frame_number,
                                "cached": True
                            }

                    response = {
                        "analysis_id": analysis.id,
                        "frame_number": frame_number,
                        "results": results
                    }
                    return jsonify(response), 200

                # Run each requested forensics method on the single frame
                results = {}

                for method in methods:
                    try:
                        # Create method-specific forensics directory
                        method_dir = DATA_ROOT / analysis.id / "forensics" / method
                        method_dir.mkdir(parents=True, exist_ok=True)

                        # Run analysis and get raw single-frame result
                        if method == "ela":
                            raw_result = run_ela(
                                frame_path,
                                top_percent=10,
                                output_dir=str(method_dir),
                                analysis_id=analysis.id
                            )

                        elif method == "noise":
                            raw_result = run_noise_analysis(
                                frame_path,
                                top_percent=10,
                                output_dir=str(method_dir),
                                analysis_id=analysis.id
                            )

                        elif method == "lbp":
                            raw_result = run_lbp_analysis(
                                frame_path,
                                top_percent=10,
                                output_dir=str(method_dir),
                                analysis_id=analysis.id
                            )

                        else:
                            continue

                        # Merge with existing data and recompute z-scores
                        existing_method_data = current_json["traditional"].get(method, {})

                        updated_method_data = _merge_and_recompute_traditional(
                            method_name=method,
                            new_frame_result=raw_result,
                            existing_data=existing_method_data,
                            frame_number=frame_number,
                            analysis_id=analysis.id
                        )

                        # Update result_json with merged data
                        current_json["traditional"][method] = updated_method_data

                        # Return the FULL updated method data (not just single frame)
                        results[method] = updated_method_data

                    except Exception as e:
                        results[method] = {
                            "score": None,
                            "error": f"Analysis failed: {str(e)}"
                        }

                # Save updated result_json back to DB
                analysis.result_json = current_json
                db.commit()

                response = {
                    "analysis_id": analysis.id,
                    "frame_number": frame_number,
                    "results": results
                }

                return jsonify(response), 200

            except ValueError as e:
                # Frame number out of range
                return jsonify(error=str(e)), 400

            except Exception as e:
                return jsonify(error=f"Frame extraction failed: {str(e)}"), 500

    except HTTPException:
        raise  # Re-raise HTTP exceptions (401/403/404)
    except Exception as e:
        return jsonify(error=str(e)), 500


@analysis_bp.post("/analyses/<analysis_id>/frames/<int:frame_number>/ml")
@require_user
def analyze_frame_ml(analysis_id: str, frame_number: int):
    """
    Run on-demand ML analysis on a specific frame.

    Request body:
    {
      "models": ["xception", "spsl", "ucf"]  // Optional, defaults to all 3
    }

    Response (200):
    {
      "analysis_id": "uuid",
      "frame_number": 42,
      "results": {
        "xception": {
          "score": 0.856,
          "index": 42,
          "time": 1.4
        },
        "spsl": {
          "score": 0.821,
          "index": 42,
          "time": 1.4
        },
        "ucf": {
          "score": 0.903,
          "index": 42,
          "time": 1.4
        }
      }
    }

    Response (400/403/404/500): error message
    """
    try:
        with get_db() as db:
            # Check access (ownership or admin)
            analysis = check_analysis_ownership_or_admin(db, analysis_id)

            # Parse request
            body = request.get_json() or {}
            models = body.get("models", ["xception", "spsl", "ucf"])

            if not models:
                return jsonify(error="No models specified"), 400

            # Validate models
            VALID_MODELS = {"xception", "spsl", "ucf"}
            invalid_models = set(models) - VALID_MODELS
            if invalid_models:
                return jsonify(
                    error=f"Invalid models: {', '.join(sorted(invalid_models))}"
                ), 400

            # Check if frame already analyzed for ALL requested models (short-circuit if so)
            current_json = copy.deepcopy(analysis.result_json) if analysis.result_json else {}
            ml_data = current_json.get("ml", {})

            all_models_exist = True
            for model_name in models:
                if model_name not in ml_data:
                    all_models_exist = False
                    break
                existing_frames = ml_data[model_name].get("frames", [])
                frame_exists = any(f.get("index") == frame_number for f in existing_frames)
                if not frame_exists:
                    all_models_exist = False
                    break

            if all_models_exist:
                # Frame already analyzed for all requested models - return cached results
                model_results = {}
                for model_name in models:
                    existing_frames = ml_data[model_name].get("frames", [])
                    frame_data = next((f for f in existing_frames if f.get("index") == frame_number), None)
                    if frame_data:
                        model_results[model_name] = {"score": frame_data.get("score")}

                response = {
                    "analysis_id": analysis.id,
                    "frame_number": frame_number,
                    "time": 0.0,  # Cached result, no compute time
                    "results": model_results,
                    "cached": True
                }
                return jsonify(response), 200

            # Run ML analysis on single frame
            try:
                results = run_single_frame_ml_analysis(
                    video_path=analysis.video_path,
                    frame_number=frame_number,
                    models=models,
                    device=None  # Will use env var DEVICE or auto-detect
                )

                # Extract frame_number and time from results
                response_frame_number = results.pop("frame_number", frame_number)
                response_time = results.pop("time", 0.0)

                # Remaining keys are model results
                model_results = results

                # Persist ad-hoc ML results to DB with requested_adhoc flag
                try:

                    # Merge ad-hoc results into each model's frames
                    for model_name, model_result in model_results.items():
                        if model_name not in ml_data:
                            ml_data[model_name] = {"score": None, "frames": [], "weights_hash": None}

                        existing_frames = ml_data[model_name].get("frames", [])

                        # Create new frame entry with requested_adhoc flag
                        new_frame = {
                            "index": response_frame_number,
                            "time": response_time,
                            "score": model_result.get("score"),
                            "requested_adhoc": True  # Mark as user-requested
                        }

                        # Find if frame already exists
                        frame_idx = next(
                            (i for i, f in enumerate(existing_frames) if f.get("index") == response_frame_number),
                            None
                        )

                        if frame_idx is not None:
                            # Update existing frame
                            existing_frames[frame_idx] = new_frame
                        else:
                            # Add new frame
                            existing_frames.append(new_frame)

                        ml_data[model_name]["frames"] = existing_frames

                        # Recalculate per-model score as average of ALL frames
                        frame_scores = [f["score"] for f in existing_frames if f.get("score") is not None]
                        if frame_scores:
                            ml_data[model_name]["score"] = sum(frame_scores) / len(frame_scores)

                    # Save updated data
                    current_json["ml"] = ml_data
                    analysis.result_json = current_json
                    analysis.updated_at = datetime.now(timezone.utc)
                    # Commit happens automatically via context manager

                    print(f"[AD-HOC ML] Saved frame {response_frame_number} for models: {', '.join(model_results.keys())}")

                except Exception as db_error:
                    # Log but don't fail the request if DB save fails
                    print(f"[AD-HOC ML] Warning: Failed to persist to DB: {db_error}")

                response = {
                    "analysis_id": analysis.id,
                    "frame_number": response_frame_number,
                    "time": response_time,
                    "results": model_results
                }

                return jsonify(response), 200

            except Exception as e:
                return jsonify(error=f"ML analysis failed: {str(e)}"), 500

    except HTTPException:
        raise  # Re-raise HTTP exceptions (401/403/404)
    except Exception as e:
        return jsonify(error=str(e)), 500


@analysis_bp.post("/analyses/<analysis_id>/run-full/<method>")
@require_user
def run_full_analysis_retroactive(analysis_id: str, method: str):
    """
    Run full sampling analysis on a method that wasn't included in initial analysis.

    Allows users to retroactively add full sampling analysis (e.g., run ELA on all
    sampled frames after initial analysis only included LBP). Deduplicates with
    any existing ad-hoc frames and recalculates aggregate statistics.

    Args:
        analysis_id: Analysis UUID
        method: One of ["ela", "noise", "lbp", "ml"]

    Response (200): Full analysis result (same structure as GET /analyses/<id>)
    Response (400): Invalid method
    Response (403/404): Access denied or analysis not found
    Response (500): Analysis failed
    """
    try:
        with get_db() as db:
            # Check access (ownership or admin)
            analysis = check_analysis_ownership_or_admin(db, analysis_id)

            # Validate method
            VALID_METHODS = {"ela", "noise", "lbp", "ml"}
            if method not in VALID_METHODS:
                return jsonify(error=f"Invalid method: {method}. Must be one of: {', '.join(sorted(VALID_METHODS))}"), 400

            print(f"\n[FULL ANALYSIS] Starting retroactive full {method} analysis for {analysis_id}")

            # Fetch current result_json
            current_json = copy.deepcopy(analysis.result_json) if analysis.result_json else {}
            if "traditional" not in current_json:
                current_json["traditional"] = {}
            if "ml" not in current_json:
                current_json["ml"] = {}

            try:
                if method == "ml":
                    # Run full ML analysis on all 3 models
                    print(f"[FULL ANALYSIS] Running ML inference...")
                    ml_output = run_ml_analysis(
                        video_path=analysis.video_path,
                        modules=["xception", "spsl", "ucf"],
                        device=None  # Will use env var DEVICE or auto-detect
                    )
                    ml_results = ml_output.get("models", {})

                    # For each model, merge with existing data
                    for model_name, new_model_data in ml_results.items():
                        existing_model_data = current_json["ml"].get(model_name, {})
                        existing_frames = existing_model_data.get("frames", [])
                        new_frames = new_model_data.get("frames", [])

                        # Deduplicate by frame index
                        existing_indices = {f.get("index") for f in existing_frames}
                        unique_new = [f for f in new_frames if f.get("index") not in existing_indices]

                        print(f"[FULL ANALYSIS] {model_name}: {len(existing_frames)} existing, {len(new_frames)} new, {len(unique_new)} unique new")

                        # Merge and mark new frames as requested_adhoc=False (auto-analysis)
                        all_frames = existing_frames + [
                            {**f, "requested_adhoc": False} for f in unique_new
                        ]

                        # Recalculate per-model score (average)
                        frame_scores = [f["score"] for f in all_frames if f.get("score") is not None]
                        avg_score = sum(frame_scores) / len(frame_scores) if frame_scores else None

                        # Update model data
                        current_json["ml"][model_name] = {
                            "score": avg_score,
                            "frames": all_frames,
                            "weights_hash": new_model_data.get("weights_hash")
                        }

                    print(f"[FULL ANALYSIS] ✓ ML analysis completed")

                else:
                    # Traditional forensics
                    print(f"[FULL ANALYSIS] Running {method} forensics...")
                    traditional_results = run_traditional_forensics(
                        video_path=analysis.video_path,
                        modules=[method],
                        analysis_id=analysis.id
                    )

                    new_method_data = traditional_results.get(method, {})
                    existing_method_data = current_json["traditional"].get(method, {})

                    # Merge with deduplication
                    merged_data = _merge_analysis_results_with_dedup(
                        existing_data=existing_method_data,
                        new_results=new_method_data,
                        method_name=method
                    )

                    # Update traditional data
                    current_json["traditional"][method] = merged_data

                    print(f"[FULL ANALYSIS] ✓ {method} forensics completed")

                # Save to database
                analysis.result_json = current_json
                analysis.updated_at = datetime.now(timezone.utc)
                # Commit happens automatically via context manager

                print(f"[FULL ANALYSIS] ✓ Saved to database")

                # Return full analysis result
                response = {
                    "analysis_id": analysis.id,
                    "status": analysis.status,
                    "result": current_json,
                    "updated_at": analysis.updated_at.isoformat()
                }

                return jsonify(response), 200

            except Exception as e:
                error_msg = str(e)
                print(f"[FULL ANALYSIS] ✗ Failed: {error_msg}")
                return jsonify(error=f"Full {method} analysis failed: {error_msg}"), 500

    except HTTPException:
        raise  # Re-raise HTTP exceptions (401/403/404)
    except Exception as e:
        return jsonify(error=str(e)), 500


# DISABLED: Persistence overhaul - files are no longer auto-deleted
# @analysis_bp.post("/analyses/<analysis_id>/cleanup")
# @require_user
# def cleanup_analysis_files_endpoint(analysis_id: str):
#     """
#     Delete video/frame files from disk while keeping database record.
#
#     Called when user finishes analysis in FrameViewer.
#     Database record persists so reports can still be generated.
#
#     Requires: Ownership or admin role
#     Returns: 204 No Content on success
#     """
#     try:
#         with get_db() as db:
#             # Check ownership
#             analysis = check_analysis_ownership_or_admin(db, analysis_id)
#
#             # Delete files from disk
#             success = delete_analysis_files(analysis_id)
#
#             if not success:
#                 logger.warning(f"Files already deleted for analysis {analysis_id}")
#                 # Still return 204 - idempotent operation
#
#             return "", 204
#
#     except HTTPException:
#         raise  # Re-raise HTTP exceptions (401/403/404)
#     except Exception as e:
#         logger.error(f"Failed to cleanup analysis {analysis_id}: {e}")
#         return jsonify(error=str(e)), 500


@analysis_bp.delete("/analyses/<analysis_id>")
@require_user
def delete_analysis(analysis_id: str):
    """
    Delete entire analysis: database record + files.

    Called from PastReports page when user wants to permanently
    delete an analysis.

    Requires: Ownership or admin role
    Returns: 204 No Content
    """
    try:
        with get_db() as db:
            # Check access (ownership or admin)
            analysis = check_analysis_ownership_or_admin(db, analysis_id)

            # Delete files from disk (if they still exist)
            delete_analysis_files(analysis_id)

            # Delete database record
            db.delete(analysis)
            # Commit happens automatically in context manager

            return "", 204

    except HTTPException:
        raise  # Re-raise HTTP exceptions (401/403/404)
    except Exception as e:
        logger.error(f"Failed to delete analysis {analysis_id}: {e}")
        return jsonify(error=str(e)), 500
