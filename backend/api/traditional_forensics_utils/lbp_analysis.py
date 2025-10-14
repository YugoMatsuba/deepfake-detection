import os
import base64
from io import BytesIO
from PIL import Image
import numpy as np
from skimage.feature import local_binary_pattern


def compute_lbp_base64(frame_path, P=8, R=1):
    """
    Compute LBP image and anomaly score.
    Returns dict with frame name, score, and Base64 LBP image.
    """
    img = Image.open(frame_path).convert("L")
    img_np = np.array(img, dtype=np.uint8)

    # Compute LBP
    lbp = local_binary_pattern(img_np, P=P, R=R, method="uniform")

    # Convert LBP to image (normalized)
    lbp_img = Image.fromarray(np.uint8((lbp / lbp.max()) * 255))

    # Encode to Base64
    buffer = BytesIO()
    lbp_img.save(buffer, format="JPEG", quality=85)
    lbp_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    lbp_base64 = f"data:image/jpeg;base64,{lbp_base64}"

    # Anomaly score = std deviation of LBP histogram
    n_bins = int(lbp.max() + 1)
    hist, _ = np.histogram(lbp.ravel(), bins=n_bins, range=(0, n_bins), density=True)
    score = float(np.std(hist))

    return {
        "frame": os.path.basename(frame_path),
        "score": score,
        "lbp_image_base64": lbp_base64
    }


def run_lbp_analysis(input_path, top_percent=10):
    """
    Run LBP analysis on single image or folder.
    Returns top frames JSON with Base64 LBP images.
    """
    # Collect frame paths
    if os.path.isdir(input_path):
        frame_files = [f for f in os.listdir(input_path)
                       if f.lower().endswith((".jpg", ".png"))]
        if not frame_files:
            return {"error": f"No frames found in folder: {input_path}"}
        frame_paths = [os.path.join(input_path, f) for f in frame_files]

    elif os.path.isfile(input_path) and input_path.lower().endswith((".jpg", ".png")):
        frame_paths = [input_path]

    else:
        return {"error": f"Invalid input path: {input_path}"}

    # Compute LBP for each frame
    results = [compute_lbp_base64(fp) for fp in frame_paths]

    # Single frame case
    if len(results) == 1:
        return {
            "mode": "single_frame",
            "frame": results[0]["frame"],
            "score": results[0]["score"],
            "lbp_image_base64": results[0]["lbp_image_base64"]
        }

    # Multi-frame case
    scores = [r["score"] for r in results]
    mean_score = float(np.mean(scores))
    std_score = float(np.std(scores)) + 1e-6

    for r in results:
        r["normalized_score"] = max((r["score"] - mean_score) / std_score, 0)

    results_sorted = sorted(results, key=lambda x: x["normalized_score"], reverse=True)

    # Top frames
    top_count = max(1, int(len(results_sorted) * top_percent / 100))
    top_frames = results_sorted[:top_count]

    return {
        "mode": "multi_frame",
        "top_percent": top_percent,
        "top_frames": top_frames
    }
