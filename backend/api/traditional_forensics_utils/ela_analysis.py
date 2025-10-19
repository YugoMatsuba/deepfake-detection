import os
import base64
from io import BytesIO
from PIL import Image, ImageChops, ImageEnhance
import numpy as np

# Configuration constants
ELA_PCTL_LOW = 5
ELA_PCTL_HIGH = 95
ELA_MAX_WIDTH = 960
ELA_PNG_LEVEL = 9


def stretch_to_uint8(arr, low_pct, high_pct):
    """
    Apply percentile-based contrast stretch to make subtle variations visible.

    Args:
        arr: 2D or 3D numpy array (float)
        low_pct: Lower percentile (e.g., 5)
        high_pct: Upper percentile (e.g., 95)

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


def compute_ela_score(image_path, resave_quality=90):
    """
    Compute ELA anomaly score only (no base64 encoding).
    Returns score and the ELA PIL image for optional encoding later.
    """
    original = Image.open(image_path).convert("RGB")

    # Save compressed JPEG in memory
    buffer = BytesIO()
    original.save(buffer, format="JPEG", quality=resave_quality)
    buffer.seek(0)
    compressed = Image.open(buffer)

    # Difference
    ela_image = ImageChops.difference(original, compressed)

    # Apply percentile-based contrast stretch for better visibility
    ela_np = np.array(ela_image)
    ela_stretched = stretch_to_uint8(ela_np, ELA_PCTL_LOW, ELA_PCTL_HIGH)
    ela_image = Image.fromarray(ela_stretched, mode='RGB')

    # Downscale for efficient transport
    ela_image = downscale_overlay(ela_image, ELA_MAX_WIDTH)

    # Compute anomaly score (use original ela_np before stretching)
    score = ela_np.std()

    return score, ela_image


def encode_ela_to_base64(ela_image):
    """
    Encode an ELA PIL image to base64 PNG string.
    """
    buffer = BytesIO()
    ela_image.save(buffer, format="PNG", compress_level=ELA_PNG_LEVEL, optimize=True)
    ela_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    ela_base64 = f"data:image/png;base64,{ela_base64}"
    return ela_base64


def compute_ela_base64(image_path, resave_quality=90):
    """
    Compute ELA image and anomaly score with base64 encoding.
    Returns score and base64-encoded ELA image.

    This is a convenience wrapper that combines score calculation and encoding.
    For better performance when processing many frames, use compute_ela_score()
    and encode_ela_to_base64() separately.
    """
    score, ela_image = compute_ela_score(image_path, resave_quality)
    ela_base64 = encode_ela_to_base64(ela_image)
    return score, ela_base64


def run_ela(input_path, top_percent=10):
    """
    Run ELA on a single image or folder.
    Returns top frames as JSON with Base64-encoded ELA images.

    PERFORMANCE OPTIMIZATION:
    - Computes scores for ALL frames
    - Sorts and selects top N frames
    - Only encodes top N frames to base64 (not all frames)
    """
    # Collect frames
    if os.path.isdir(input_path):
        frame_files = [f for f in os.listdir(input_path)
                       if f.lower().endswith((".jpg", ".png"))]
        if not frame_files:
            raise ValueError("No frames found in folder")
        frame_paths = [os.path.join(input_path, f) for f in frame_files]

    elif os.path.isfile(input_path) and input_path.lower().endswith((".jpg", ".png")):
        frame_paths = [input_path]

    else:
        raise FileNotFoundError(f"Invalid path: {input_path}")

    # Single frame case - compute score and encode immediately
    if len(frame_paths) == 1:
        score, ela_base64 = compute_ela_base64(frame_paths[0])
        return {
            "mode": "single_frame",
            "frame": os.path.basename(frame_paths[0]),
            "score": float(score),
            "ela_image_base64": ela_base64
        }

    # Multi-frame case - optimize by only encoding top frames
    # Step 1: Compute scores for ALL frames (without base64 encoding)
    results = []
    for path in frame_paths:
        score, ela_image = compute_ela_score(path)
        results.append((os.path.basename(path), path, score, ela_image))

    # Step 2: Normalize scores (z-scores, no zero-clipping - negatives are meaningful)
    scores_only = [s for _, _, s, _ in results]
    mean_score = np.mean(scores_only)
    std_score = np.std(scores_only) + 1e-6
    normalized_results = [
        (fname, fpath, (score - mean_score) / std_score, ela_img)
        for fname, fpath, score, ela_img in results
    ]

    # Step 3: Sort and pick top frames
    normalized_results.sort(key=lambda x: x[2], reverse=True)  # Sort by normalized score
    top_count = min(max(1, int(len(normalized_results) * top_percent / 100)), 32)
    top_frames_data = normalized_results[:top_count]

    # Step 4: Only NOW encode the top frames to base64
    top_frames = []
    for fname, fpath, norm_score, ela_img in top_frames_data:
        ela_base64 = encode_ela_to_base64(ela_img)
        top_frames.append({
            "frame": fname,
            "score": float(norm_score),
            "ela_image_base64": ela_base64
        })

    # Return JSON-ready dict
    return {
        "mode": "multi_frame",
        "top_percent": top_percent,
        "top_frames": top_frames
    }
