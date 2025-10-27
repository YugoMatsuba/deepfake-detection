from flask import Blueprint, jsonify, g
import cv2
from pathlib import Path
from api import get_db
from api.auth_utils import require_user, current_user
from models import Analysis
from storage import DATA_ROOT

frame_rate_bp = Blueprint("framerate", __name__)

@frame_rate_bp.get("/framerate")
@require_user
def get_frame_rate():
    """
    Get frame rate of latest video accessible to current user.

    Regular users see only their own videos.
    Admin/owner users see all videos.

    Returns:
    - 200: {video_id, original_name, frame_rate}
    - 401: Unauthorized (no session)
    - 404: No videos found
    """
    with get_db() as db:
        user = current_user(db)

        # Admin/owner can see all videos
        if user.role in ("admin", "owner"):
            analyses = db.query(Analysis).order_by(Analysis.created_at.desc()).all()
        else:
            # Regular users see only their own
            analyses = db.query(Analysis).filter(
                Analysis.user_id == user.id
            ).order_by(Analysis.created_at.desc()).all()

        if not analyses:
            return jsonify({"error": "No videos found"}), 404

        # Find latest analysis with existing video file
        for analysis in analyses:
            analysis_dir = DATA_ROOT / analysis.id
            if analysis_dir.exists():
                video_files = list(analysis_dir.glob("video.*"))
                if video_files:
                    video_path = video_files[0]

                    # Open video with OpenCV
                    cap = cv2.VideoCapture(str(video_path))
                    if not cap.isOpened():
                        continue  # Try next analysis

                    fps = cap.get(cv2.CAP_PROP_FPS)
                    cap.release()

                    return jsonify({
                        "video_id": analysis.id,
                        "original_name": analysis.original_filename or video_path.name,
                        "frame_rate": fps
                    })

        return jsonify({"error": "No valid video files found"}), 404
