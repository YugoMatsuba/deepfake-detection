from flask import Blueprint, request, jsonify
import os
import tempfile
import base64
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
    - Returns top ELA frames with Base64-encoded images
    """
    data = request.get_json(silent=True) or {}
    input_path = data.get("input_path")
    top_percent = data.get("top_percent", 10)  # optional, defaults to 10%

    if not input_path:
        return jsonify(error="input_path_required"), 400

    try:
        result = run_ela(input_path, top_percent=top_percent)
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

# --- Noise Analysis ---
@bp_forensics.post("/noise_analysis")
def noise_route():
    """
    POST /api/forensics/noise_analysis
    Body: { "input_path": "frames" } OR { "input_path": "frames/frame1.jpg" }
    """
    data = request.get_json(silent=True) or {}
    input_path = data.get("input_path")
    if not input_path:
        return jsonify(error="input_path_required"), 400

    try:
        result = run_noise_analysis(input_path)
    except FileNotFoundError:
        return jsonify(error="file_or_folder_not_found"), 404
    except ValueError as e:
        return jsonify(error=str(e)), 400
    except Exception as e:
        return jsonify(error=str(e)), 500

    return jsonify(
        message="Noise analysis completed",
        result=result
    ), 200

# --- LBP Analysis ---
@bp_forensics.post("/lbp_analysis")
def lbp_route():
    """
    POST /api/forensics/lbp_analysis
    Body: { "input_path": "frames" } OR { "input_path": "frames/frame1.jpg" }
    Returns top LBP frames with Base64 images.
    """
    data = request.get_json(silent=True) or {}
    input_path = data.get("input_path")
    top_percent = data.get("top_percent", 10)  # optional, defaults to 10%

    if not input_path:
        return jsonify(error="input_path_required"), 400

    try:
        result = run_lbp_analysis(input_path, top_percent=top_percent)
    except FileNotFoundError:
        return jsonify(error="file_or_folder_not_found"), 404
    except ValueError as e:
        return jsonify(error=str(e)), 400
    except Exception as e:
        return jsonify(error=str(e)), 500

    return jsonify(
        message="LBP analysis completed",
        result=result
    ), 200



@bp_forensics.post("/analyze_frame")
def analyze_frame_route():
    """
    POST /api/forensics/analyze_frame
    Body: { "frame_data": "data:image/jpeg;base64,...", "analysis_type": "lbp", "frame_number": 123 }
    """
    data = request.get_json(silent=True) or {}
    frame_data = data.get("frame_data")
    analysis_type = data.get("analysis_type", "lbp")
    frame_number = data.get("frame_number")

    if not frame_data:
        return jsonify(error="frame_data_required"), 400

    try:
        # Remove base64 header if present
        if "," in frame_data:
            frame_data = frame_data.split(",")[1]
        img_data = base64.b64decode(frame_data)

        # Save to temp file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
        temp_file.write(img_data)
        temp_file.close()
        temp_path = temp_file.name

        # Run selected analysis
        if analysis_type == "lbp":
            result = run_lbp_analysis(temp_path)
        elif analysis_type == "ela":
            result = run_ela(temp_path)
        elif analysis_type == "noise":
            result = run_noise_analysis(temp_path)
        # elif analysis_type == "cmfd":
        #     result = run_cmfd_analysis(temp_path)  # TODO: implement CMFD analysis
        else:
            os.remove(temp_path)
            return jsonify(error="unsupported_analysis_type"), 400

        os.remove(temp_path)

        # ✅ Extract confidence/score if the result is a dict
        if isinstance(result, dict):
            score = result.get("score") or result.get("confidence") or result.get("value")
            image_file = result.get("lbp_image") or result.get("ela_image") or result.get("residual")
        else:
            score = result
            image_file = None

    except Exception as e:
        print(f"Error during frame analysis: {e}")
        return jsonify(error=str(e)), 500

    # ✅ Return simplified JSON with only score
    return jsonify({
        "frame_number": frame_number,
        "analysis_type": analysis_type,
        "score": score,
        "image_file": image_file
    }), 200
