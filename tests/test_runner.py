# tests/test_runner.py
"""
Unit tests for ml.runner using ONLY unittest.mock (no pytest monkeypatch).

These tests stub out I/O and model inference so we can validate the runner's
contract end-to-end:
- input video batch ingestion
- preprocessing -> normalized tensor
- per-model adapter routing and return-shape validation
- aggregation (mean of per-frame probs)
- structured JSON output schema
- CLI entrypoint behavior
"""

import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import numpy as np
import pytest
import torch

import ml.runner as runner_mod


def _mk_video_batch(N=5):
    """
    Build a minimal VideoBatch-like object (using SimpleNamespace) that the
    runner expects from ml.video_io.process_video().
    """
    meta = SimpleNamespace(
        path="fake.mp4",
        fps=25.0,
        frame_count=100,
        duration_sec=4.0,
        width=1920,
        height=1080,
    )
    # Create N synthetic frames with consistent indices/timestamps
    frames = [
        SimpleNamespace(index=i * 10, timestamp_sec=i * (1.0 / 25.0) * 10)
        for i in range(N)
    ]
    # Create N dummy 256x256 RGB crops (uint8) as preprocess inputs
    crops_rgb = [np.zeros((256, 256, 3), dtype=np.uint8) for _ in range(N)]
    return SimpleNamespace(crops_rgb=crops_rgb, frames=frames, meta=meta)


def _stub_adapter_dict(N, feat_dim=32, p0=0.1, p1=0.9):
    """
    Build a DeepfakeBench-format adapter dict with deterministic content:

    - 'prob' is a linspace from p0..p1 (used to test aggregation = mean)
    - 'cls' is a [N,2] tensor with column-1 set to prob (shape contract check)
    - 'feat' is [N, feat_dim] (kept simple; content not used by runner)
    """
    probs = torch.linspace(p0, p1, steps=N)
    cls = torch.zeros(N, 2, dtype=torch.float32)
    cls[:, 1] = probs
    feat = torch.zeros(N, feat_dim, dtype=torch.float32)
    return {"cls": cls, "prob": probs, "feat": feat}


def test_runner_happy_path():
    """
    Happy-path integration:
    - Stubs process_video(), preprocess_crops(), model loaders, and adapter predicts
    - Verifies output schema, presence of 3 models, and correct mean aggregation
    - Ensures per-frame indices/timestamps propagate through to model frames[]
    """
    N = 5
    vb = _mk_video_batch(N)

    with (
        patch("ml.runner.process_video", return_value=vb),
        patch(
            "ml.runner.preprocess_crops",
            side_effect=lambda crops, device="cpu": torch.randn(
                N, 3, 256, 256, dtype=torch.float32
            ),
        ),
        patch.object(
            runner_mod, "MODEL_ROUTES",
            {
                "xception": (lambda w,d: object(), lambda m,b: _stub_adapter_dict(N, p0=0.0, p1=1.0), "Xception"),
                "spsl":     (lambda w,d: object(), lambda m,b: _stub_adapter_dict(N, p0=0.2, p1=0.6), "SPSL"),
                "ucf":      (lambda w,d: object(), lambda m,b: _stub_adapter_dict(N, p0=0.4, p1=0.8), "UCF"),
            },
        ),
    ):
        out = runner_mod.run(
            "fake.mp4", device="cpu", models=["xception", "spsl", "ucf"], weights={}
        )

    # Top-level schema keys
    assert set(out.keys()) >= {"video", "frames", "models", "timing_ms", "error"}
    assert out["error"] is None
    assert len(out["frames"]) == N
    assert len(out["models"]) == 3

    by_name = {m["name"]: m for m in out["models"]}

    def mean(a, b):
        # Mean of torch.linspace(a, b, N)
        return float(torch.linspace(a, b, steps=N).mean().item())

    # Video-level scores should equal mean of deterministic per-frame linspace
    assert by_name["Xception"]["score"] == pytest.approx(mean(0.0, 1.0))
    assert by_name["SPSL"]["score"] == pytest.approx(mean(0.2, 0.6))
    assert by_name["UCF"]["score"] == pytest.approx(mean(0.4, 0.8))

    # Frame alignment: model.frames[i].(index,time) must match top-level frames[i]
    for model in out["models"]:
        assert len(model["frames"]) == N
        for i, entry in enumerate(model["frames"]):
            assert entry["index"] == out["frames"][i]["index"]
            assert entry["time"] == out["frames"][i]["time"]


def test_runner_empty_video():
    """
    Empty video / no crops case:
    - process_video returns empty crops/frames
    - Runner should not crash; returns structured error {stage:'decode'}
    - frames=[], models=[]
    """
    empty_vb = SimpleNamespace(
        crops_rgb=[],
        frames=[],
        meta=SimpleNamespace(
            path="empty.mp4", fps=0.0, frame_count=0, duration_sec=0.0, width=0, height=0
        ),
    )

    with patch("ml.runner.process_video", return_value=empty_vb):
        out = runner_mod.run("empty.mp4", device="cpu", models=["xception"], weights={})

    assert out["frames"] == []
    assert out["models"] == []
    assert out["error"] and out["error"]["stage"] == "decode"


def test_runner_model_failure_isolated():
    """
    One model raises at inference; others succeed:
    - Ensure the failing model is omitted, not crashing the entire run
    - Confirms failure isolation / graceful degradation behavior
    """
    N = 4
    vb = _mk_video_batch(N)

    with (
        patch("ml.runner.process_video", return_value=vb),
        patch(
            "ml.runner.preprocess_crops",
            side_effect=lambda crops, device="cpu": torch.randn(
                N, 3, 256, 256, dtype=torch.float32
            ),
        ),
        patch.object(
            runner_mod, "MODEL_ROUTES",
            {
                "xception": (lambda w,d: object(), lambda m,b: _stub_adapter_dict(N), "Xception"),
                "spsl":     (lambda w,d: object(), (lambda *_: (_ for _ in ()).throw(RuntimeError("kaboom"))), "SPSL"),
            },
        ),
    ):
        out = runner_mod.run(
            "fake.mp4", device="cpu", models=["xception", "spsl"], weights={}
        )

    # Only the successful model appears in results
    names = [m["name"] for m in out["models"]]
    assert names == ["Xception"]


def test_weight_env_fallback_and_hash(tmp_path):
    """
    Env fallback + weight hashing:
    - Put a real temp weight file path in $XCEPTION_WEIGHTS
    - Provide weights={'xception': None} so env var is used
    - Runner should include 'weights_hash' for that model
    """
    wfile = tmp_path / "xception_fake.pth"
    wfile.write_bytes(b"hello-weights")  # real content → stable hash

    N = 2
    vb = _mk_video_batch(N)

    with (
        patch("ml.runner.process_video", return_value=vb),
        patch(
            "ml.runner.preprocess_crops",
            side_effect=lambda crops, device="cpu": torch.randn(
                N, 3, 256, 256, dtype=torch.float32
            ),
        ),
        patch.object(
            runner_mod, "MODEL_ROUTES",
            {
                "xception": (lambda w,d: object(), lambda m,b: _stub_adapter_dict(N), "Xception"),
            },
        ),
        patch.dict(os.environ, {"XCEPTION_WEIGHTS": str(wfile)}, clear=False),
    ):
        out = runner_mod.run(
            "fake.mp4", device="cpu", models=["xception"], weights={"xception": None}
        )

    assert len(out["models"]) == 1
    assert out["models"][0]["weights_hash"] is not None


@pytest.mark.parametrize("cli_models", ["xception,spsl"])
def test_cli_entrypoint_smoke(capsys, cli_models):
    """
    CLI smoke test:
    - Patch sys.argv and run runner.main()
    - Validate printed JSON structure and that --models is honored
    - Hashing is disabled via --no-hash to keep it fast/stable
    """
    N = 3
    vb = _mk_video_batch(N)

    with (
        patch("ml.runner.process_video", return_value=vb),
        patch(
            "ml.runner.preprocess_crops",
            side_effect=lambda crops, device="cpu": torch.randn(
                N, 3, 256, 256, dtype=torch.float32
            ),
        ),
        patch.object(
            runner_mod, "MODEL_ROUTES",
            {
                "xception": (lambda w,d: object(), lambda m,b: _stub_adapter_dict(N, p0=0.1, p1=0.1), "Xception"),
                "spsl":     (lambda w,d: object(), lambda m,b: _stub_adapter_dict(N, p0=0.2, p1=0.2), "SPSL"),
            },
        ),
        patch.object(
            sys,
            "argv",
            ["prog", "fake.mp4", "--device", "cpu", "--models", cli_models, "--no-hash"],
            create=True,
        ),
    ):
        runner_mod.main()
        out = capsys.readouterr().out

    payload = json.loads(out)
    assert "video" in payload and "models" in payload
    want = [s.upper() for s in cli_models.split(",")]
    names = [m["name"].upper() for m in payload["models"]]
    assert all(n in names for n in want)


def test_runner_guard_wrong_dtype():
    """
    WHAT: If preprocessing returns a tensor with the wrong dtype (float64),
          the runner should **not** proceed. It must surface an INTERNAL error.

    WHY: This catches pipeline misconfigurations early (e.g., transforms returning
         doubles by mistake). Silently accepting the wrong dtype risks undefined
         model behavior.

    EXPECTED: The runner returns a structured error envelope:
              out["error"]["stage"] == "internal", and no frames/models in output.
    """
    N = 3
    vb = _mk_video_batch(N)

    with (
        patch("ml.runner.process_video", return_value=vb),
        # Return a *wrong* dtype (float64), right shape/device.
        patch("ml.runner.preprocess_crops",
              return_value=torch.zeros(N, 3, 256, 256, dtype=torch.float64)),
        # Minimal routes to avoid real adapter calls; we won't reach them.
        patch.object(
            runner_mod, "MODEL_ROUTES",
            {"xception": (lambda _w, _d: object(), lambda _m, _b: _stub_adapter_dict(N), "Xception")},
        ),
    ):
        out = runner_mod.run("fake.mp4", device="cpu", models=["xception"], weights={})

    # The runner should bail with a structured internal error, not crash.
    assert out["error"] and out["error"]["stage"] == "internal"
    assert out["models"] == []
    assert out["frames"] == []


def test_runner_guard_wrong_device():
    """
    WHAT: If the runner is told to use 'cuda' but preprocessing returns a CPU tensor,
          the runner should not proceed; it must surface an INTERNAL error.

    WHY: Proves we enforce device contract after preprocessing.

    EXPECTED: out['error']['stage'] == 'internal' (not a crash).
    """
    N = 3
    vb = _mk_video_batch(N)

    with (
        patch("ml.runner.torch.cuda.is_available", return_value=True),  # <-- let _select_device accept 'cuda'
        patch("ml.runner.process_video", return_value=vb),
        # Return CPU tensor while runner thinks device='cuda'
        patch("ml.runner.preprocess_crops",
              return_value=torch.zeros(N, 3, 256, 256, dtype=torch.float32, device="cpu")),
        patch.object(
            runner_mod, "MODEL_ROUTES",
            {"xception": (lambda _w, _d: object(), lambda _m, _b: _stub_adapter_dict(N), "Xception")},
        ),
    ):
        out = runner_mod.run("fake.mp4", device="cuda", models=["xception"], weights={})

    assert out["error"] and out["error"]["stage"] == "internal"
    assert out["models"] == []
    assert out["frames"] == []


def test_runner_length_mismatch_internal_error():
    """
    WHAT: If an adapter returns N-1 probabilities while the runner has N frames,
          the output assembler should **reject** the inconsistency.

    WHY: This enforces the adapter contract (one prob per frame). Any drift in an
         adapter (or pre/postprocessing) must be caught before we emit misleading JSON.

    EXPECTED: The runner returns a structured error envelope:
              out["error"]["stage"] == "internal", and no frames/models in output.
    """
    N = 5
    vb = _mk_video_batch(N)

    def stub_mismatch(_m, _b):
        probs = torch.linspace(0.0, 1.0, steps=N - 1)  # one short on purpose
        cls = torch.zeros(N - 1, 2, dtype=torch.float32)
        cls[:, 1] = probs
        feat = torch.zeros(N - 1, 32, dtype=torch.float32)
        return {"cls": cls, "prob": probs, "feat": feat}

    with (
        patch("ml.runner.process_video", return_value=vb),
        patch("ml.runner.preprocess_crops",
              return_value=torch.zeros(N, 3, 256, 256, dtype=torch.float32)),
        patch.object(
            runner_mod, "MODEL_ROUTES",
            {"xception": (lambda _w, _d: object(), stub_mismatch, "Xception")},
        ),
    ):
        out = runner_mod.run("fake.mp4", device="cpu", models=["xception"], weights={})

    # The assembler should assert and the runner should transform that into an internal error.
    assert out["error"] and out["error"]["stage"] == "internal"
    assert out["models"] == []
    assert out["frames"] == []