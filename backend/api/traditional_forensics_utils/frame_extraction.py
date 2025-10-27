import cv2
import os


def extract_single_frame(video_path: str, frame_number: int, output_path: str) -> str:
    """
    Extract a specific frame by index from video and save to output_path.

    Args:
        video_path: Path to input video
        frame_number: 0-indexed frame number to extract
        output_path: Full path where frame should be saved (e.g., /tmp/frame.jpg)

    Returns:
        str: Path to saved frame file

    Raises:
        FileNotFoundError: If video doesn't exist
        ValueError: If frame_number is out of range
        RuntimeError: If video cannot be opened
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video not found: {video_path}")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open video: {video_path}")

    try:
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if frame_number < 0 or frame_number >= total_frames:
            raise ValueError(
                f"Frame number {frame_number} out of range (video has {total_frames} frames)"
            )

        # Seek to specific frame
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = cap.read()

        if not ret:
            raise RuntimeError(f"Failed to read frame {frame_number} from video")

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Save frame as PNG (lossless)
        if output_path.lower().endswith('.png'):
            cv2.imwrite(output_path, frame, [cv2.IMWRITE_PNG_COMPRESSION, 3])
        else:
            # Default to PNG if no specific extension
            cv2.imwrite(output_path, frame)
        return output_path

    finally:
        cap.release()


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
            frame_filename = f"{video_name}_frame{count}.png"
            path = os.path.join(output_folder, frame_filename)
            cv2.imwrite(path, frame, [cv2.IMWRITE_PNG_COMPRESSION, 3])
            saved_frames.append(path)
            frame_no += 1
        count += 1

    cap.release()
    return saved_frames
