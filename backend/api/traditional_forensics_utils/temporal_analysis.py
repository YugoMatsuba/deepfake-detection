import cv2
import numpy as np
import os
import csv

def run_temporal_analysis(video_path, sample_rate=10, output_dir="reports"):
    """
    Run temporal forensics analysis on a video.
    Saves issues to a CSV inside the reports folder.
    """
    os.makedirs(output_dir, exist_ok=True)

    # Output CSV path inside reports/
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    output_csv = os.path.join(output_dir, f"temporal_{base_name}_report.csv")

    # Load Haar cascades
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")

    if face_cascade.empty() or eye_cascade.empty():
        raise RuntimeError("Haar cascades not found. Check your OpenCV installation.")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise FileNotFoundError(f"Could not open video: {video_path}")

    frame_idx = 0
    prev_face_center = None
    issues = []
    total_frames = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_idx += 1

        if frame_idx % sample_rate != 0:
            continue  # skip frames for speed

        total_frames += 1
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # --- Face detection ---
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)
        for (x, y, w, h) in faces:
            face_center = (x + w // 2, y + h // 2)

            # --- Jitter check ---
            if prev_face_center is not None:
                dist = np.linalg.norm(np.array(face_center) - np.array(prev_face_center))
                if dist > 50:
                    issues.append((frame_idx, "Facial jitter"))

            prev_face_center = face_center

            roi_gray = gray[y:y + h, x:x + w]

            # --- Eye detection ---
            eyes = eye_cascade.detectMultiScale(roi_gray)
            if len(eyes) >= 2:
                ear_values = []
                for (ex, ey, ew, eh) in eyes[:2]:
                    aspect_ratio = eh / float(ew)
                    ear_values.append(aspect_ratio)

                avg_ear = np.mean(ear_values)
                if avg_ear < 0.15:
                    issues.append((frame_idx, "Irregular blinking"))

            # --- Head pose estimation (simplified) ---
            aspect_ratio = w / float(h)
            if aspect_ratio < 0.7 or aspect_ratio > 1.3:
                issues.append((frame_idx, "Unnatural head pose"))

    cap.release()

    # --- Save report in reports/ ---
    with open(output_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Frame", "Issue"])
        writer.writerows(issues)

    return {
        "mode": "video_analysis",
        "video_path": video_path,
        "total_frames_analyzed": total_frames,
        "issues_detected": len(issues),
        "issues": issues,
        "report_csv": output_csv
    }
