# backend/api/routes/video_upload.py
"""
Video upload endpoint that creates Analysis records.

Flow:
1. Receive multipart/form-data upload
2. Save to /data/analyses/{analysis_id}/video.{ext}
3. Compute SHA-256 hash
4. Probe video metadata (ffprobe → OpenCV fallback)
5. Create Analysis row with status="created"
6. Return {analysis_id, video_sha256, meta}
"""
from __future__ import annotations
import tempfile
from pathlib import Path
from flask import Blueprint, jsonify, request, session, send_file
from flask_cors import cross_origin
from werkzeug.utils import secure_filename

from api import get_db
from api.auth_utils import require_user
from models import Analysis
from storage import save_video_for_analysis, probe_video_metadata, DATA_ROOT

video_bp = Blueprint("video", __name__)

ALLOWED_MIME = {
    "video/mp4", "video/quicktime", "video/x-matroska", "video/webm", "video/avi"
}


@video_bp.post("/videos")
@require_user
def upload_video():
    """
    Upload video and create Analysis record.

    Expects:
    - multipart/form-data with 'file' field
    - Session must contain user_id (enforced by @require_user)

    Returns:
    - 201: {analysis_id, video_sha256, meta: {fps, frame_count, width, height}}
    - 400: validation errors
    - 401: unauthorized (no session)
    """
    if "file" not in request.files:
        return jsonify(error="No file part"), 400

    file = request.files["file"]

    if not file or file.filename == "":
        return jsonify(error="Empty filename"), 400

    if file.mimetype not in ALLOWED_MIME:
        return jsonify(error=f"Unsupported mimetype: {file.mimetype}"), 400

    # Get secure extension
    ext = Path(secure_filename(file.filename)).suffix or ".mp4"

    # Use context manager for DB session
    with get_db() as db:
        try:
            analysis = Analysis(
                user_id=session["user_id"],
                status="created",
                video_path="",  # Will be updated after save
                video_sha256="",  # Will be updated after save
            )
            db.add(analysis)
            db.flush()  # Get analysis.id without committing

            # Save uploaded file to temporary location first
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                file.save(tmp.name)
                tmp_path = Path(tmp.name)

            # Move to final location and compute SHA-256
            video_path, sha256 = save_video_for_analysis(tmp_path, ext, analysis.id)

            # Probe metadata
            meta = probe_video_metadata(video_path)

            # Update Analysis record
            analysis.video_path = str(video_path)
            analysis.video_sha256 = sha256
            analysis.meta_json = meta

            # Commit happens automatically in context manager
            return jsonify({
                "analysis_id": analysis.id,
                "video_sha256": sha256,
                "meta": meta
            }), 201

        except Exception as e:
            # Rollback happens automatically in context manager
            # Clean up video file if it exists
            try:
                video_dir = DATA_ROOT / analysis.id
                if video_dir.exists():
                    import shutil
                    shutil.rmtree(video_dir)
            except:
                pass
            return jsonify(error=f"Upload failed: {str(e)}"), 500


@video_bp.get("/videos/all")
@cross_origin()
def list_videos():
    """
    List all uploaded videos from analysis storage.

    Used by frame viewer to show available videos.
    Returns array of {id: analysis_id, ...metadata}.
    """
    videos = []

    # Iterate through all analysis directories
    if DATA_ROOT.exists():
        for analysis_dir in DATA_ROOT.iterdir():
            if not analysis_dir.is_dir():
                continue

            analysis_id = analysis_dir.name

            # Check if video exists
            video_files = list(analysis_dir.glob("video.*"))
            if video_files:
                videos.append({
                    "id": analysis_id,
                    "path": f"/api/videos/{analysis_id}"
                })

    return jsonify(videos), 200


@video_bp.get("/videos/<analysis_id>")
@cross_origin()
def get_video(analysis_id: str):
    """
    Serve video file for a given analysis.

    Used by frame viewer to stream video content.
    Does NOT require authentication (public video serving).
    """
    # Find video file in analysis directory
    video_dir = DATA_ROOT / analysis_id
    if not video_dir.exists():
        return jsonify(error="Analysis not found"), 404

    # Find video file (any extension)
    video_files = list(video_dir.glob("video.*"))
    if not video_files:
        return jsonify(error="Video file not found"), 404

    video_path = video_files[0]
    return send_file(video_path, mimetype="video/mp4")


@video_bp.get("/analyses/<analysis_id>/video")
@require_user
def get_analysis_video(analysis_id: str):
    """
    Serve video file for a given analysis with authentication and ownership check.

    Used by frame viewer to stream video content securely.
    Requires authentication and verifies user owns the analysis.

    Returns:
    - 200: Video file stream
    - 401: Unauthorized (no session)
    - 403: Forbidden (not owner)
    - 404: Analysis or video not found
    """
    with get_db() as db:
        # Check ownership
        from api.routes.analysis import check_analysis_ownership
        analysis = check_analysis_ownership(db, analysis_id)

        # Find video file in analysis directory
        video_dir = DATA_ROOT / analysis_id
        if not video_dir.exists():
            return jsonify(error="Analysis not found"), 404

        # Find video file (any extension)
        video_files = list(video_dir.glob("video.*"))
        if not video_files:
            return jsonify(error="Video file not found"), 404

        video_path = video_files[0]
        return send_file(video_path, mimetype="video/mp4")
