# video_io.py - DeepfakeBench-aligned video frame sampling and processing

"""
Video I/O module that replicates DeepfakeBench's exact preprocessing pipeline:

1. Uniform frame sampling via np.linspace (matches preprocess.py fixed_num_frames mode)
2. BGR→RGB conversion before any processing (per abstract_dataset.py)
3. Face alignment using largest face + 5-point landmarks + scale=1.3
4. Padding strategy: repeat last valid crop until exactly 32 frames
5. Output: uint8 RGB crops ready for transforms.py normalization

Reference DeepfakeBench files:
- preprocessing/preprocess.py: frame sampling logic (line 278)
- training/dataset/abstract_dataset.py: BGR->RGB conversion (line 313)
- training/dataset/face_utils.py: alignment template and scale factor
"""

from dataclasses import dataclass
from typing import List, Optional
import numpy as np
import cv2
import logging

from . import face_align_crop
from . import constants

logger = logging.getLogger(__name__)


@dataclass
class VideoMeta:
    """Video metadata extracted during processing."""
    path: str
    frame_count: int
    fps: float
    duration_sec: float
    width: int
    height: int


@dataclass
class FrameInfo:
    """Information about a processed frame."""
    index: int              # Original frame index in source video
    timestamp_sec: float    # Timestamp in seconds (index / fps)


@dataclass
class VideoBatch:
    """Batch of 32 face-aligned crops with metadata."""
    crops_rgb: List[np.ndarray]    # len == 32, each (256,256,3) uint8 RGB
    frames: List[FrameInfo]        # len == 32, padded entries repeat last valid
    meta: VideoMeta


def _sample_frame_indices(frame_count: int, num_frames: int = 32) -> np.ndarray:
    """
    Sample frame indices using DeepfakeBench's exact uniform sampling method.

    Based on preprocessing/preprocess.py line 278:
    frame_idxs = np.linspace(0, frame_count_org - 1, num_frames, endpoint=True, dtype=int)

    Args:
        frame_count: Total number of frames in video
        num_frames: Number of frames to sample (default 32)

    Returns:
        np.ndarray: Array of frame indices, shape (num_frames,)
    """
    if frame_count <= 0:
        return np.array([], dtype=int)

    # DeepfakeBench exact sampling: endpoint=True ensures last frame included
    indices = np.linspace(0, frame_count - 1, num=num_frames, endpoint=True, dtype=int)
    return indices


def load_video_32(
    video_path: str,
    detector,
    predictor,
    num_frames: int = constants.FRAME_NUM,
    required: bool = True
) -> VideoBatch:
    """
    Load and process a video into exactly 32 face-aligned RGB crops.

    Replicates DeepfakeBench preprocessing pipeline:
    1. Uniform frame sampling (np.linspace with endpoint=True)
    2. BGR→RGB conversion before processing
    3. Largest face detection + 5-point alignment (scale=1.3)
    4. Padding by repeating last valid crop

    Args:
        video_path: Path to input video file
        detector: dlib face detector instance
        predictor: dlib shape predictor instance (81-point)
        num_frames: Number of frames to extract (default 32)
        required: If True, raise on empty video or no faces found

    Returns:
        VideoBatch: Container with 32 RGB crops, frame info, and metadata

    Raises:
        ValueError: If video is empty/unreadable or no faces found (when required=True)
    """
    cap = cv2.VideoCapture(video_path)

    try:
        # Extract video metadata
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
        fps = float(cap.get(cv2.CAP_PROP_FPS)) or 0.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 0
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 0
        duration_sec = (frame_count / fps) if (frame_count and fps) else 0.0

        meta = VideoMeta(
            path=video_path,
            frame_count=frame_count,
            fps=fps,
            duration_sec=duration_sec,
            width=width,
            height=height
        )

        # Handle empty/unreadable video
        if frame_count <= 0:
            if required:
                raise ValueError("empty or unreadable video")
            logger.warning(f"Empty video: {video_path}")
            return VideoBatch(crops_rgb=[], frames=[], meta=meta)

        # Sample frame indices using DeepfakeBench method
        frame_indices = _sample_frame_indices(frame_count, num_frames)
        logger.info(f"Sampling {len(frame_indices)} frames from {frame_count} total frames")

        crops_rgb = []
        frame_infos = []

        # Process each sampled frame
        for idx in frame_indices:
            # Seek to specific frame
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
            success, bgr_frame = cap.read()

            if not success or bgr_frame is None:
                logger.warning(f"Failed to read frame {idx}")
                continue

            # Convert BGR→RGB before processing (per DeepfakeBench abstract_dataset.py)
            rgb_frame = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)

            # Align and crop face using existing function
            aligned_crop = face_align_crop.align_and_crop_rgb(
                rgb_frame, detector, predictor,
                outsize=constants.ALIGN_OUTPUT_SIZE,
                scale=constants.ALIGN_SCALE
            )

            if aligned_crop is None:
                logger.debug(f"No face detected in frame {idx}")
                continue

            # Compute timestamp
            timestamp = (idx / fps) if fps > 0 else 0.0

            crops_rgb.append(aligned_crop)
            frame_infos.append(FrameInfo(index=int(idx), timestamp_sec=float(timestamp)))

        # Handle case where no faces were found
        if len(crops_rgb) == 0:
            if required:
                raise ValueError("no faces found in any of the sampled frames")
            logger.warning(f"No faces found in video: {video_path}")
            return VideoBatch(crops_rgb=[], frames=[], meta=meta)

        # Track valid frames before padding
        valid_frames = len(crops_rgb)

        # Pad to exactly num_frames by repeating last valid crop
        while len(crops_rgb) < num_frames:
            crops_rgb.append(crops_rgb[-1].copy())
            # Create copy of FrameInfo to avoid aliasing
            frame_infos.append(FrameInfo(
                index=frame_infos[-1].index,
                timestamp_sec=frame_infos[-1].timestamp_sec
            ))

        padded_frames = len(crops_rgb) - valid_frames
        logger.info(f"Successfully processed {valid_frames} valid frames "
                   f"({padded_frames} padded)")

        return VideoBatch(
            crops_rgb=crops_rgb,
            frames=frame_infos,
            meta=meta
        )

    finally:
        cap.release()


def create_video_processor(predictor_path: Optional[str] = None):
    """
    Create face detector and predictor for video processing.

    Args:
        predictor_path: Path to dlib 81-point predictor file.
                       If None, uses constants.get_dlib_predictor_path()

    Returns:
        tuple: (detector, predictor) ready for load_video_32()

    Raises:
        FileNotFoundError: If predictor file not found
    """
    detector, predictor = face_align_crop.create_dlib_detector_and_predictor(predictor_path)
    logger.info("Created dlib face detector and 81-point predictor")
    return detector, predictor


# Convenience function for one-shot processing
def process_video(video_path: str, predictor_path: Optional[str] = None, **kwargs) -> VideoBatch:
    """
    One-shot video processing with automatic detector/predictor creation.

    Args:
        video_path: Path to input video file
        predictor_path: Path to dlib predictor file (optional)
        **kwargs: Additional arguments passed to load_video_32()

    Returns:
        VideoBatch: Processed video batch
    """
    detector, predictor = create_video_processor(predictor_path)
    return load_video_32(video_path, detector, predictor, **kwargs)
