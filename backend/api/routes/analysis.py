# backend/api/routes/analysis.py
"""
Analysis lifecycle endpoints.

Routes:
- POST /api/analyses/<id>/start - Start analysis (synchronous, returns full results)
- GET /api/analyses/<id> - Fetch analysis status/results (scores only from DB)
- POST /api/analyses/<id>/frames/<frame_number>/forensics - On-demand frame analysis
"""
from __future__ import annotations
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import cv2
from flask import Blueprint, jsonify, request, session
from sqlalchemy import update
from werkzeug.exceptions import HTTPException

from api import get_db
from api.auth_utils import require_user, check_analysis_ownership
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

    Response (200):
    {
      "analysis_id": "uuid",
      "status": "succeeded",
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
      },
      "created_at": "2025-10-14T...",
      "completed_at": "2025-10-14T..."
    }

    Note: ML results include per-frame scores but NO overlays.
          Traditional results include overlay URLs (overlays persisted to disk).

    Response (400/403/404/500): error message
    """
    try:
        with get_db() as db:
            # Check ownership
            analysis = check_analysis_ownership(db, analysis_id)

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

            # Collect baseline metadata (used even if ML modules are skipped)
            video_metadata = _get_video_metadata(analysis.video_path)

            # Run analyses (BLOCKING)
            ml_results = {}
            traditional_results = {}
            ml_provenance = None

            try:
                # Run ML analysis
                ml_video_meta = video_metadata
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
                    ml_video_meta = ml_output.get("video") or video_metadata
                    ml_frames_meta = ml_output.get("frames", [])
                    ml_timing_meta = ml_output.get("timing_ms")

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
                    traditional_results = run_traditional_forensics(
                        video_path=analysis.video_path,
                        modules=traditional_modules,
                        analysis_id=analysis.id
                    )

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

                # Extract scores-only for DB storage
                result_json = {
                    "metadata": metadata_result,  # From metadata analysis above
                    "ml": {},
                    "traditional": {}
                }

                # ML results: save scores + frames (no overlays to strip)
                for model_name, model_data in ml_results.items():
                    result_json["ml"][model_name] = {
                        "score": model_data.get("score"),
                        "frames": model_data.get("frames", []),
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

            # Build full response payload
            # Metadata: from upload (persisted in DB)
            # ML: scores + frames (no overlays)
            # Traditional: scores + overlay URLs (overlays persisted to disk)
            response = {
                "analysis_id": analysis.id,
                "status": "succeeded",
                "metadata": analysis.result_json.get("metadata", {}),  # From upload
                "ml": ml_results,
                "ml_video": ml_video_meta,
                "ml_frames": ml_frames_meta,
                "ml_timing": ml_timing_meta,
                "traditional": traditional_results,  # Includes ephemeral overlays
                "created_at": analysis.created_at.isoformat(),
                "completed_at": analysis.updated_at.isoformat()
            }

            return jsonify(response), 200

    except HTTPException:
        raise  # Re-raise HTTP exceptions (401/403/404) from check_analysis_ownership
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
        analysis = check_analysis_ownership(db, analysis_id)

        response = {
            "analysis_id": analysis.id,
            "status": analysis.status,
            "result": analysis.result_json,  # Scores + overlay URLs
            "error": analysis.error,
            "created_at": analysis.created_at.isoformat(),
            "updated_at": analysis.updated_at.isoformat()
        }

        return jsonify(response), 200


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
            # Check ownership
            analysis = check_analysis_ownership(db, analysis_id)

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
            frame_path = str(frames_dir / f"frame_{frame_number:04d}.jpg")

            try:
                extract_single_frame(
                    video_path=analysis.video_path,
                    frame_number=frame_number,
                    output_path=frame_path
                )

                # Run each requested forensics method on the single frame
                results = {}

                for method in methods:
                    try:
                        # Create method-specific forensics directory
                        method_dir = DATA_ROOT / analysis.id / "forensics" / method
                        method_dir.mkdir(parents=True, exist_ok=True)

                        if method == "ela":
                            raw_result = run_ela(
                                frame_path,
                                top_percent=10,
                                output_dir=str(method_dir),
                                analysis_id=analysis.id
                            )
                            transformed = transform_ela_result(raw_result, analysis.id)

                        elif method == "noise":
                            raw_result = run_noise_analysis(
                                frame_path,
                                top_percent=10,
                                output_dir=str(method_dir),
                                analysis_id=analysis.id
                            )
                            transformed = transform_noise_result(raw_result, analysis.id)

                        elif method == "lbp":
                            raw_result = run_lbp_analysis(
                                frame_path,
                                top_percent=10,
                                output_dir=str(method_dir),
                                analysis_id=analysis.id
                            )
                            transformed = transform_lbp_result(raw_result, analysis.id)

                        else:
                            continue

                        # Annotate each frame entry with the requested frame number
                        frames = transformed.get("frames", [])
                        for entry in frames:
                            entry.setdefault("frame_number", frame_number)
                        transformed["frames"] = frames

                        results[method] = transformed

                    except Exception as e:
                        results[method] = {
                            "score": None,
                            "error": f"Analysis failed: {str(e)}"
                        }

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
            # Check ownership
            analysis = check_analysis_ownership(db, analysis_id)

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
#             analysis = check_analysis_ownership(db, analysis_id)
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
            # Check ownership
            analysis = check_analysis_ownership(db, analysis_id)

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
