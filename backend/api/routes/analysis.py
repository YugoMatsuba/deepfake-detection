# backend/api/routes/analysis.py
"""
Analysis lifecycle endpoints.

Routes:
- POST /api/analyses/<id>/start - Start analysis (synchronous, returns full results)
- GET /api/analyses/<id> - Fetch analysis status/results (scores only from DB)
"""
from __future__ import annotations
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request
from sqlalchemy import update
from werkzeug.exceptions import HTTPException

from api import get_db
from api.auth_utils import require_login, check_analysis_ownership
from models import Analysis
from api.ml_integration import run_ml_analysis
from api.traditional_integration import run_traditional_forensics

analysis_bp = Blueprint("analysis", __name__)


@analysis_bp.post("/analyses/<analysis_id>/start")
@require_login
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

            # Run analyses (BLOCKING)
            ml_results = {}
            traditional_results = {}

            try:
                # Run ML analysis
                if ml_modules:
                    ml_results = run_ml_analysis(
                        video_path=analysis.video_path,
                        modules=ml_modules,
                        device=None  # Will use env var DEVICE or auto-detect
                    )

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
                "traditional": traditional_results,  # Includes ephemeral overlays
                "created_at": analysis.created_at.isoformat(),
                "completed_at": analysis.updated_at.isoformat()
            }

            return jsonify(response), 200

    except HTTPException:
        raise  # Re-raise HTTP exceptions (401/403/404) from check_analysis_ownership
    except Exception as e:
        return jsonify(error=str(e)), 500


@analysis_bp.get("/analyses/<analysis_id>")
@require_login
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
