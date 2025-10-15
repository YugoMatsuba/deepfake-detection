# tests/test_schema.py
"""
Unit tests for ml.schema validation and serialization.

Tests schema invariant enforcement, JSON round-trip, and critical requirements:
- Empty frames → model scores must be None
- Non-decreasing timestamps (allows duplicates from padding)
- Schema version validation
- Length consistency and aggregation accuracy
"""

import pytest
from ml.schema import (
    SCHEMA_VERSION, validate_result, mean_from_frames, to_json, from_json,
    VideoInferenceResult, FrameRef, FrameScore, ModelOut, VideoMetaOut
)


def test_schema_version_constant():
    """Test schema version is properly defined."""
    assert SCHEMA_VERSION == "1.0.0"
    assert isinstance(SCHEMA_VERSION, str)


def test_mean_from_frames():
    """Test pure Python mean calculation helper."""
    # Empty frames → None
    assert mean_from_frames([]) is None

    # Single frame
    frames = [{"index": 0, "time": 0.0, "score": 0.5}]
    assert mean_from_frames(frames) == 0.5

    # Multiple frames
    frames = [
        {"index": 0, "time": 0.0, "score": 0.2},
        {"index": 1, "time": 1.0, "score": 0.8},
        {"index": 2, "time": 2.0, "score": 0.5}
    ]
    assert mean_from_frames(frames) == pytest.approx(0.5)


def test_validate_result_happy_path():
    """Test validation passes for well-formed result."""
    result = {
        "schema_version": "1.0.0",
        "video": {
            "path": "test.mp4",
            "fps": 25.0,
            "frame_count": 100,
            "duration_sec": 4.0,
            "width": 640,
            "height": 480
        },
        "frames": [
            {"index": 0, "time": 0.0},
            {"index": 25, "time": 1.0},
            {"index": 50, "time": 2.0}
        ],
        "models": [
            {
                "name": "Xception",
                "score": 0.6,
                "frames": [
                    {"index": 0, "time": 0.0, "score": 0.4},
                    {"index": 25, "time": 1.0, "score": 0.7},
                    {"index": 50, "time": 2.0, "score": 0.7}
                ],
                "weights_hash": "abc123"
            }
        ],
        "timing_ms": {
            "decode_align": 100.0,
            "normalize": 10.0,
            "load_models": 200.0,
            "inference_total": 50.0
        },
        "error": None
    }

    # Should not raise
    validate_result(result)


def test_validate_result_empty_frames_requires_none_score():
    """Test critical requirement: empty frames → model score must be None."""
    result = {
        "schema_version": "1.0.0",
        "video": {"path": "empty.mp4", "fps": 0.0, "frame_count": 0, "duration_sec": 0.0, "width": 0, "height": 0},
        "frames": [],
        "models": [
            {
                "name": "Xception",
                "score": 0.5,  # WRONG: should be None for empty frames
                "frames": [],
                "weights_hash": None
            }
        ],
        "timing_ms": {},
        "error": {"stage": "decode", "message": "no frames"}
    }

    with pytest.raises(AssertionError, match="with empty frames must have score=None"):
        validate_result(result)

    # Fix: set score to None
    result["models"][0]["score"] = None
    validate_result(result)  # Should pass now


def test_validate_result_non_decreasing_timestamps():
    """Test critical requirement: timestamps must be non-decreasing (allows duplicates)."""
    base_result = {
        "schema_version": "1.0.0",
        "video": {"path": "test.mp4", "fps": 25.0, "frame_count": 100, "duration_sec": 4.0, "width": 640, "height": 480},
        "models": [],
        "timing_ms": {},
        "error": None
    }

    # Valid: strictly increasing
    result = base_result.copy()
    result["frames"] = [
        {"index": 0, "time": 0.0},
        {"index": 25, "time": 1.0},
        {"index": 50, "time": 2.0}
    ]
    validate_result(result)  # Should pass

    # Valid: non-decreasing with duplicates (padding case)
    result = base_result.copy()
    result["frames"] = [
        {"index": 0, "time": 0.0},
        {"index": 25, "time": 1.0},
        {"index": 25, "time": 1.0},  # Duplicate from padding
        {"index": 25, "time": 1.0}   # Another duplicate
    ]
    validate_result(result)  # Should pass

    # Invalid: decreasing timestamps
    result = base_result.copy()
    result["frames"] = [
        {"index": 0, "time": 0.0},
        {"index": 25, "time": 2.0},
        {"index": 50, "time": 1.0}  # Goes backward
    ]
    with pytest.raises(AssertionError, match="Timestamps must be non-decreasing"):
        validate_result(result)


def test_validate_result_schema_version_mismatch():
    """Test schema version validation."""
    result = {
        "schema_version": "2.0.0",  # Wrong version
        "video": {"path": "test.mp4", "fps": 25.0, "frame_count": 100, "duration_sec": 4.0, "width": 640, "height": 480},
        "frames": [],
        "models": [],
        "timing_ms": {},
        "error": None
    }

    with pytest.raises(AssertionError, match="Schema version mismatch"):
        validate_result(result)


def test_validate_result_length_consistency():
    """Test that model frames must match top-level frames length."""
    result = {
        "schema_version": "1.0.0",
        "video": {"path": "test.mp4", "fps": 25.0, "frame_count": 100, "duration_sec": 4.0, "width": 640, "height": 480},
        "frames": [
            {"index": 0, "time": 0.0},
            {"index": 25, "time": 1.0}
        ],
        "models": [
            {
                "name": "Xception",
                "score": 0.5,
                "frames": [
                    {"index": 0, "time": 0.0, "score": 0.5}  # Only 1 frame, but top-level has 2
                ],
                "weights_hash": None
            }
        ],
        "timing_ms": {},
        "error": None
    }

    with pytest.raises(AssertionError, match="has 1 frames, expected 2"):
        validate_result(result)


def test_validate_result_aggregation_accuracy():
    """Test that model score equals mean of frame scores."""
    result = {
        "schema_version": "1.0.0",
        "video": {"path": "test.mp4", "fps": 25.0, "frame_count": 100, "duration_sec": 4.0, "width": 640, "height": 480},
        "frames": [
            {"index": 0, "time": 0.0},
            {"index": 25, "time": 1.0}
        ],
        "models": [
            {
                "name": "Xception",
                "score": 0.8,  # Wrong: should be 0.5 (mean of 0.4 and 0.6)
                "frames": [
                    {"index": 0, "time": 0.0, "score": 0.4},
                    {"index": 25, "time": 1.0, "score": 0.6}
                ],
                "weights_hash": None
            }
        ],
        "timing_ms": {},
        "error": None
    }

    with pytest.raises(AssertionError, match="score .* != mean of frame scores"):
        validate_result(result)


def test_json_round_trip():
    """Test JSON serialization and deserialization with validation."""
    result = {
        "schema_version": "1.0.0",
        "video": {
            "path": "test.mp4",
            "fps": 25.0,
            "frame_count": 75,
            "duration_sec": 3.0,
            "width": 640,
            "height": 480
        },
        "frames": [
            {"index": 0, "time": 0.0},
            {"index": 37, "time": 1.48},
            {"index": 74, "time": 2.96}
        ],
        "models": [
            {
                "name": "SPSL",
                "score": 0.7,
                "frames": [
                    {"index": 0, "time": 0.0, "score": 0.6},
                    {"index": 37, "time": 1.48, "score": 0.8},
                    {"index": 74, "time": 2.96, "score": 0.7}
                ],
                "weights_hash": "def456"
            }
        ],
        "timing_ms": {
            "decode_align": 150.0,
            "normalize": 15.0,
            "load_models": 250.0,
            "inference_total": 75.0
        },
        "error": None
    }

    # Round trip: dict → JSON → dict
    json_str = to_json(result)
    assert isinstance(json_str, str)
    assert "schema_version" in json_str

    parsed = from_json(json_str)
    assert parsed == result

    # Validation happens automatically in from_json
    validate_result(parsed)


def test_score_range_validation():
    """Test that scores must be in [0.0, 1.0] range."""
    result = {
        "schema_version": "1.0.0",
        "video": {"path": "test.mp4", "fps": 25.0, "frame_count": 100, "duration_sec": 4.0, "width": 640, "height": 480},
        "frames": [{"index": 0, "time": 0.0}],
        "models": [
            {
                "name": "Xception",
                "score": 1.5,  # Will be caught by aggregation check, but frame score is checked first
                "frames": [
                    {"index": 0, "time": 0.0, "score": 1.5}  # Out of range
                ],
                "weights_hash": None
            }
        ],
        "timing_ms": {},
        "error": None
    }

    with pytest.raises(AssertionError, match="Score out of range"):
        validate_result(result)


def test_timing_validation():
    """Test that timing values must be non-negative."""
    result = {
        "schema_version": "1.0.0",
        "video": {"path": "test.mp4", "fps": 25.0, "frame_count": 100, "duration_sec": 4.0, "width": 640, "height": 480},
        "frames": [],
        "models": [],
        "timing_ms": {
            "decode_align": -50.0  # Invalid: negative timing
        },
        "error": None
    }

    with pytest.raises(AssertionError, match="must be non-negative"):
        validate_result(result)