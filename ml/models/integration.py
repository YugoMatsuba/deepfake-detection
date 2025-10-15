# integration.py - Integration constants for deepfake detection runner
"""
Centralized constants and registry for model integration.

Defines:
- DEFAULT_WEIGHTS: Default checkpoint paths with env var overrides
- AGGREGATION: Frame-to-clip aggregation method
- MODEL_REGISTRY: Maps model names to (loader_fn, predict_fn, default_weights_path)

Usage in runner:
    from ml.models.integration import MODEL_REGISTRY, DEFAULT_WEIGHTS, AGGREGATION

    for model_name in args.models:
        loader_fn, predict_fn, default_path = MODEL_REGISTRY[model_name]
        weights_path = args.weights_override or default_path
        model = loader_fn(weights_path, device)
        # ... inference ...
        clip_score = aggregate_frames(frame_probs, method=AGGREGATION)
"""

import os

# Default weight file paths (repo-relative) with env overrides.
# Priority: per-model env var → ML_WEIGHTS_DIR → repo default location.
from ml.constants import get_weights_dir, DEFAULT_WEIGHTS as DEFAULT_WEIGHT_FILENAMES


def _default_weight_path(model_key: str, env_var: str) -> str:
    env_override = os.getenv(env_var)
    if env_override:
        return env_override

    weights_dir = get_weights_dir()
    filename = DEFAULT_WEIGHT_FILENAMES[model_key]
    return os.path.join(weights_dir, filename)


DEFAULT_WEIGHTS = {
    "xception": _default_weight_path("xception", "XCEPTION_WEIGHTS"),
    "spsl":     _default_weight_path("spsl", "SPSL_WEIGHTS"),
    "ucf":      _default_weight_path("ucf", "UCF_WEIGHTS"),
}

# Aggregation method for frame-level probabilities → clip-level score
# Runner computes: clip_score = mean(frame_probs)
AGGREGATION = "mean"

# Model registry: name → (loader_fn, predict_fn, default_weights_path)
# Import adapters
from .xception_infer import load_xception, predict_probs_xception
from .spsl_infer     import load_spsl,     predict_probs_spsl
from .ucf_infer      import load_ucf,      predict_probs_ucf

MODEL_REGISTRY = {
    "xception": (load_xception, predict_probs_xception, DEFAULT_WEIGHTS["xception"]),
    "spsl":     (load_spsl,     predict_probs_spsl,     DEFAULT_WEIGHTS["spsl"]),
    "ucf":      (load_ucf,      predict_probs_ucf,      DEFAULT_WEIGHTS["ucf"]),
}
