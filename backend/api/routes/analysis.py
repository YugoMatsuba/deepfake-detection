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

analysis_bp = Blueprint("analysis", __name__)


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
          "overlay": "data:image/png;base64,..."  // EPHEMERAL, not in DB
        },
        ...
      },
      "created_at": "2025-10-14T...",
      "completed_at": "2025-10-14T..."
    }

    Note: ML results include per-frame scores but NO overlays.
          Traditional results include base64 overlays (ephemeral, not saved to DB).

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

            try:
                # Run ML analysis
                ml_video_meta = video_metadata
                ml_frames_meta = []
                ml_timing_meta = None

                if ml_modules:
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
                        modules=traditional_modules
                    )

                # Extract scores-only for DB storage
                result_json = {
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

                # Traditional results: strip base64 overlays before saving
                for method_name, method_data in traditional_results.items():
                    result_json["traditional"][method_name] = {
                        "score": method_data.get("score")
                        # NOTE: "overlay" field intentionally omitted (not saved to DB)
                    }

                # Update Analysis record with scores only
                analysis.status = "succeeded"
                analysis.result_json = result_json
                analysis.updated_at = datetime.now(timezone.utc)
                # Commit happens automatically in context manager

            except Exception as e:
                error_msg = str(e)
                analysis.status = "failed"
                analysis.error = error_msg
                analysis.updated_at = datetime.now(timezone.utc)
                # Commit happens automatically in context manager
                return jsonify(error=f"Analysis failed: {error_msg}"), 500

            # Build full response payload
            # ML: scores + frames (no overlays)
            # Traditional: scores + base64 overlays (ephemeral, not in DB)
            response = {
                "analysis_id": analysis.id,
                "status": "succeeded",
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
    Fetch analysis status and results (scores only from DB, no base64).

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
          "ela": {"score": 0.65},
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
            "result": analysis.result_json,  # Scores only (no base64 overlays)
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
          "overlay": "data:image/jpeg;base64,..."
        },
        "noise": {
          "confidence": 0.68,
          "overlay": "data:image/jpeg;base64,..."
        },
        "lbp": {
          "score": 0.81,
          "overlay": "data:image/jpeg;base64,..."
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

            # Extract frame to temporary directory (consistent with initial analysis pattern)
            with tempfile.TemporaryDirectory(prefix=f"frame_{frame_number}_") as tmp_dir:
                frame_path = os.path.join(tmp_dir, f"frame_{frame_number}.jpg")

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
                            if method == "ela":
                                raw_result = run_ela(frame_path, top_percent=10)
                                transformed = transform_ela_result(raw_result)

                            elif method == "noise":
                                raw_result = run_noise_analysis(frame_path, top_percent=10)
                                transformed = transform_noise_result(raw_result)

                            elif method == "lbp":
                                raw_result = run_lbp_analysis(frame_path, top_percent=10)
                                transformed = transform_lbp_result(raw_result)

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
            # Temp directory auto-cleaned up here

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
