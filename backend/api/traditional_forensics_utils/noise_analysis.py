import os
from pathlib import Path
from PIL import Image
import numpy as np
from scipy.ndimage import gaussian_filter


def compute_noise(frame_path):
    """
    Compute spatial noise residual and anomaly score.
    Returns residual image (PIL), and raw anomaly score.
    """
    # Load frame and convert to grayscale
    img = Image.open(frame_path).convert("L")
    img_np = np.array(img, dtype=np.float32)

    # Smooth image using Gaussian filter
    smoothed = gaussian_filter(img_np, sigma=1.0)

    # Noise residual
    residual = img_np - smoothed

    # Create residual image
    residual_img = Image.fromarray(np.clip(residual + 128, 0, 255).astype(np.uint8))

    # Anomaly score = standard deviation of residual
    score = np.std(residual)
    return score, residual_img


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


def run_noise_analysis(input_path, top_percent=10, output_dir=None, analysis_id=None):
    """
    Run noise analysis on a folder or single frame.
    Saves overlay images to output_dir if provided.
    Returns JSON with top frames (no base64, overlays saved to disk).
    """

    # Collect frame paths
    if os.path.isdir(input_path):
        frame_files = [f for f in os.listdir(input_path)
                       if f.lower().endswith((".jpg", ".png"))]
        if not frame_files:
            return {"error": f"No frames found in folder {input_path}"}
        frame_paths = [os.path.join(input_path, f) for f in frame_files]

    elif os.path.isfile(input_path) and input_path.lower().endswith((".jpg", ".png")):
        frame_paths = [input_path]

    else:
        return {"error": f"Invalid input path {input_path}"}

    # Compute noise scores
    results = []
    for path in frame_paths:
        score, residual_img = compute_noise(path)
        results.append((os.path.basename(path), score, residual_img))

    # Single frame case
    if len(results) == 1:
        filename, score, residual_img = results[0]
        # Save overlay to disk
        _save_overlay(residual_img, filename, output_dir)
        # Return raw score, not tanh transformation
        return {
            "mode": "single_frame",
            "frame": filename,
            "confidence": float(score)
        }

    # Multi-frame case
    scores_only = [s for _, s, _ in results]
    mean_score = np.mean(scores_only)
    std_score = np.std(scores_only) + 1e-6

    normalized = [(f, max((s - mean_score) / std_score, 0), img)
                  for f, s, img in results]
    sorted_results = sorted(normalized, key=lambda x: x[1], reverse=True)

    # Cap at 32 frames to limit JSON payload size
    top_count = min(max(1, int(len(sorted_results) * top_percent / 100)), 32)
    top_frames = sorted_results[:top_count]

    # Save overlays and build response
    frame_list = []
    for f, s, img in top_frames:
        # Save overlay to disk
        _save_overlay(img, f, output_dir)
        frame_list.append({
            "frame": f,
            "score": float(s)
        })

    # Return top frames JSON
    return {
        "mode": "multi_frame",
        "top_frames": frame_list
    }

