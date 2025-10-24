import os
from pathlib import Path
from io import BytesIO
from PIL import Image, ImageChops, ImageEnhance
import numpy as np

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

    # Scale brightness
    extrema = ela_image.getextrema()
    max_diff = max([ex[1] for ex in extrema])
    scale = 255.0 / max_diff if max_diff != 0 else 1
    ela_image = ImageEnhance.Brightness(ela_image).enhance(scale)

    # Compute anomaly score
    ela_np = np.array(ela_image)
    score = ela_np.std()

    return score, ela_image


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


def run_ela(input_path, top_percent=10, output_dir=None, analysis_id=None):
    """
    Run ELA on a single image or folder.
    Saves overlay images to output_dir if provided.
    Returns top frames as JSON (no base64, overlays saved to disk).

    PERFORMANCE OPTIMIZATION:
    - Computes scores for ALL frames
    - Sorts and selects top N frames
    - Only saves top N frames to disk
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

    # Single frame case - compute score and save overlay
    if len(frame_paths) == 1:
        score, ela_image = compute_ela_score(frame_paths[0])
        filename = os.path.basename(frame_paths[0])
        # Save overlay to disk
        _save_overlay(ela_image, filename, output_dir)
        return {
            "mode": "single_frame",
            "frame": filename,
            "score": float(score)
        }

    # Multi-frame case - optimize by only saving top frames
    # Step 1: Compute scores for ALL frames
    results = []
    for path in frame_paths:
        score, ela_image = compute_ela_score(path)
        results.append((os.path.basename(path), path, score, ela_image))

    # Step 2: Normalize scores
    scores_only = [s for _, _, s, _ in results]
    mean_score = np.mean(scores_only)
    std_score = np.std(scores_only) + 1e-6
    normalized_results = [
        (fname, fpath, max((score - mean_score) / std_score, 0), ela_img)
        for fname, fpath, score, ela_img in results
    ]

    # Step 3: Sort and pick top frames
    normalized_results.sort(key=lambda x: x[2], reverse=True)  # Sort by normalized score
    top_count = min(max(1, int(len(normalized_results) * top_percent / 100)), 32)
    top_frames_data = normalized_results[:top_count]

    # Step 4: Save overlays for top frames only
    top_frames = []
    for fname, fpath, norm_score, ela_img in top_frames_data:
        # Save overlay to disk
        _save_overlay(ela_img, fname, output_dir)
        top_frames.append({
            "frame": fname,
            "score": float(norm_score)
        })

    # Return JSON-ready dict
    return {
        "mode": "multi_frame",
        "top_percent": top_percent,
        "top_frames": top_frames
    }
