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

        # NOTE: Real DeepfakeBench UCF uses Xception encoders with 256-dim shared features
        # (512 encoder features split into 256 specific + 256 shared). This skeleton uses
        # 32 features for simplicity. When implementing full architecture, change this to
        # match the actual encoder feature dimensions (256 for shared head).
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


def predict_probs_ucf(model: torch.nn.Module, batch_rgb: torch.Tensor, inference=True) -> Dict[str, torch.Tensor]:
    """
    Predict per-frame fake probabilities using UCF shared head only.

    Based on ucf_detector.py lines 237-241: inference=True uses head_sha only.
    Follows exact DeepfakeBench return format.

    Args:
        model: Loaded UCF model in eval mode
        batch_rgb: Normalized RGB tensor [N, 3, 256, 256] on model's device
        inference: If True, use shared head path only (default True)

    Returns:
        Dict with keys:
            - 'cls': shared head logits [N, 2] on CPU
            - 'prob': fake probabilities [N] on CPU
            - 'feat': shared features [N, feat_dim] on CPU
    """
    if batch_rgb.numel() == 0:
        feat_dim = getattr(model.head_sha, "in_features", 32)
        return {
            'cls': torch.empty(0, 2, dtype=torch.float32),
            'prob': torch.empty(0, dtype=torch.float32),
            'feat': torch.empty(0, feat_dim, dtype=torch.float32)
        }

    # Defensive validation
    assert not model.training, "Model should be in eval mode for inference"
    dev_model = next(model.parameters()).device
    assert batch_rgb.device == dev_model, f"Batch on {batch_rgb.device}, model on {dev_model}"
    assert batch_rgb.dtype == torch.float32, f"Expected float32 normalized input, got {batch_rgb.dtype}"

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

            # Return DeepfakeBench-format dictionary
            return {
                'cls': to_cpu(out_sha),
                'prob': to_cpu(probs),
                'feat': to_cpu(shared_features)
            }
        else:
            raise NotImplementedError("UCF training mode not implemented in adapter")