from flask import Flask, jsonify
import cv2
from flask_cors import CORS
from pathlib import Path
import json

app = Flask(__name__)
CORS(app)

VIDEO_META_FILE = Path(__file__).parent / "videos.json"  # adjust path if needed
UPLOADS_DIR = Path(__file__).parent / "instance" / "uploads"

@app.route("/frame_rate", methods=["GET"])
def get_frame_rate():
    # Check if metadata file exists
    if not VIDEO_META_FILE.exists():
        return jsonify({"error": "No videos uploaded"}), 404

    try:
        videos = json.loads(VIDEO_META_FILE.read_text())
        if not videos:
            return jsonify({"error": "No videos found"}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to read videos metadata: {e}"}), 500

    # Get the latest uploaded video (last in array)
    latest_video = videos[-1]
    video_path = Path(latest_video["path"])
    
    if not video_path.exists():
        return jsonify({"error": "Video file not found"}), 404

    # Open video with OpenCV and get FPS
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

if __name__ == "__main__":
    app.run(port=5050, debug=True)
