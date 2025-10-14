from flask import Flask, jsonify
import cv2
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route("/frame_rate", methods=["GET"])
def get_frame_rate():
    video_path = "uploads/rickroll.mp4"  # Or dynamically set this
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        return jsonify({"error": "Could not open video"}), 400

    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.release()

    return jsonify({"frame_rate": fps})
    
if __name__ == "__main__":
    app.run(debug=True)