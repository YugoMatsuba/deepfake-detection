# runner.py - DeepfakeBench-aligned inference orchestrator
"""
Video-to-scores inference pipeline following exact DeepfakeBench patterns.

Consumes a video path, applies DFB preprocessing, runs model inference,
and aggregates to structured JSON output.
"""

import argparse
import json
import logging
import os
import time
from typing import Dict, List, Optional

import torch

from ml.video_io import process_video
from ml.transforms import preprocess_crops
from ml.models.xception_infer import load_xception, predict_probs_xception
from ml.models.spsl_infer import load_spsl, predict_probs_spsl
from ml.models.ucf_infer import load_ucf, predict_probs_ucf
from ml.models.utils import hash_file

# Model routing following DFB patterns
MODEL_ROUTES = {
    "xception": (load_xception, predict_probs_xception, "Xception"),
    "spsl": (load_spsl, predict_probs_spsl, "SPSL"),
    "ucf": (load_ucf, predict_probs_ucf, "UCF"),
}

logger = logging.getLogger(__name__)


def _select_device(device_arg: Optional[str]) -> str:
    """Select device following DeepfakeBench pattern."""
    if device_arg:
        # Fail fast if user explicitly requests CUDA but it's not available
        if device_arg.startswith("cuda") and not torch.cuda.is_available():
            raise RuntimeError(f"CUDA device '{device_arg}' requested but CUDA is not available")
        return device_arg
    # DeepfakeBench standard pattern
    return "cuda" if torch.cuda.is_available() else "cpu"


def _resolve_weight_paths(weights: Optional[Dict[str, Optional[str]]]) -> Dict[str, Optional[str]]:
    """Resolve weight paths from arguments and environment variables."""
    env_weights = {
        "xception": os.getenv("XCEPTION_WEIGHTS"),
        "spsl": os.getenv("SPSL_WEIGHTS"),
        "ucf": os.getenv("UCF_WEIGHTS"),
    }
    result: Dict[str, Optional[str]] = {}
    w = weights or {}
    for name in ("xception", "spsl", "ucf"):
        val = w.get(name, None)
        # None  -> use env fallback
        # ""    -> explicit empty (disable/ignore)
        result[name] = env_weights[name] if val is None else val
    return result


def _load_models(device: str, weights: Dict[str, Optional[str]], models: List[str]) -> Dict[str, torch.nn.Module]:
    """Load models following DeepfakeBench device placement patterns."""
    loaded_models = {}

    for model_name in models:
        if model_name not in MODEL_ROUTES:
            logger.warning(f"Unknown model: {model_name}, skipping")
            continue

        load_fn, _, _ = MODEL_ROUTES[model_name]
        weights_path = weights.get(model_name, "")

        try:
            # DeepfakeBench pattern: load then move to device
            model = load_fn(weights_path, device)
            loaded_models[model_name] = model
            logger.info(f"Loaded {model_name} model on {device}")
        except Exception as e:
            logger.error(f"Failed to load {model_name}: {e}")
            # Continue with other models (graceful degradation)

    return loaded_models


def _infer_one(model_name: str, model: torch.nn.Module, batch_rgb_norm: torch.Tensor) -> Dict[str, torch.Tensor]:
    """Run inference for one model using appropriate adapter."""
    _, predict_fn, _ = MODEL_ROUTES[model_name]

    # DeepfakeBench inference pattern: call adapter with normalized batch
    result = predict_fn(model, batch_rgb_norm)

    # Validate DFB format contract
    assert isinstance(result, dict), f"Adapter should return dict, got {type(result)}"
    assert set(result.keys()) == {"cls", "prob", "feat"}, f"Expected keys {{cls,prob,feat}}, got {result.keys()}"
    assert result["cls"].shape[1] == 2, f"Expected 2-class logits, got shape {result['cls'].shape}"
    assert result["prob"].ndim == 1, f"Expected 1D probabilities, got shape {result['prob'].shape}"

    return result


def _aggregate_frame_probs(probs: torch.Tensor) -> Optional[float]:
    """Aggregate frame probabilities following DeepfakeBench pattern."""
    if len(probs) == 0:
        return None
    # DeepfakeBench aggregation: simple mean
    return float(probs.mean().item())




def _assemble_output(meta, frames, per_model_outputs: Dict[str, Dict],
                    weights: Dict[str, Optional[str]], timing_ms: Dict[str, float],
                    compute_hashes: bool = True) -> dict:
    """Assemble final JSON output following structured schema."""

    # Assemble frame list using precomputed timestamps
    frame_list = []
    for frame_info in frames:
        frame_list.append({
            "index": frame_info.index,
            "time": frame_info.timestamp_sec
        })

    # Assemble model results
    model_list = []
    for model_name, output in per_model_outputs.items():
        _, _, display_name = MODEL_ROUTES[model_name]

        # Video-level score aggregation
        video_score = _aggregate_frame_probs(output["prob"])

        # Per-frame scores
        frame_scores = []
        probs = output["prob"].cpu().detach().numpy()
        assert len(probs) == len(frames), f"Length mismatch: {len(probs)} probs vs {len(frames)} frames"

        for i, prob in enumerate(probs):
            frame_scores.append({
                "index": frames[i].index,
                "time": frames[i].timestamp_sec,
                "score": float(prob)
            })

        model_entry = {
            "name": display_name,
            "score": video_score,
            "frames": frame_scores
        }

        # Optional weight hash
        weights_path = weights.get(model_name)
        if weights_path and os.path.exists(weights_path) and compute_hashes:
            try:
                model_entry["weights_hash"] = hash_file(weights_path)
            except Exception as e:
                logger.warning(f"Could not hash {weights_path}: {e}")
                model_entry["weights_hash"] = None
        else:
            model_entry["weights_hash"] = None

        model_list.append(model_entry)

    # Final output structure
    result = {
        "video": {
            "path": meta.path,
            "fps": meta.fps,
            "frame_count": meta.frame_count,
            "duration_sec": meta.duration_sec,
            "width": meta.width,
            "height": meta.height
        },
        "frames": frame_list,
        "models": model_list,
        "timing_ms": timing_ms,
        "error": None
    }

    return result


def _assemble_empty_output(meta, stage: str, message: str) -> dict:
    """Assemble output for empty/failed videos."""
    return {
        "video": {
            "path": meta.path if meta else "unknown",
            "fps": meta.fps if meta else 0.0,
            "frame_count": meta.frame_count if meta else 0,
            "duration_sec": meta.duration_sec if meta else 0.0,
            "width": meta.width if meta else 0,
            "height": meta.height if meta else 0
        },
        "frames": [],
        "models": [],
        "timing_ms": {},
        "error": {
            "stage": stage,
            "message": message
        }
    }


def run(video_path: str, device: Optional[str] = None, models: Optional[List[str]] = None,
        weights: Optional[Dict[str, Optional[str]]] = None, compute_hashes: bool = True) -> dict:
    """
    Main inference pipeline following DeepfakeBench patterns.

    Args:
        video_path: Path to input video
        device: Target device ("cuda", "cpu", etc.)
        models: List of models to run (default: all)
        weights: Dict of model -> weight path
        compute_hashes: Whether to compute weight file hashes

    Returns:
        JSON-serializable dict with results
    """
    # Resolve configuration
    device = _select_device(device)
    models = models or ["xception", "spsl", "ucf"]
    weights = _resolve_weight_paths(weights)

    logger.info(f"Running inference on {video_path} with device={device}, models={models}")

    # Timing following DeepfakeBench patterns
    t0 = time.perf_counter()

    try:
        # 1. Video ingest following DFB preprocessing
        video_batch = process_video(video_path, predictor_path=None, required=False)
        t1 = time.perf_counter()

        # Handle empty video case
        if len(video_batch.crops_rgb) == 0:
            logger.warning(f"No frames/faces found in {video_path}")
            return _assemble_empty_output(video_batch.meta, "decode", "no frames/faces detected")

        logger.info(f"Extracted {len(video_batch.crops_rgb)} face crops")

        # 2. Preprocessing following DFB normalization
        batch_rgb_norm = preprocess_crops(video_batch.crops_rgb, device=device)
        t2 = time.perf_counter()

        # DeepfakeBench validation patterns
        assert batch_rgb_norm.dtype == torch.float32, f"Expected float32, got {batch_rgb_norm.dtype}"
        assert batch_rgb_norm.device.type == device.split(':')[0], f"Device mismatch: {batch_rgb_norm.device} vs {device}"
        logger.info(f"Preprocessed batch shape: {batch_rgb_norm.shape}")

        # 3. Load models following DFB patterns
        loaded_models = _load_models(device, weights, models)
        t3 = time.perf_counter()

        if not loaded_models:
            return _assemble_empty_output(video_batch.meta, "load_models", "no models loaded successfully")

        # 4. Per-model inference following DFB patterns
        per_model_outputs = {}
        for model_name, model in loaded_models.items():
            try:
                logger.info(f"Running inference with {model_name}")
                output = _infer_one(model_name, model, batch_rgb_norm)
                per_model_outputs[model_name] = output

                # Log aggregated score
                score = _aggregate_frame_probs(output["prob"])
                score_str = f"{score:.4f}" if score is not None else "None"
                logger.info(f"{model_name} video score: {score_str}")

            except Exception as e:
                logger.error(f"Inference failed for {model_name}: {e}")
                # Continue with other models

        t4 = time.perf_counter()

        # 5. Assemble output following structured schema
        timing_ms = {
            "decode_align": (t1 - t0) * 1000,
            "normalize": (t2 - t1) * 1000,
            "load_models": (t3 - t2) * 1000,
            "inference_total": (t4 - t3) * 1000,
        }

        result = _assemble_output(
            video_batch.meta, video_batch.frames, per_model_outputs,
            weights, timing_ms, compute_hashes
        )

        logger.info(f"Inference completed in {(t4-t0):.2f}s")
        return result

    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        return _assemble_empty_output(None, "internal", str(e))


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="DeepfakeBench-aligned video inference")
    parser.add_argument("video", help="Input video path")
    parser.add_argument("--device", help="Target device (cuda/cpu)")
    parser.add_argument("--models", help="Comma-separated list of models (xception,spsl,ucf)")
    parser.add_argument("--xception-weights", help="Path to Xception weights")
    parser.add_argument("--spsl-weights", help="Path to SPSL weights")
    parser.add_argument("--ucf-weights", help="Path to UCF weights")
    parser.add_argument("--no-hash", action="store_true", help="Skip weight file hashing")
    parser.add_argument("--json-out", help="Output JSON file path")
    parser.add_argument("--strict", action="store_true", help="Raise exceptions instead of error JSON")

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # Parse models list
    models = None
    if args.models:
        models = [m.strip() for m in args.models.split(",")]

    # Build weights dict
    weights = {
        "xception": args.xception_weights,
        "spsl": args.spsl_weights,
        "ucf": args.ucf_weights,
    }

    # Run inference
    try:
        result = run(
            args.video,
            device=args.device,
            models=models,
            weights=weights,
            compute_hashes=not args.no_hash
        )

        # Output result
        json_str = json.dumps(result, indent=2, ensure_ascii=False)

        if args.json_out:
            with open(args.json_out, 'w') as f:
                f.write(json_str)
            print(f"Results written to {args.json_out}")
        else:
            print(json_str)

    except Exception as e:
        if args.strict:
            raise
        else:
            error_result = {"error": {"stage": "cli", "message": str(e)}}
            print(json.dumps(error_result, indent=2))


if __name__ == "__main__":
    main()