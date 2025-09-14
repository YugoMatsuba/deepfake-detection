# xception_infer.py - DeepfakeBench-aligned Xception model adapter

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
# For a complete working adapter, we need to copy the full Xception architecture
# from DeepfakeBench's training/networks/xception.py including all Block classes,
# separable convolutions, and exact layer configurations.

class XceptionBackboneSkeleton(nn.Module):
    """
    Skeleton Xception backbone for interface compatibility.

    NOTE: This is incomplete! For real inference, copy the complete
    architecture from DeepfakeBench training/networks/xception.py
    """

    def __init__(self, config: Dict[str, Any]):
        super(XceptionBackboneSkeleton, self).__init__()
        self.num_classes = config["num_classes"]
        self.mode = config["mode"]

        # Match DeepfakeBench Xception structure with explicit layers
        self.conv1 = nn.Conv2d(config["inc"], 32, 3, 2, 0, bias=False)
        self.bn1 = nn.BatchNorm2d(32)
        self.relu = nn.ReLU(inplace=True)
        self.pool = nn.AdaptiveAvgPool2d((1, 1))
        self.flatten = nn.Flatten()

        # NOTE: Real DeepfakeBench Xception has 2048 features (or 512 with adjust_channel).
        # This skeleton uses 32 features for simplicity. When implementing full architecture,
        # change this to match the actual feature dimensions from the loaded weights.
        self.last_linear = nn.Linear(32, self.num_classes)

    def features(self, input_tensor: torch.Tensor) -> torch.Tensor:
        """Extract features - using explicit layers."""
        x = self.conv1(input_tensor)
        x = self.bn1(x)
        x = self.relu(x)
        x = self.pool(x)
        x = self.flatten(x)
        return x

    def classifier(self, features: torch.Tensor) -> torch.Tensor:
        """Classification head - simplified version."""
        return self.last_linear(features)


def load_xception(weights_path: str, device: str) -> torch.nn.Module:
    """
    Load Xception model with DeepfakeBench-compatible weights.

    WARNING: This is a skeleton implementation for interface compatibility.
    For real model loading, implement complete XceptionBackbone with
    full architecture from DeepfakeBench training/networks/xception.py

    Args:
        weights_path: Path to .pth checkpoint file
        device: Device string ("cpu" or "cuda")

    Returns:
        Loaded model in eval mode (currently skeleton)
    """
    config = {
        "mode": "original",
        "num_classes": 2,
        "inc": 3,
        "dropout": False
    }

    # Use skeleton for now - replace with full XceptionBackbone
    model = XceptionBackboneSkeleton(config)

    # Note: Actual weight loading would happen here with real architecture
    # map_location = map_location_for_device(device)
    # state_dict = torch.load(weights_path, map_location=map_location)
    # state_dict = strip_module_prefix(state_dict)
    # state_dict = fix_pointwise_separable_convs(state_dict)
    # state_dict = drop_fc_keys(state_dict)
    # model.load_state_dict(state_dict, strict=False)

    model = ensure_eval(model).to(device)

    # Assertion checks
    assert model.conv1.in_channels == 3, f"Xception conv1 should have 3 input channels, got {model.conv1.in_channels}"

    logger.warning(f"Using skeleton Xception model - replace with full implementation")
    return model


def predict_probs_xception(model: torch.nn.Module, batch: torch.Tensor) -> Dict[str, torch.Tensor]:
    """
    Predict per-frame fake probabilities using Xception model.

    Follows exact DeepfakeBench return format from xception_detector.py lines 108-117.

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
        feat_dim = getattr(model.last_linear, "in_features", 32)
        return {
            'cls': torch.empty(0, 2, dtype=torch.float32),
            'prob': torch.empty(0, dtype=torch.float32),
            'feat': torch.empty(0, feat_dim, dtype=torch.float32)
        }

    # Defensive validation
    assert not model.training, "Model should be in eval mode for inference"
    dev_model = next(model.parameters()).device
    assert batch.device == dev_model, f"Batch on {batch.device}, model on {dev_model}"
    assert batch.dtype == torch.float32, f"Expected float32 normalized input, got {batch.dtype}"

    with inference_guard():
        features = model.features(batch)  # [N, feat_dim]
        logits = model.classifier(features)  # [N, 2]
        probs = softmax_fake(logits)  # [N]

        # Return DeepfakeBench-format dictionary
        return {
            'cls': to_cpu(logits),
            'prob': to_cpu(probs),
            'feat': to_cpu(features)
        }