import os
import base64
from io import BytesIO
from PIL import Image
import numpy as np
from scipy.ndimage import gaussian_filter

# Configuration constants
NOISE_PCTL_LOW = 1
NOISE_PCTL_HIGH = 99
NOISE_MAX_WIDTH = 960
NOISE_PNG_LEVEL = 9


def stretch_to_uint8(arr, low_pct, high_pct):
    """
    Apply percentile-based contrast stretch to make subtle variations visible.

    Args:
        arr: 2D numpy array (float)
        low_pct: Lower percentile (e.g., 1)
        high_pct: Upper percentile (e.g., 99)

    Returns:
        uint8 array with values stretched to full 0-255 range
    """
    lo, hi = np.percentile(arr, (low_pct, high_pct))
    vis = ((arr - lo) / max(hi - lo, 1e-6)) * 255.0
    return np.clip(vis, 0, 255).astype(np.uint8)


def downscale_overlay(img, max_width=960):
    """
    Downscale PIL image to max_width while preserving aspect ratio.

    Args:
        img: PIL Image
        max_width: Maximum width in pixels

    Returns:
        Downscaled PIL Image (or original if already smaller)
    """
    if img.width > max_width:
        ratio = max_width / img.width
        new_h = int(img.height * ratio)
        return img.resize((max_width, new_h), Image.BILINEAR)
    return img


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

    # Create residual image with percentile-based contrast stretch
    residual_u8 = stretch_to_uint8(residual, NOISE_PCTL_LOW, NOISE_PCTL_HIGH)
    residual_img = Image.fromarray(residual_u8, mode='L')

    # Downscale for efficient transport
    residual_img = downscale_overlay(residual_img, NOISE_MAX_WIDTH)

    # Anomaly score = standard deviation of residual
    score = np.std(residual)
    return score, residual_img


def encode_image_to_base64(image):
    """Convert PIL image to Base64 PNG (with MIME prefix)."""
    buffer = BytesIO()
    image.save(buffer, format="PNG", compress_level=NOISE_PNG_LEVEL, optimize=True)
    base64_data = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{base64_data}"


def run_noise_analysis(input_path, top_percent=10):
    """
    Run noise analysis on a folder or single frame.
    Returns JSON with top frames and their Base64 residuals.
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
        confidence = float(np.tanh(score * 10))
        return {
            "mode": "single_frame",
            "frame": filename,
            "confidence": confidence,
            "residual_image_base64": encode_image_to_base64(residual_img)
        }

    # Multi-frame case
    scores_only = [s for _, s, _ in results]
    mean_score = np.mean(scores_only)
    std_score = np.std(scores_only) + 1e-6

    # Compute z-scores (no zero-clipping - negatives are meaningful)
    normalized = [(f, (s - mean_score) / std_score, img)
                  for f, s, img in results]
    sorted_results = sorted(normalized, key=lambda x: x[1], reverse=True)

    # Cap at 32 frames to limit JSON payload size
    top_count = min(max(1, int(len(sorted_results) * top_percent / 100)), 32)
    top_frames = sorted_results[:top_count]

    # Return top frames JSON
    return {
        "mode": "multi_frame",
        "top_frames": [
            {
                "frame": f,
                "score": float(s),
                "residual_image_base64": encode_image_to_base64(img)
            }
            for f, s, img in top_frames
        ]
    }

