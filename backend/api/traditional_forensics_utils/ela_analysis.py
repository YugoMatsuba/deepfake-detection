import os
import base64
from io import BytesIO
from PIL import Image, ImageChops, ImageEnhance
import numpy as np

def compute_ela_base64(image_path, resave_quality=90):
    """
    Compute ELA image and anomaly score.
    Returns PIL ELA image and anomaly score.
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

    # Convert to Base64 with MIME prefix
    buffer2 = BytesIO()
    ela_image.save(buffer2, format="JPEG", quality=85)
    ela_base64 = base64.b64encode(buffer2.getvalue()).decode("utf-8")
    ela_base64 = f"data:image/jpeg;base64,{ela_base64}"

    return score, ela_base64


def run_ela(input_path, top_percent=10):
    """
    Run ELA on a single image or folder.
    Returns top frames as JSON with Base64-encoded ELA images.
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

    # Compute ELA scores
    results = []
    for path in frame_paths:
        score, ela_base64 = compute_ela_base64(path)
        results.append((os.path.basename(path), score, ela_base64))

    # Single frame case
    if len(results) == 1:
        frame, score, ela_base64 = results[0]
        return {
            "mode": "single_frame",
            "frame": frame,
            "score": float(score),
            "ela_image_base64": ela_base64
        }

    # Multi-frame case
    scores_only = [s for _, s, _ in results]
    mean_score = np.mean(scores_only)
    std_score = np.std(scores_only) + 1e-6
    normalized_results = [(f, max((s - mean_score) / std_score, 0), b64)
                          for f, s, b64 in results]

    # Sort and pick top frames
    normalized_results.sort(key=lambda x: x[1], reverse=True)
    top_count = max(1, int(len(normalized_results) * top_percent / 100))
    top_frames = normalized_results[:top_count]

    # Return JSON-ready dict
    return {
        "mode": "multi_frame",
        "top_percent": top_percent,
        "top_frames": [
            {
                "frame": f,
                "score": float(s),
                "ela_image_base64": b64
            }
            for f, s, b64 in top_frames
        ]
    }
