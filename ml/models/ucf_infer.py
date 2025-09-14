# ucf_infer.py - DeepfakeBench-aligned UCF model adapter

import logging
from typing import Dict, Any

import torch
import torch.nn as nn

from .utils import (
    map_location_for_device,
    strip_module_prefix,
    fix_pointwise_separable_convs,
    drop_fc_keys,
    softmax_fake,
    inference_guard,
    to_cpu,
    ensure_eval
)

logger = logging.getLogger(__name__)


# TODO: This is a skeleton implementation
class UCFBackboneSkeleton(nn.Module):
    """Skeleton UCF backbone for interface compatibility."""

    def __init__(self, config: Dict[str, Any]):
        super(UCFBackboneSkeleton, self).__init__()
        self.num_classes = config["num_classes"]
        self.mode = config["mode"]  # Should be 'adjust_channel'

        # Simplified placeholder - real UCF has dual Xception encoders
        self.shared_features = nn.Sequential(
            nn.Conv2d(config["inc"], 32, 3, 2, 0, bias=False),
            nn.BatchNorm2d(32), nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d((1, 1)), nn.Flatten()
        )
        # Shared head for inference (head_sha in DeepfakeBench)
        self.head_sha = nn.Linear(32, self.num_classes)

    def features_shared(self, input_tensor: torch.Tensor) -> torch.Tensor:
        return self.shared_features(input_tensor)

    def forward_shared_head(self, shared_features: torch.Tensor) -> torch.Tensor:
        return self.head_sha(shared_features)


def load_ucf(weights_path: str, device: str) -> torch.nn.Module:
    """Load UCF model with DeepfakeBench-compatible weights (skeleton)."""
    config = {
        "mode": "adjust_channel",  # UCF uses adjust_channel mode
        "num_classes": 2, "inc": 3, "dropout": False
    }
    model = UCFBackboneSkeleton(config)
    model = ensure_eval(model).to(device)
    logger.warning(f"Using skeleton UCF model - replace with full implementation")
    return model


def predict_probs_ucf(model: torch.nn.Module, batch_rgb: torch.Tensor, inference=True) -> tuple[torch.Tensor, torch.Tensor]:
    """
    Predict per-frame fake probabilities using UCF shared head only.

    Based on ucf_detector.py lines 237-241: inference=True uses head_sha only.

    Returns:
        Tuple of (logits[N, 2], probs[N]) - shared head logits and fake probabilities on CPU
    """
    if batch_rgb.numel() == 0:
        empty_logits = torch.empty(0, 2, dtype=torch.float32)
        empty_probs = torch.empty(0, dtype=torch.float32)
        return empty_logits, empty_probs

    with inference_guard():
        if inference:
            # UCF inference path: shared features and shared head only
            shared_features = model.features_shared(batch_rgb)
            out_sha = model.forward_shared_head(shared_features)  # [N, 2] logits
            probs = softmax_fake(out_sha)  # [N] fake probabilities

            # Runtime hygiene checks
            assert out_sha.shape[1] == 2, f"UCF logits should be [N, 2], got {out_sha.shape}"
            assert probs.ndim == 1 and probs.shape[0] == out_sha.shape[0]
            assert not out_sha.requires_grad and not probs.requires_grad
            assert out_sha.device == batch_rgb.device

            return to_cpu(out_sha), to_cpu(probs)
        else:
            raise NotImplementedError("UCF training mode not implemented in adapter")