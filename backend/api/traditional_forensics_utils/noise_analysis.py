import os
from pathlib import Path
from PIL import Image
import numpy as np
from scipy.ndimage import gaussian_filter, zoom
import cv2
from concurrent.futures import ProcessPoolExecutor, as_completed

# Prevent thread oversubscription when multiprocessing
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

# Configuration constants (Pass 1)
NOISE_PCTL_LOW = 1
NOISE_PCTL_HIGH = 99
NOISE_MAX_WIDTH = 960
NOISE_PNG_LEVEL = 3  # Fast compression (3 = good balance, 9 = max but very slow)

# Configuration constants (Pass 2 - blockwise scoring)
NOISE_BLOCK_SIZE = 8  # Window size for variance computation
NOISE_BLOCK_STRIDE = 4  # Stride for sliding window (4 = 50% overlap, 2 = 75% overlap)
NOISE_TOPK_PERCENT = 10
NOISE_EDGE_MASK_PERCENTILE = 70
NOISE_TEMP_NMS_WINDOW = 3
NOISE_ZMAP_PCTL_LOW = 5
NOISE_ZMAP_PCTL_HIGH = 95

# Multiprocessing config (env-configurable)
MAX_WORKERS = int(os.getenv("FORENSICS_WORKERS") or os.cpu_count() or 4)


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
    Compute blockwise noise inconsistency score and z-map overlay.

    Pass 2 algorithm:
    1. Compute residual (Gaussian smoothing)
    2. Build edge mask to exclude high-texture regions
    3. Tile into blocks, compute std per block (excluding edges)
    4. Build z-map: standardize block stds within frame
    5. Frame score = mean of top-k blocks
    6. Overlay = upscaled z-map (percentile stretched)

    Returns:
        score: float (mean of top-k block z-scores)
        overlay_img: PIL Image (z-map visualization)
    """
    # Load frame and convert to grayscale
    img = Image.open(frame_path).convert("L")
    img_np = np.array(img, dtype=np.float32)

    # Smooth image using Gaussian filter
    smoothed = gaussian_filter(img_np, sigma=1.0)

    # Noise residual
    residual = img_np - smoothed

    # 1. Compute edge mask (Laplacian, threshold at percentile)
    img_u8 = np.array(img, dtype=np.uint8)
    laplacian = cv2.Laplacian(img_u8, cv2.CV_64F, ksize=3)
    edge_mag = np.abs(laplacian)
    edge_threshold = np.percentile(edge_mag, NOISE_EDGE_MASK_PERCENTILE)
    edge_mask = edge_mag < edge_threshold  # True = not an edge (include in stats)

    # 2. Sliding window with stride (for dense sampling, reduces blockiness)
    h, w = residual.shape
    bs = NOISE_BLOCK_SIZE
    stride = NOISE_BLOCK_STRIDE

    # Calculate grid dimensions based on stride
    n_rows = (h - bs) // stride + 1
    n_cols = (w - bs) // stride + 1

    # 3. Compute per-window std using sliding window (excluding edge pixels, with fallback)
    block_stds = np.zeros((n_rows, n_cols))
    for i in range(n_rows):
        for j in range(n_cols):
            # Extract window at strided position
            row_start = i * stride
            col_start = j * stride
            window_residual = residual[row_start:row_start + bs, col_start:col_start + bs]
            window_edge_mask = edge_mask[row_start:row_start + bs, col_start:col_start + bs]

            # Use non-edge pixels; fallback to all if none remain
            masked_pixels = window_residual[window_edge_mask]
            if len(masked_pixels) > 0:
                block_stds[i, j] = np.std(masked_pixels)
            else:
                block_stds[i, j] = np.std(window_residual)

    # 4. Build z-map within frame
    mean_std = np.mean(block_stds)
    std_std = np.std(block_stds) + 1e-6
    z_map = (block_stds - mean_std) / std_std

    # 5. Frame score = mean of top-k blocks
    k = max(1, int(np.ceil(n_rows * n_cols * NOISE_TOPK_PERCENT / 100.0)))
    top_k_values = np.sort(z_map.ravel())[-k:]
    score = float(np.mean(top_k_values))

    # 6. Generate z-map overlay
    # Upsample z-map to approximate original image size using bilinear interpolation
    # Calculate scale factor based on stride
    scale_factor = stride
    z_map_upsampled = zoom(z_map, scale_factor, order=1)  # order=1 = bilinear

    # Crop/pad to match original image dimensions
    target_h, target_w = h, w
    current_h, current_w = z_map_upsampled.shape

    # Crop if larger
    z_map_upsampled = z_map_upsampled[:min(current_h, target_h), :min(current_w, target_w)]

    # Pad if smaller (shouldn't happen with stride=2, but safety check)
    if z_map_upsampled.shape[0] < target_h or z_map_upsampled.shape[1] < target_w:
        padded = np.zeros((target_h, target_w))
        padded[:z_map_upsampled.shape[0], :z_map_upsampled.shape[1]] = z_map_upsampled
        z_map_upsampled = padded

    # Apply percentile stretch and convert to uint8
    z_map_u8 = stretch_to_uint8(z_map_upsampled, NOISE_ZMAP_PCTL_LOW, NOISE_ZMAP_PCTL_HIGH)

    # Light blur to reduce visual noise and smooth heatmap
    z_map_u8 = cv2.GaussianBlur(z_map_u8, (3, 3), 1.0)

    overlay_img = Image.fromarray(z_map_u8, mode='L')

    # Downscale for efficient transport
    overlay_img = downscale_overlay(overlay_img, NOISE_MAX_WIDTH)

    return score, overlay_img


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


def _compute_noise_worker(path):
    """
    Worker function for multiprocessing.

    Args:
        path: Absolute path to frame image

    Returns:
        Tuple of (basename, score, overlay_img) suitable for multiprocessing
    """
    score, overlay_img = compute_noise(path)
    return (os.path.basename(path), score, overlay_img)


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
    total_frames = len(frame_paths)
    print(f"[Noise Analysis] Processing {total_frames} frames with {MAX_WORKERS} workers...")

    # Use multiprocessing for multi-frame case
    if len(frame_paths) > 1:
        results = []
        completed = 0
        milestones = {total_frames // 4, total_frames // 2, (3 * total_frames) // 4}

        with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Submit all tasks
            futures = {executor.submit(_compute_noise_worker, path): path
                      for path in frame_paths}

            # Collect results as they complete
            for future in as_completed(futures):
                results.append(future.result())
                completed += 1

                # Progress tracking
                if completed % 10 == 0 or completed in milestones:
                    progress_pct = (completed / total_frames) * 100
                    print(f"[Noise Analysis] Progress: {completed}/{total_frames} frames ({progress_pct:.1f}%)")
    else:
        # Single frame: no multiprocessing overhead
        results = [_compute_noise_worker(frame_paths[0])]

    print(f"[Noise Analysis] ✓ Completed processing {total_frames} frames")

    # Single frame case
    if len(results) == 1:
        filename, score, residual_img = results[0]
        # Save overlay to disk
        _save_overlay(residual_img, filename, output_dir)
        # Return raw score (NO tanh transformation)
        return {
            "mode": "single_frame",
            "frame": filename,
            "confidence": float(score)
        }

    # Multi-frame case
    scores_only = [s for _, s, _ in results]
    mean_score = np.mean(scores_only)
    std_score = np.std(scores_only) + 1e-6

    # Compute z-scores (no zero-clipping - negatives are meaningful)
    # Keep both raw scores and z-scores for persistence
    normalized = [(f, s, (s - mean_score) / std_score, img, idx)
                  for idx, (f, s, img) in enumerate(results)]
    sorted_results = sorted(normalized, key=lambda x: x[2], reverse=True)

    # Cap at 32 frames to limit JSON payload size
    top_count = min(max(1, int(len(sorted_results) * top_percent / 100)), 32)

    # Temporal NMS: select frames with temporal diversity
    selected_frames = []
    selected_indices = []

    for fname, raw_score, z_score, img, idx in sorted_results:
        # Check if this frame is too close to any already selected
        too_close = any(abs(idx - sel_idx) <= NOISE_TEMP_NMS_WINDOW for sel_idx in selected_indices)

        if not too_close:
            selected_frames.append((fname, raw_score, z_score, img))
            selected_indices.append(idx)

        if len(selected_frames) >= top_count:
            break

    top_frames = selected_frames

    # Save overlays and build response
    frame_list = []
    for f, raw_s, z_s, img in top_frames:
        # Save overlay to disk
        _save_overlay(img, f, output_dir)
        frame_list.append({
            "frame": f,
            "raw_score": float(raw_s),  # NEW: Store raw score for z-score recalculation
            "score": float(z_s)
        })

    # Return top frames JSON
    return {
        "mode": "multi_frame",
        "top_frames": frame_list
    }
