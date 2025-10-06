# cmfd_analysis.py (optimized)
import os
import cv2
import numpy as np
import csv
from scipy.fftpack import dct
import random

def extract_blocks(img_gray, block_size=32, stride=16):
    """Split image into overlapping blocks with given stride."""
    h, w = img_gray.shape
    blocks = []
    positions = []
    for y in range(0, h - block_size + 1, stride):
        for x in range(0, w - block_size + 1, stride):
            block = img_gray[y:y+block_size, x:x+block_size]
            blocks.append(block)
            positions.append((x, y))
    return blocks, positions

def compute_dct_features(blocks):
    """Compute reduced DCT features for each block."""
    features = []
    for block in blocks:
        block_dct = dct(dct(block.T, norm='ortho').T, norm='ortho')
        features.append(block_dct[:4, :4].flatten())  # smaller feature vector
    return np.array(features)

def detect_copymove(frame_path, output_folder="cmfd_frames", block_size=32, stride=16, threshold=0.1):
    """
    Detect copy-move forgery in a frame and return anomaly score.
    """
    os.makedirs(output_folder, exist_ok=True)
    img = cv2.imread(frame_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    blocks, positions = extract_blocks(gray, block_size, stride)
    features = compute_dct_features(blocks)
    
    # Normalize features
    features = features / (np.linalg.norm(features, axis=1, keepdims=True) + 1e-6)
    
    dup_mask = np.zeros_like(gray, dtype=np.uint8)
    n_blocks = len(blocks)
    
    # Naive all-pairs comparison (still faster due to fewer blocks and smaller features)
    for i in range(n_blocks):
        for j in range(i+1, n_blocks):
            xi, yi = positions[i]
            xj, yj = positions[j]
            if abs(xi - xj) < block_size and abs(yi - yj) < block_size:
                continue
            sim = np.dot(features[i], features[j])
            if sim > 1 - threshold:
                dup_mask[yi:yi+block_size, xi:xi+block_size] = 255
                dup_mask[yj:yj+block_size, xj:xj+block_size] = 255

    score = np.sum(dup_mask > 0) / dup_mask.size
    
    # Save visual output
    overlay = img.copy()
    overlay[dup_mask > 0] = [0, 0, 255]  # mark in red
    out_name = os.path.basename(frame_path).replace(".", "_cmfd.")
    cv2.imwrite(os.path.join(output_folder, out_name), overlay)
    
    return score

def run_cmfd_analysis(input_path, output_csv_all="reports/cmfd_all_frames.csv",
                      output_csv_top="reports/cmfd_top_frames.csv",
                      top_percent=10, sample_ratio=0.2):
    """
    Run CMFD on:
    - A folder of frames (random subset to speed up analysis)
    - A single frame (direct analysis)

    Returns a JSON-like dict for Flask routes.
    """

    # Case 1: Folder
    if os.path.isdir(input_path):
        frame_files = [f for f in os.listdir(input_path) if f.lower().endswith((".jpg", ".png"))]
        if not frame_files:
            return {"error": f"No frames found in folder: {input_path}"}

        n_sample = max(1, int(len(frame_files) * sample_ratio))
        sampled_frames = random.sample(frame_files, n_sample)
        frame_paths = [os.path.join(input_path, f) for f in sampled_frames]

    # Case 2: Single image
    elif os.path.isfile(input_path) and input_path.lower().endswith((".jpg", ".png")):
        frame_paths = [input_path]

    else:
        return {"error": f"Invalid input path: {input_path}"}

    results = []
    for path in frame_paths:
        score = detect_copymove(path)
        results.append((os.path.basename(path), score))

    # Case: single frame → no CSVs, return scaled confidence
    if len(results) == 1:
        _, score = results[0]
        confidence = float(np.tanh(score * 10))
        return {"confidence": confidence}

    # Z-score normalization for multiple frames
    scores_only = [s for _, s in results]
    mean_score = np.mean(scores_only)
    std_score = np.std(scores_only) + 1e-6
    normalized_results = [(f, max((s - mean_score) / std_score, 0)) for f, s in results]

    # Save all results
    results_sorted = sorted(normalized_results, key=lambda x: x[1], reverse=True)
    os.makedirs("reports", exist_ok=True)
    with open(output_csv_all, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Frame", "AnomalyScore"])
        writer.writerows(results_sorted)

    # Top X% results
    top_count = max(1, int(len(results_sorted) * top_percent / 100))
    top_frames = results_sorted[:top_count]
    avg_score = np.mean([s for _, s in results_sorted])
    top_frames_percent = [
        (f, s, round((s / avg_score) * 100 if avg_score != 0 else 0, 2))
        for f, s in top_frames
    ]
    with open(output_csv_top, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Frame", "AnomalyScore", "PercentComparedToAverage"])
        writer.writerows(top_frames_percent)

    return {
        "all_frames_csv": output_csv_all,
        "top_frames_csv": output_csv_top,
        "top_percent": top_percent,
        "total_frames": len(results_sorted),
        "top_frames": [
            {"frame": f, "score": float(s), "percent_vs_avg": p}
            for f, s, p in top_frames_percent
        ]
    }
