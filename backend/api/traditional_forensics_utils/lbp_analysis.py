import os
from pathlib import Path
from PIL import Image
import numpy as np
from skimage.feature import local_binary_pattern


def compute_lbp(frame_path, P=8, R=1):
    """
    Compute LBP image and anomaly score.
    Returns score and PIL image.
    """
    img = Image.open(frame_path).convert("L")
    img_np = np.array(img, dtype=np.uint8)

    # Compute LBP
    lbp = local_binary_pattern(img_np, P=P, R=R, method="uniform")

    # Convert LBP to image (normalized)
    lbp_img = Image.fromarray(np.uint8((lbp / lbp.max()) * 255))

    # Anomaly score = std deviation of LBP histogram
    n_bins = int(lbp.max() + 1)
    hist, _ = np.histogram(lbp.ravel(), bins=n_bins, range=(0, n_bins), density=True)
    score = float(np.std(hist))

    return score, lbp_img


def _save_overlay(image, frame_filename, output_dir):
    """Save overlay image to disk and return saved path."""
    if output_dir:
        # Parse frame number from filename (e.g., "frame_0001.jpg" -> "0001")
        stem = Path(frame_filename).stem
        digits = "".join(ch for ch in stem if ch.isdigit())
        if digits:
            out_path = Path(output_dir) / f"frame_{digits}.jpg"
            image.save(out_path, "JPEG", quality=90)
            return str(out_path)
    return None


def run_lbp_analysis(input_path, top_percent=10, output_dir=None, analysis_id=None):
    """
    Run LBP analysis on single image or folder.
    Saves overlay images to output_dir if provided.
    Returns top frames JSON (no base64, overlays saved to disk).
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
    results = []
    for fp in frame_paths:
        score, lbp_img = compute_lbp(fp)
        results.append({
            "frame": os.path.basename(fp),
            "score": score,
            "lbp_img": lbp_img
        })

    # Single frame case
    if len(results) == 1:
        # Save overlay to disk
        _save_overlay(results[0]["lbp_img"], results[0]["frame"], output_dir)
        return {
            "mode": "single_frame",
            "frame": results[0]["frame"],
            "score": results[0]["score"]
        }

    # Multi-frame case
    scores = [r["score"] for r in results]
    mean_score = float(np.mean(scores))
    std_score = float(np.std(scores)) + 1e-6

    for r in results:
        r["normalized_score"] = max((r["score"] - mean_score) / std_score, 0)

    results_sorted = sorted(results, key=lambda x: x["normalized_score"], reverse=True)

    # Top frames (cap at 32 to limit JSON payload size)
    top_count = min(max(1, int(len(results_sorted) * top_percent / 100)), 32)
    top_frames_data = results_sorted[:top_count]

    # Save overlays and build response
    top_frames = []
    for r in top_frames_data:
        # Save overlay to disk
        _save_overlay(r["lbp_img"], r["frame"], output_dir)
        top_frames.append({
            "frame": r["frame"],
            "score": r["score"],
            "normalized_score": r["normalized_score"]
        })

    return {
        "mode": "multi_frame",
        "top_percent": top_percent,
        "top_frames": top_frames
    }
