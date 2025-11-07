# xception_infer.py - DeepfakeBench-aligned Xception model adapter

import logging
import os
from typing import Dict

import torch

from .xception_arch import Xception
from .utils import (
    load_dfb_checkpoint,
    softmax_fake,
    inference_guard,
    to_cpu,
    ensure_eval
)

logger = logging.getLogger(__name__)


def load_xception(weights_path: str, device: str) -> torch.nn.Module:
    """
    Load Xception model with DeepfakeBench-compatible weights.

    Uses exact DeepfakeBench Xception architecture from training/networks/xception.py.
    Follows exact loading pattern from xception_detector.py build_backbone() lines 63-76.

    Args:
        weights_path: Path to .pth checkpoint file (ImageNet pretrained xception-b5690688.pth)
        device: Device string ("cpu" or "cuda")

    Returns:
        Loaded model in eval mode, with weights_hash stored as model._weights_hash
    """
    # Exact config from DeepfakeBench xception.yaml backbone_config
    model_config = {
        "mode": "original",
        "num_classes": 2,
        "inc": 3,
        "dropout": False
    }

    # Instantiate using exact DeepfakeBench Xception architecture from PR1
    model = Xception(model_config)

    # PR4: Load weights using centralized DFB checkpoint loader
    # Follows xception_detector.py lines 69-75
    # FAIL FAST: Production should never run with untrained weights
    if not weights_path:
        raise ValueError("Xception: weights_path is required but not provided")

    if not os.path.isfile(weights_path):
        raise FileNotFoundError(f"Xception weights not found: {weights_path}")

    report = load_dfb_checkpoint(
        model,
        weights_path,
        device=device,
        arch="xception",
        expected_num_classes=2
    )
    # Store weights hash for provenance (used by runner.py for JSON output)
    model._weights_hash = report['weights_hash']
    logger.info(f"Loaded Xception with {report['keys_loaded']}/{report['keys_total']} backbone weights")

    # Move to device and set eval mode
    model = ensure_eval(model).to(device)

    # Validate architecture matches expected DeepfakeBench structure
    assert model.conv1.in_channels == 3, f"Xception conv1 should have 3 input channels, got {model.conv1.in_channels}"
    assert hasattr(model, 'features'), "Xception should have features() method"
    assert hasattr(model, 'classifier'), "Xception should have classifier() method"
    assert model.num_classes == 2, f"Expected 2 classes, got {model.num_classes}"

    # PR5: Validate 2-class head with probe forward pass
    with torch.no_grad():
        _probe = torch.zeros(1, 3, 256, 256, device=device, dtype=torch.float32)
        _feat = model.features(_probe)
        _logits = model.classifier(_feat)
        assert _logits.shape[-1] == 2, (
            f"Xception head must output 2 classes, got {_logits.shape[-1]}. "
            f"Check your checkpoint or num_classes in config."
        )

    return model


def predict_probs_xception(model: torch.nn.Module, batch: torch.Tensor) -> Dict[str, torch.Tensor]:
    """
    Predict per-frame fake probabilities using Xception model.

    Follows exact DeepfakeBench pattern from xception_detector.py lines 108-117:
    - features = backbone.features(data_dict['image'])
    - pred = backbone.classifier(features)
    - prob = torch.softmax(pred, dim=1)[:, 1]
    - return {'cls': pred, 'prob': prob, 'feat': features}

    Args:
        model: Loaded Xception model in eval mode
        batch: Normalized tensor [N, 3, 256, 256] on model's device

    Returns:
        Dict with keys:
            - 'cls': logits [N, 2] on CPU
            - 'prob': fake probabilities [N] on CPU
            - 'feat': features [N, feat_dim] on CPU
    """
    if batch.numel() == 0:
        # Determine feature dimensions for empty batch
        # Real Xception: 2048 for original mode, 512 for adjust_channel mode
        feat_dim = 2048 if model.mode == "original" else 512
        return {
            'cls': torch.empty(0, 2, dtype=torch.float32),
            'prob': torch.empty(0, dtype=torch.float32),
            'feat': torch.empty(0, feat_dim, dtype=torch.float32)
        }

    # Defensive validation
    assert not model.training, "Model should be in eval mode for inference"
    try:
        dev_model = next(model.parameters()).device
    except StopIteration:
        dev_model = batch.device  # Fallback for mock models with no parameters
    assert batch.device == dev_model, f"Batch on {batch.device}, model on {dev_model}"
    assert batch.dtype == torch.float32, f"Expected float32 normalized input, got {batch.dtype}"

    with inference_guard():
        # Use exact DeepfakeBench pattern from xception_detector.py
        features = model.features(batch)        # [N, C, H, W] or [N, feat_dim] after pooling
        pred = model.classifier(features)       # [N, 2] logits, sets model.last_emb
        prob = softmax_fake(pred)               # [N] fake probabilities (softmax[:,1])

        # PR5: Runtime validation guards
        assert prob.ndim == 1, f"prob must be 1-D, got shape {tuple(prob.shape)}"
        assert torch.isfinite(prob).all(), "prob contains non-finite values"
        assert (prob >= 0).all() and (prob <= 1).all(), "prob outside [0,1]"

        # Use last_emb for consistency with SPSL/UCF adapters
        # Xception.classifier() sets this after pooling and flattening
        emb = getattr(model, "last_emb", None)
        if emb is None:
            # Fallback: pool and flatten manually if last_emb not set
            if features.ndim == 4:
                import torch.nn.functional as F
                emb = F.adaptive_avg_pool2d(features, (1, 1)).flatten(1)
            else:
                emb = features

        # Return exact DeepfakeBench format
        return {
            'cls': to_cpu(pred),
            'prob': to_cpu(prob),
            'feat': to_cpu(emb)
        }