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

# Default weight file paths (relative to ml/ directory - working directory)
# Can be overridden via environment variables
DEFAULT_WEIGHTS = {
    "xception": os.getenv("XCEPTION_WEIGHTS", "weights/xception_best.pth"),
    "spsl":     os.getenv("SPSL_WEIGHTS",     "weights/spsl_best.pth"),
    "ucf":      os.getenv("UCF_WEIGHTS",      "weights/ucf_best.pth"),
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
