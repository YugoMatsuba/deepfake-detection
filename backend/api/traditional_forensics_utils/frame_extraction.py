import cv2
import os

def extract_frames(video_path: str, output_base: str = "frames") -> list[str]:
    """
    Extract frames from a single video based on FPS and save in output folder.

    Args:
        video_path (str): Path to input video
        output_base (str): Base folder to save frames

    Returns:
        list[str]: List of saved frame file paths
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video not found: {video_path}")

    video_name = os.path.splitext(os.path.basename(video_path))[0]
    output_folder = os.path.join(output_base, video_name)
    os.makedirs(output_folder, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 24:
        frames_per_sec = 4
    elif fps < 60:
        frames_per_sec = 6
    else:
        frames_per_sec = 10

    frame_interval = max(int(fps / frames_per_sec), 1)

    count = 0
    frame_no = 0
    saved_frames = []

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        if count % frame_interval == 0:
            frame_filename = f"{video_name}_frame{frame_no:03d}.jpg"
            path = os.path.join(output_folder, frame_filename)
            cv2.imwrite(path, frame)
            saved_frames.append(path)
            frame_no += 1
        count += 1

    cap.release()
    return saved_frames
