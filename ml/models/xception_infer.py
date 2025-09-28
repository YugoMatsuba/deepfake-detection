# xception_infer.py - DeepfakeBench-aligned Xception model adapter

import logging
from typing import Dict

import torch

from .xception_arch import Xception
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


def load_xception(weights_path: str, device: str) -> torch.nn.Module:
    """
    Load Xception model with DeepfakeBench-compatible weights.

    Uses exact DeepfakeBench Xception architecture from training/networks/xception.py.
    Instantiation follows exact pattern from xception_detector.py build_backbone().

    Args:
        weights_path: Path to .pth checkpoint file
        device: Device string ("cpu" or "cuda")

    Returns:
        Loaded model in eval mode
    """
    # Exact config from DeepfakeBench xception.yaml backbone_config
    model_config = {
        "mode": "original",
        "num_classes": 2,
        "inc": 3,
        "dropout": False
    }

    # Instantiate using real DeepfakeBench Xception architecture
    model = Xception(model_config)

    # TODO: Weight loading will be implemented in PR4
    # Following exact pattern from xception_detector.py lines 69-74:
    # state_dict = torch.load(weights_path)
    # for name, weights in state_dict.items():
    #     if 'pointwise' in name:
    #         state_dict[name] = weights.unsqueeze(-1).unsqueeze(-1)
    # state_dict = {k:v for k, v in state_dict.items() if 'fc' not in k}
    # model.load_state_dict(state_dict, False)

    model = ensure_eval(model).to(device)

    # Validate architecture matches expected DeepfakeBench structure
    assert model.conv1.in_channels == 3, f"Xception conv1 should have 3 input channels, got {model.conv1.in_channels}"
    assert hasattr(model, 'features'), "Xception should have features() method"
    assert hasattr(model, 'classifier'), "Xception should have classifier() method"
    assert model.num_classes == 2, f"Expected 2 classes, got {model.num_classes}"

    logger.info("Loaded DeepfakeBench Xception architecture (no weights loaded yet)")
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
        pred = model.classifier(features)       # [N, 2] logits
        prob = softmax_fake(pred)               # [N] fake probabilities (softmax[:,1])

        # Ensure features are properly flattened for output
        if len(features.shape) == 4:
            # If features are still [N, C, H, W], they need to be pooled and flattened
            # This should normally be handled by classifier(), but ensure consistency
            import torch.nn.functional as F
            features = F.adaptive_avg_pool2d(features, (1, 1))
            features = features.view(features.size(0), -1)

        # Return exact DeepfakeBench format
        return {
            'cls': to_cpu(pred),
            'prob': to_cpu(prob),
            'feat': to_cpu(features)
        }