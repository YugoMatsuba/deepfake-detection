# schema.py - Versioned output schema for DeepfakeBench-aligned inference
"""
Precise, versioned JSON schema contract for ml.runner output.

Provides TypedDict definitions, validation helpers, and serialization functions
for the video inference pipeline. Encodes DeepfakeBench assumptions:
- 32-frame uniform sampling with padding semantics
- Per-frame deepfake probabilities in [0.0, 1.0]
- Simple mean aggregation for video-level scores
- Structured error envelopes for graceful failure handling

Zero runtime dependencies - uses only standard library typing.
"""

import json
from typing import TypedDict, Literal, List, Union, Dict, Any

# Schema version - bump for breaking changes
SCHEMA_VERSION = "1.0.0"

# Type aliases for constrained values
ModelName = Literal["Xception", "SPSL", "UCF"]
ErrorStage = Literal["decode", "preprocess", "load_models", "inference", "aggregate", "internal", "cli"]


class VideoMetaOut(TypedDict):
    """
    Video metadata captured during ingest and processing.

    Units:
    - fps: frames per second (float, may be 0.0 if unknown)
    - duration_sec: total duration in seconds (derived from frame_count/fps)
    - width/height: source resolution in pixels
    """
    path: str                 # Video file path (relative or absolute)
    fps: float                # Frames per second from container metadata
    frame_count: int          # Total frames in source video
    duration_sec: float       # Video duration in seconds
    width: int                # Source width in pixels
    height: int               # Source height in pixels


class FrameRef(TypedDict):
    """
    Frame reference without prediction score.

    Used at top-level to define the ordered sequence of frames processed.

    Units:
    - index: 0-based frame index in source video
    - time: timestamp in seconds relative to video start

    Invariants:
    - Timestamps are non-decreasing (padding may create duplicates)
    - Length typically 32 (DeepfakeBench standard) but may be 0 for empty videos
    """
    index: int                # Original frame index in source video
    time: float               # Timestamp in seconds (index / fps)


class FrameScore(FrameRef):
    """
    Per-frame prediction result extending FrameRef with model score.

    Used in per-model results to provide frame-by-frame predictions.

    Invariants:
    - score in [0.0, 1.0] (deepfake class probability)
    - index/time must match corresponding top-level FrameRef
    """
    score: float              # Deepfake class probability in [0.0, 1.0]


class ModelOut(TypedDict):
    """
    Per-model inference results with provenance tracking.

    Invariants:
    - name constrained to known model types
    - score is None iff len(frames) == 0 (empty video case)
    - score equals mean of frame scores when frames present
    - frames length must match top-level frames length
    - frames[i].index and frames[i].time must match top-level frames[i]
    """
    name: ModelName           # Model display name: "Xception" | "SPSL" | "UCF"
    score: Union[float, None] # Video-level score (mean of frames) or None if empty
    frames: List[FrameScore]  # Per-frame scores, same length/order as top-level frames
    weights_hash: Union[str, None]  # SHA-256 hex of weight file, or None if unavailable


class TimingOut(TypedDict, total=False):
    """
    Pipeline stage timings in milliseconds.

    Uses total=False to allow future extension with new timing keys
    without breaking existing consumers.

    Units: All values are milliseconds (float)
    Invariants: All values >= 0.0
    """
    decode_align: float       # Video decode + face detection + alignment + padding
    normalize: float          # Tensor conversion + normalization + device transfer
    load_models: float        # Model weight loading and initialization
    inference_total: float    # Total time for all model inference (sequential)


class ErrorOut(TypedDict):
    """
    Structured error envelope for graceful failure reporting.

    Used when pipeline cannot complete normally but should not crash.
    Presence of error field indicates incomplete processing.
    """
    stage: ErrorStage         # Pipeline stage where error occurred
    message: str              # Human-readable error description


class VideoInferenceResult(TypedDict):
    """
    Top-level schema for video inference pipeline output.

    Invariants:
    - schema_version must equal SCHEMA_VERSION
    - All models.frames must have same length as top-level frames
    - Frame indices/timestamps must align across models
    - When error is present, models may be empty but structure remains valid
    - When frames is empty, all model scores must be None
    """
    schema_version: str       # Schema version for compatibility tracking
    video: VideoMetaOut       # Source video metadata
    frames: List[FrameRef]    # Ordered sequence of processed frames (may be empty)
    models: List[ModelOut]    # Results from successfully executed models
    timing_ms: TimingOut      # Pipeline stage timings
    error: Union[ErrorOut, None]  # Error info if pipeline failed, None on success


def validate_result(obj: Dict[str, Any]) -> None:
    """
    Validate VideoInferenceResult against schema invariants.

    Enforces critical requirements:
    1. Schema version matches expected version
    2. Empty frames → model scores must be None (not numeric)
    3. Timestamps are non-decreasing (allows duplicates from padding)
    4. Length consistency across models and top-level frames
    5. Score ranges and aggregation accuracy

    Args:
        obj: Dictionary to validate (should conform to VideoInferenceResult)

    Raises:
        AssertionError: If any invariant is violated
    """
    # 1. Schema version requirement
    assert "schema_version" in obj, "Missing required field: schema_version"
    assert obj["schema_version"] == SCHEMA_VERSION, f"Schema version mismatch: expected {SCHEMA_VERSION}, got {obj['schema_version']}"

    # 2. Validate top-level structure
    assert "video" in obj, "Missing required field: video"
    assert "frames" in obj, "Missing required field: frames"
    assert "models" in obj, "Missing required field: models"
    assert "timing_ms" in obj, "Missing required field: timing_ms"
    assert "error" in obj, "Missing required field: error"

    frames = obj["frames"]
    models = obj["models"]

    # 3. Non-decreasing timestamps requirement (allows duplicates from padding)
    if len(frames) > 1:
        times = [f["time"] for f in frames]
        for i in range(len(times) - 1):
            assert times[i] <= times[i + 1], f"Timestamps must be non-decreasing: {times[i]} > {times[i + 1]} at index {i}"

    # 4. Per-model validation
    for model in models:
        model_frames = model["frames"]

        # Length consistency
        assert len(model_frames) == len(frames), f"Model {model['name']} has {len(model_frames)} frames, expected {len(frames)}"

        # Empty frames → None score requirement
        if len(frames) == 0:
            assert model["score"] is None, f"Model {model['name']} with empty frames must have score=None, got {model['score']}"
        else:
            # Non-empty: score must be numeric and equal to mean
            assert model["score"] is not None, f"Model {model['name']} with {len(frames)} frames must have numeric score, got None"
            assert isinstance(model["score"], (int, float)), f"Model {model['name']} score must be numeric, got {type(model['score'])}"

            # Index/time alignment
            for i, (top_frame, model_frame) in enumerate(zip(frames, model_frames)):
                assert top_frame["index"] == model_frame["index"], f"Index mismatch at frame {i}: top={top_frame['index']}, model={model_frame['index']}"
                assert abs(top_frame["time"] - model_frame["time"]) < 1e-6, f"Time mismatch at frame {i}: top={top_frame['time']}, model={model_frame['time']}"

                # Score range validation
                score = model_frame["score"]
                assert 0.0 <= score <= 1.0, f"Score out of range [0,1]: {score} at frame {i}"

            # Aggregation accuracy (mean validation)
            expected_mean = sum(f["score"] for f in model_frames) / len(model_frames)
            actual_score = model["score"]
            assert abs(actual_score - expected_mean) < 1e-6, f"Model {model['name']} score {actual_score} != mean of frame scores {expected_mean}"

    # 5. Timing validation (non-negative)
    timing = obj["timing_ms"]
    for key, value in timing.items():
        assert isinstance(value, (int, float)), f"Timing {key} must be numeric, got {type(value)}"
        assert value >= 0.0, f"Timing {key} must be non-negative, got {value}"


def mean_from_frames(frames: List[FrameScore]) -> Union[float, None]:
    """
    Calculate mean score from frame scores using pure Python.

    Args:
        frames: List of FrameScore objects

    Returns:
        Mean score as float, or None if frames is empty
    """
    if not frames:
        return None
    return sum(f["score"] for f in frames) / len(frames)


def to_json(obj: VideoInferenceResult) -> str:
    """
    Serialize VideoInferenceResult to JSON string.

    Uses compact formatting and ensures no NaN/Infinity values.

    Args:
        obj: VideoInferenceResult to serialize

    Returns:
        JSON string representation
    """
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def from_json(s: str) -> VideoInferenceResult:
    """
    Parse and validate JSON string to VideoInferenceResult.

    Args:
        s: JSON string to parse

    Returns:
        Validated VideoInferenceResult object

    Raises:
        json.JSONDecodeError: If JSON parsing fails
        AssertionError: If validation fails
    """
    obj = json.loads(s)
    validate_result(obj)
    return obj  # Type checker knows this is VideoInferenceResult after validation


# Export all public symbols
__all__ = [
    "SCHEMA_VERSION",
    "ModelName",
    "ErrorStage",
    "VideoMetaOut",
    "FrameRef",
    "FrameScore",
    "ModelOut",
    "TimingOut",
    "ErrorOut",
    "VideoInferenceResult",
    "validate_result",
    "mean_from_frames",
    "to_json",
    "from_json",
]