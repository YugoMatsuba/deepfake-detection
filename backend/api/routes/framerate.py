from flask import Blueprint, jsonify, current_app
import cv2
from pathlib import Path
from api.routes.video_upload import get_all_videos  # import the endpoint function

frame_rate_bp = Blueprint("framerate", __name__)

@frame_rate_bp.get("/framerate")
def get_frame_rate():
    # Call the get_all_videos function to get all metadata
    response = get_all_videos()
    videos = response.get_json()  # this gives the JSON array

    if not videos:
        return jsonify({"error": "No videos found"}), 404

    # Pick the latest video (last in array)
    latest_video = videos[-1]
    video_path = Path(latest_video["path"])

    if not video_path.exists():
        return jsonify({"error": "Video file not found"}), 404

    # Open video with OpenCV
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return jsonify({"error": "Could not open video"}), 400

    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.release()

    return jsonify({
        "video_id": latest_video["id"],
        "original_name": latest_video["original_name"],
        "frame_rate": fps
    })
