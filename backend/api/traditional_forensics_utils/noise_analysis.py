import os
from PIL import Image
import numpy as np
import csv
from scipy.ndimage import gaussian_filter


def compute_noise(frame_path, output_folder="noise_frames"):
    """
    Compute spatial noise residual and anomaly score.
    Saves the residual noise image.
    Returns raw anomaly score.
    """
    os.makedirs(output_folder, exist_ok=True)

    # Load frame and convert to grayscale
    img = Image.open(frame_path).convert("L")
    img_np = np.array(img, dtype=np.float32)

    # Smooth image using Gaussian filter
    smoothed = gaussian_filter(img_np, sigma=1.0)

    # Noise residual
    residual = img_np - smoothed

    # Save residual image
    residual_img = Image.fromarray(np.clip(residual + 128, 0, 255).astype(np.uint8))
    residual_name = os.path.basename(frame_path).replace(".", "_noise.")
    residual_path = os.path.join(output_folder, residual_name)
    residual_img.save(residual_path)

    # Anomaly score = standard deviation of residual
    score = np.std(residual)
    return score, residual_path


def run_noise_analysis(input_path,
                       reports_folder="reports",
                       output_csv_all="noise_all_frames.csv",
                       output_csv_top="noise_top_frames.csv",
                       top_percent=10):
    """
    Run noise analysis on:
    - A folder of frames (saves CSVs with all and top anomalies)
    - A single frame (returns confidence + residual path)

    Returns:
        dict with results (consistent format)
    """

    # Ensure reports folder exists
    os.makedirs(reports_folder, exist_ok=True)

    # Build full CSV paths inside reports/
    output_csv_all = os.path.join(reports_folder, output_csv_all)
    output_csv_top = os.path.join(reports_folder, output_csv_top)

    # Case 1: Folder
    if os.path.isdir(input_path):
        frame_files = [f for f in os.listdir(input_path) if f.lower().endswith((".jpg", ".png"))]
        if not frame_files:
            return {"error": f"No frames found in folder {input_path}"}
        frame_paths = [os.path.join(input_path, f) for f in frame_files]

    # Case 2: Single image
    elif os.path.isfile(input_path) and input_path.lower().endswith((".jpg", ".png")):
        frame_paths = [input_path]

    else:
        return {"error": f"Invalid input path {input_path}"}

    results = []
    for path in frame_paths:
        score, residual_path = compute_noise(path)  # Saves residual in noise_frames/
        results.append((os.path.basename(path), score, residual_path))

    # Single frame case → return confidence + residual
    if len(results) == 1:
        filename, score, residual_path = results[0]
        confidence = float(np.tanh(score * 10))  # heuristic scaling
        return {
            "frame": filename,
            "confidence": confidence,
            "residual": residual_path
        }

    # Multiple frames → return CSVs
    scores_only = [s for _, s, _ in results]
    mean_score = np.mean(scores_only)
    std_score = np.std(scores_only) + 1e-6
    normalized_results = [(f, max((s - mean_score) / std_score, 0), r)
                          for f, s, r in results]

    # Save all frames CSV
    results_sorted = sorted(normalized_results, key=lambda x: x[1], reverse=True)
    with open(output_csv_all, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Frame", "AnomalyScore", "ResidualPath"])
        writer.writerows(results_sorted)

    # Top X% frames
    top_count = max(1, int(len(results_sorted) * top_percent / 100))
    top_frames = results_sorted[:top_count]
    avg_score = np.mean([s for _, s, _ in results_sorted])
    top_frames_percent = [
        (f, s, round((s / avg_score) * 100 if avg_score != 0 else 0, 2), r)
        for f, s, r in top_frames
    ]

    # Save top frames CSV
    with open(output_csv_top, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Frame", "AnomalyScore", "PercentComparedToAverage", "ResidualPath"])
        writer.writerows(top_frames_percent)

    return {
        "csv_all": output_csv_all,
        "csv_top": output_csv_top,
        "top_frames": [
            {"frame": f, "score": float(s), "percent": float(p), "residual": r}
            for f, s, p, r in top_frames_percent
        ]
    }
