# tests/test_schema_contract.py
"""
Schema contract tests for ml.schema.

These tests validate, in isolation, that the schema contract is enforced
and that runner outputs conform to that contract — using only
unittest.mock.patch for any orchestration stubbing.
"""

import json
from unittest.mock import patch
import pytest

from ml.schema import (
    SCHEMA_VERSION,
    validate_result,
    to_json,
    from_json,
)


# --------------------------
# Helpers to build payloads
# --------------------------

def _mk_frames(N=4, fps=25.0):
    """Top-level frames list: monotonically increasing timestamps."""
    return [{"index": i, "time": i / fps} for i in range(N)]

def _mk_model(name, frames, probs, weights_hash=None):
    """
    Build a ModelOut dict aligned to `frames`:
    - copies index/time from frames
    - per-frame score from probs[i]
    - video-level score is mean(probs) or None if no frames
    """
    if frames:
        frame_scores = [
            {"index": fr["index"], "time": fr["time"], "score": float(probs[i])}
            for i, fr in enumerate(frames)
        ]
        score = float(sum(probs) / len(probs))
    else:
        frame_scores = []
        score = None
    return {
        "name": name,
        "score": score,
        "frames": frame_scores,
        "weights_hash": weights_hash,
    }

def _mk_base_video_meta():
    return {
        "path": "video.mp4",
        "fps": 25.0,
        "frame_count": 100,
        "duration_sec": 4.0,
        "width": 1920,
        "height": 1080,
    }

def _mk_valid_result(N=4):
    """
    Fully valid VideoInferenceResult used as a starting point for tests.

    WHY: Establishes the happy-path structure so we can purposefully break
    specific invariants and verify validation catches them.
    """
    frames = _mk_frames(N)
    probs_x = [i / (N - 1) if N > 1 else 0.0 for i in range(N)]  # linspace [0..1]
    probs_s = [0.2] * N                                          # constant
    return {
        "schema_version": SCHEMA_VERSION,
        "video": _mk_base_video_meta(),
        "frames": frames,
        "models": [
            _mk_model("Xception", frames, probs_x),
            _mk_model("SPSL", frames, probs_s),
        ],
        "timing_ms": {
            "decode_align": 1.0,
            "normalize": 1.0,
            "load_models": 1.0,
            "inference_total": 1.0,
        },
        "error": None,
    }


# --------------------------
# Core validation tests
# --------------------------

def test_schema_happy_path_valid():
    """
    WHAT: A fully correct payload validates.
    WHY: Baseline sanity that our builder + validator agree on invariants.
    EXPECT: validate_result() does not raise.
    """
    obj = _mk_valid_result(N=5)
    validate_result(obj)  # should not raise


def test_schema_empty_frames_require_none_score():
    """
    WHAT: When frames == [], each model must have score=None and frames=[].
    WHY: Enforces empty-video semantics for downstream simplicity.
    EXPECT: validate_result() passes with score=None for empty frames.
    """
    obj = {
        "schema_version": SCHEMA_VERSION,
        "video": _mk_base_video_meta(),
        "frames": [],
        "models": [
            _mk_model("Xception", [], []),
            _mk_model("SPSL", [], []),
        ],
        "timing_ms": {},  # allowed (total=False in schema)
        "error": {"stage": "decode", "message": "no frames"},
    }
    validate_result(obj)


def test_schema_timestamps_must_be_non_decreasing():
    """
    WHAT: Timestamps must be non-decreasing (padding may duplicate times).
    WHY: Consumers rely on chronological order; schema encodes monotonicity.
    EXPECT: Validator raises if time[i] > time[i+1].
    """
    frames = [{"index": 0, "time": 0.04},
              {"index": 1, "time": 0.08},
              {"index": 2, "time": 0.01}]  # violation
    obj = _mk_valid_result(N=0)
    obj["frames"] = frames
    obj["models"] = [
        {
            "name": "Xception",
            "score": 0.5,
            "frames": [{"index": f["index"], "time": f["time"], "score": 0.5} for f in frames],
            "weights_hash": None,
        }
    ]
    with pytest.raises(AssertionError):
        validate_result(obj)


def test_schema_model_frames_length_mismatch():
    """
    WHAT: model.frames length must equal top-level frames length.
    WHY: Keeps indices aligned; prevents subtle UI/out-of-bounds bugs.
    EXPECT: Validator raises when lengths differ.
    """
    obj = _mk_valid_result(N=4)
    obj["models"][0]["frames"] = obj["models"][0]["frames"][:-1]  # drop one
    with pytest.raises(AssertionError):
        validate_result(obj)


def test_schema_index_time_alignment_mismatch():
    """
    WHAT: Each model frame must copy index/time from the top-level frame at that position.
    WHY: Guarantees per-model data aligns with the global frame list.
    EXPECT: Validator raises if any index/time differs.
    """
    obj = _mk_valid_result(N=3)
    obj["models"][0]["frames"][1]["time"] += 0.5  # corrupt time
    with pytest.raises(AssertionError):
        validate_result(obj)


def test_schema_score_out_of_range_rejected():
    """
    WHAT: Per-frame scores must be probabilities in [0,1].
    WHY: Prevents invalid classifier outputs from slipping through.
    EXPECT: Validator raises for scores <0 or >1.
    """
    obj = _mk_valid_result(N=3)
    obj["models"][1]["frames"][0]["score"] = 1.5  # invalid
    with pytest.raises(AssertionError):
        validate_result(obj)


def test_schema_aggregation_must_equal_mean():
    """
    WHAT: model.score must equal arithmetic mean of per-frame scores.
    WHY: Runner promises 'mean aggregation'; schema locks it.
    EXPECT: Validator raises if model.score != mean(frames[].score).
    """
    obj = _mk_valid_result(N=4)
    obj["models"][0]["score"] += 0.01  # break the contract slightly
    with pytest.raises(AssertionError):
        validate_result(obj)


def test_schema_version_mismatch_rejected():
    """
    WHAT: schema_version must exactly match SCHEMA_VERSION.
    WHY: Prevents silent contract drift when dependencies change.
    EXPECT: Validator raises on mismatch.
    """
    obj = _mk_valid_result(N=2)
    obj["schema_version"] = "9.9.9"
    with pytest.raises(AssertionError):
        validate_result(obj)


def test_schema_timings_must_be_non_negative():
    """
    WHAT: Timing values represent milliseconds; they must not be negative.
    WHY: Catches underflow/clock errors early.
    EXPECT: Validator raises on negative timing.
    """
    obj = _mk_valid_result(N=2)
    obj["timing_ms"]["normalize"] = -3.0
    with pytest.raises(AssertionError):
        validate_result(obj)


def test_schema_json_roundtrip_preserves_structure():
    """
    WHAT: to_json()/from_json() should be a lossless round-trip for valid payloads.
    WHY: Ensures serialization layer won't distort numeric/None fields.
    EXPECT: from_json(to_json(obj)) validates and yields an equivalent dict.
    """
    obj = _mk_valid_result(N=3)
    s = to_json(obj)
    obj2 = from_json(s)  # validates inside
    assert obj2["schema_version"] == obj["schema_version"]
    assert obj2["video"] == obj["video"]
    assert obj2["frames"] == obj["frames"]
    assert obj2["models"] == obj["models"]
    assert obj2["error"] == obj["error"]
    for k, v in obj["timing_ms"].items():
        assert abs(obj2["timing_ms"][k] - v) < 1e-12


# --------------------------
# Runner integration smoke
# --------------------------

def test_runner_output_conforms_to_schema_smoke():
    """
    WHAT: Minimal runner invocation yields schema-valid output.
    WHY: Guards the runner→schema interface as we evolve both modules.
    EXPECT: validate_result() accepts the result.
    """
    import torch
    import ml.runner as runner_mod

    # Build a minimal "VideoBatch-like" object the runner expects
    class _Meta:  # simple attribute bag
        path = "video.mp4"
        fps = 25.0
        frame_count = 100
        duration_sec = 4.0
        width = 1920
        height = 1080

    class _Frame:
        def __init__(self, i, t): self.index, self.timestamp_sec = i, t

    class _VB:
        pass

    N = 3
    vb = _VB()
    vb.meta = _Meta()
    vb.frames = [_Frame(i * 10, i * (1.0 / 25.0) * 10) for i in range(N)]
    vb.crops_rgb = [b"\x00"] * N  # not used by our preprocess stub

    # Stub adapter returns deterministic probabilities and shape-correct tensors
    def _stub_adapter(_m, _b):
        probs = torch.linspace(0.0, 1.0, steps=N)
        return {
            "cls": torch.zeros(N, 2),
            "prob": probs,
            "feat": torch.zeros(N, 32),
        }

    with (
        patch("ml.runner.process_video", return_value=vb),
        patch("ml.runner.preprocess_crops",
              side_effect=lambda crops, device="cpu":
                  torch.zeros(N, 3, 256, 256, dtype=torch.float32, device="cpu")),
        patch.object(
            runner_mod, "MODEL_ROUTES",
            {"xception": (lambda w, d: object(), _stub_adapter, "Xception")},
        ),
    ):
        out = runner_mod.run("video.mp4", device="cpu", models=["xception"], weights={})
        # This is the whole point: runner-produced JSON conforms to our schema.
        validate_result(out)