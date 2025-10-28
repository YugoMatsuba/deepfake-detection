import os
from pathlib import Path
from io import BytesIO
from PIL import Image, ImageChops, ImageEnhance
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed

# Prevent thread oversubscription when multiprocessing
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

# Configuration constants
ELA_PCTL_LOW = 5
ELA_PCTL_HIGH = 95
ELA_MAX_WIDTH = 960
ELA_PNG_LEVEL = 9

# Multiprocessing config (env-configurable)
MAX_WORKERS = int(os.getenv("FORENSICS_WORKERS") or os.cpu_count() or 4)


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


def _save_overlay(image, frame_filename, output_dir):
    """Save overlay image to disk and return saved path."""
    if output_dir:
        # Parse frame number from filename
        stem = Path(frame_filename).stem
        digits = "".join(ch for ch in stem if ch.isdigit())
        if digits:
            frame_num = int(digits)  # Convert to int to strip leading zeros
            out_path = Path(output_dir) / f"frame_{frame_num}.jpg"
            image.save(out_path, "JPEG", quality=90)
            return str(out_path)
    return None


def _compute_ela_worker(path):
    """
    Worker function for multiprocessing.

    Args:
        path: Absolute path to frame image

    Returns:
        Tuple of (basename, path, score, ela_image) suitable for multiprocessing
    """
    score, ela_image = compute_ela_score(path)
    return (os.path.basename(path), path, score, ela_image)


def run_ela(input_path, top_percent=10, output_dir=None, analysis_id=None):
    """
    Run ELA on a single image or folder.
    Saves overlay images to output_dir if provided.
    Returns top frames as JSON (no base64, overlays saved to disk).

    PERFORMANCE OPTIMIZATION:
    - Computes scores for ALL frames
    - Sorts and selects top N frames
    - Only saves overlays for top N frames (not all frames)
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

    # Multi-frame case - optimize by only saving overlays for top frames
    # Step 1: Compute scores for ALL frames (without saving overlays yet)
    total_frames = len(frame_paths)
    print(f"[ELA Analysis] Processing {total_frames} frames with {MAX_WORKERS} workers...")

    # Use multiprocessing for multi-frame case
    if len(frame_paths) > 1:
        results = []
        completed = 0
        milestones = {total_frames // 4, total_frames // 2, (3 * total_frames) // 4}

        with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Submit all tasks
            futures = {executor.submit(_compute_ela_worker, path): path
                      for path in frame_paths}

            # Collect results as they complete
            for future in as_completed(futures):
                results.append(future.result())
                completed += 1

                # Progress tracking
                if completed % 10 == 0 or completed in milestones:
                    progress_pct = (completed / total_frames) * 100
                    print(f"[ELA Analysis] Progress: {completed}/{total_frames} frames ({progress_pct:.1f}%)")
    else:
        # Single frame: no multiprocessing overhead
        results = [_compute_ela_worker(frame_paths[0])]

    print(f"[ELA Analysis] ✓ Completed processing {total_frames} frames")

    # Step 2: Normalize scores (z-scores, no zero-clipping - negatives are meaningful)
    # Keep both raw scores and z-scores for persistence
    scores_only = [s for _, _, s, _ in results]
    mean_score = np.mean(scores_only)
    std_score = np.std(scores_only) + 1e-6
    normalized_results = [
        (fname, fpath, score, (score - mean_score) / std_score, ela_img)
        for fname, fpath, score, ela_img in results
    ]

    # Step 3: Sort and pick top frames
    normalized_results.sort(key=lambda x: x[3], reverse=True)  # Sort by z-score (index 3)
    top_count = min(max(1, int(len(normalized_results) * top_percent / 100)), 32)
    top_frames_data = normalized_results[:top_count]

    # Step 4: Save overlays for top frames and build response
    top_frames = []
    for fname, fpath, raw_score, z_score, ela_img in top_frames_data:
        # Save overlay to disk
        _save_overlay(ela_img, fname, output_dir)
        top_frames.append({
            "frame": fname,
            "raw_score": float(raw_score),  # NEW: Store raw score for z-score recalculation
            "score": float(z_score)
        })

    # Return JSON-ready dict
    return {
        "mode": "multi_frame",
        "top_percent": top_percent,
        "top_frames": top_frames
    }
