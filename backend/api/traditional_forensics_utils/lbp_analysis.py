import os
from PIL import Image
import numpy as np
import csv
from skimage.feature import local_binary_pattern

def compute_lbp(frame_path, output_folder="lbp_frames", P=8, R=1):
    """
    Compute Local Binary Pattern (LBP) image and anomaly score.
    Saves LBP image and returns anomaly score.
    """
    os.makedirs(output_folder, exist_ok=True)
    
    img = Image.open(frame_path).convert("L")
    img_np = np.array(img, dtype=np.uint8)
    
    # Compute LBP
    lbp = local_binary_pattern(img_np, P=P, R=R, method="uniform")
    
    # Save LBP image (normalized to 0-255)
    lbp_img = Image.fromarray(np.uint8((lbp / lbp.max()) * 255))
    lbp_filename = os.path.basename(frame_path).replace(".", "_lbp.")
    lbp_output_path = os.path.join(output_folder, lbp_filename)
    lbp_img.save(os.path.join(output_folder, lbp_filename))
    
    # Anomaly score = std deviation of LBP histogram
    n_bins = int(lbp.max() + 1)
    hist, _ = np.histogram(lbp.ravel(), bins=n_bins, range=(0, n_bins), density=True)
    score = np.std(hist)
    return score, lbp_output_path


def run_lbp_analysis(input_path, reports_folder="reports", top_percent=10):
    """
    Run LBP analysis on:
    - A folder of frames → saves CSVs with all and top anomalies into reports/
    - A single frame → returns confidence only
    """

    os.makedirs(reports_folder, exist_ok=True)

    # Case 1: Folder
    if os.path.isdir(input_path):
        frame_files = [f for f in os.listdir(input_path) if f.lower().endswith((".jpg", ".png"))]
        if not frame_files:
            return {"error": f"No frames found in folder: {input_path}"}

        frame_paths = [os.path.join(input_path, f) for f in frame_files]

    # Case 2: Single image file
    elif os.path.isfile(input_path) and input_path.lower().endswith((".jpg", ".png")):
        frame_paths = [input_path]

    else:
        return {"error": f"Invalid input path: {input_path}"}

    results = []
    for path in frame_paths:
        score, lbp_path = compute_lbp(path)  # Saves LBP image
        results.append((os.path.basename(path), score, lbp_path))

    # If only one frame → just return scaled confidence
    if len(results) == 1:
        _, score, lbp_path = results[0]
        confidence = np.tanh(score * 10)  # heuristic scaling
        return {"confidence": float(confidence), "lbp_image": lbp_path}

    # Z-score normalization
    scores_only = [s for _, s in results]
    mean_score = np.mean(scores_only)
    std_score = np.std(scores_only) + 1e-6
    normalized_results = [(f, max((s - mean_score) / std_score, 0)) for f, s in results]

    # Save all frames CSV
    results_sorted = sorted(normalized_results, key=lambda x: x[1], reverse=True)
    all_csv = os.path.join(reports_folder, "lbp_all_frames.csv")
    with open(all_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Frame", "AnomalyScore"])
        writer.writerows(results_sorted)

    # Top X% frames
    top_count = max(1, int(len(results_sorted) * top_percent / 100))
    top_frames = results_sorted[:top_count]

    # Percent relative to average
    avg_score = np.mean([s for _, s in results_sorted])
    top_frames_percent = [(f, s, round((s / avg_score) * 100 if avg_score != 0 else 0, 2)) for f, s in top_frames]

    top_csv = os.path.join(reports_folder, "lbp_top_frames.csv")
    with open(top_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Frame", "AnomalyScore", "PercentComparedToAverage"])
        writer.writerows(top_frames_percent)

    return {
        "message": f"✅ LBP analysis complete. Reports saved in {reports_folder}/",
        "csv_all": all_csv,
        "csv_top": top_csv,
    }
