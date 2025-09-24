from flask import Blueprint, request, jsonify
from api.traditional_forensics_utils.frame_extraction import extract_frames
from api.traditional_forensics_utils.ela_analysis import run_ela
from api.traditional_forensics_utils.noise_analysis import run_noise_analysis
from api.traditional_forensics_utils.lbp_analysis import run_lbp_analysis

bp_forensics = Blueprint("forensics", __name__)

# --- Frame Extraction ---
@bp_forensics.post("/extract_frames")
def extract_frames_route():
    """
    POST /api/forensics/extract_frames
    Body: { "video_path": "uploads/video1.mp4" }
    """
    data = request.get_json(silent=True) or {}
    video_path = data.get("video_path")
    if not video_path:
        return jsonify(error="video_path_required"), 400

    try:
        frames = extract_frames(video_path)
    except FileNotFoundError:
        return jsonify(error="video_not_found"), 404
    except Exception as e:
        return jsonify(error=str(e)), 500

    return jsonify(
        message=f"Extracted {len(frames)} frames",
        frames=frames
    ), 200

# --- ELA Analysis ---
@bp_forensics.post("/ela_analysis")
def ela_analysis_route():
    """
    POST /api/forensics/ela_analysis
    Body: { "input_path": "frames/video1" }
    - input_path can be a single image OR a folder of frames
    """
    data = request.get_json(silent=True) or {}
    input_path = data.get("input_path")
    if not input_path:
        return jsonify(error="input_path_required"), 400

    try:
        result = run_ela(input_path)
    except FileNotFoundError:
        return jsonify(error="file_or_folder_not_found"), 404
    except ValueError as e:
        return jsonify(error=str(e)), 400
    except Exception as e:
        return jsonify(error=str(e)), 500

    return jsonify(
        message="ELA analysis complete",
        result=result
    ), 200

# Noise Analysis
@bp_forensics.post("/noise_analysis")
def noise_route():
    """
    POST /api/forensics/noise
    Body: { "input_path": "frames" } OR { "input_path": "frames/frame1.jpg" }
    """
    data = request.get_json(silent=True) or {}
    input_path = data.get("input_path")
    if not input_path:
        return jsonify(error="input_path_required"), 400

    try:
        confidence = run_noise_analysis(input_path)
    except Exception as e:
        return jsonify(error=str(e)), 500

    return jsonify(message="Noise analysis completed", confidence=confidence), 200

# LBP Analysis
@bp_forensics.post("/lbp_analysis")
def lbp_route():
    data = request.get_json(silent=True) or {}
    input_path = data.get("input_path")
    if not input_path:
        return jsonify(error="input_path_required"), 400

    try:
        result = run_lbp_analysis(input_path)
    except Exception as e:
        return jsonify(error=str(e)), 500

    return jsonify(result), 200