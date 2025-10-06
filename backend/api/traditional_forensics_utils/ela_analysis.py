import os
from PIL import Image, ImageChops, ImageEnhance
import numpy as np
import csv

def compute_ela(image_path, output_folder="ela_frames", resave_quality=90):
    """
    Compute the ELA image and anomaly score.
    Saves the ELA image and returns anomaly score.
    """
    os.makedirs(output_folder, exist_ok=True)

    original = Image.open(image_path).convert("RGB")

    # Save compressed JPEG
    temp_path = "temp_ela.jpg"
    original.save(temp_path, quality=resave_quality)
    compressed = Image.open(temp_path)

    # Difference
    ela_image = ImageChops.difference(original, compressed)

    # Scale brightness
    extrema = ela_image.getextrema()
    max_diff = max([ex[1] for ex in extrema])
    scale = 255.0 / max_diff if max_diff != 0 else 1
    ela_image = ImageEnhance.Brightness(ela_image).enhance(scale)

    # Save ELA image
    ela_filename = os.path.basename(image_path).replace(".", "_ela.")
    ela_output_path = os.path.join(output_folder, ela_filename)
    ela_image.save(ela_output_path)

    # Score
    ela_np = np.array(ela_image)
    anomaly_score = ela_np.std()

    return anomaly_score


def run_ela(input_path, output_dir="reports", top_percent=10):
    """
    Run ELA on a single image OR a folder of frames.
    Saves reports to CSV and returns results as JSON-friendly dict.
    """
    os.makedirs(output_dir, exist_ok=True)

    # Case 1: Folder
    if os.path.isdir(input_path):
        frame_files = [f for f in os.listdir(input_path) if f.lower().endswith((".jpg", ".png"))]
        frame_files = [os.path.join(input_path, f) for f in frame_files]
        if not frame_files:
            raise ValueError("No frames found in folder")

    # Case 2: Single image
    elif os.path.isfile(input_path) and input_path.lower().endswith((".jpg", ".png")):
        frame_files = [input_path]

    else:
        raise FileNotFoundError(f"Invalid path: {input_path}")

    results = []
    for frame in frame_files:
        score = compute_ela(frame)
        results.append((os.path.basename(frame), score))

    # --- Single frame case ---
    if len(results) == 1:
        frame, score = results[0]
        return {
            "mode": "single_frame",
            "frame": frame,
            "score": score
        }

    # --- Multi-frame case ---
    scores_only = [s for _, s in results]
    mean_score = np.mean(scores_only)
    std_score = np.std(scores_only) + 1e-6
    normalized_results = [(f, max((s - mean_score) / std_score, 0)) for f, s in results]

    results_sorted = sorted(normalized_results, key=lambda x: x[1], reverse=True)

    # Save all frames CSV
    all_csv_path = os.path.join(output_dir, "ela_all_frames.csv")
    with open(all_csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Frame", "AnomalyScore"])
        writer.writerows(results_sorted)

    # Top X% frames
    top_count = max(1, int(len(results_sorted) * top_percent / 100))
    top_frames = results_sorted[:top_count]

    top_csv_path = os.path.join(output_dir, "ela_top_frames.csv")
    with open(top_csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Frame", "AnomalyScore"])
        writer.writerows(top_frames)

    return {
        "mode": "multi_frame",
        "all_frames_count": len(results_sorted),
        "top_frames": top_frames,
        "csv_all": all_csv_path,
        "csv_top": top_csv_path
    }
