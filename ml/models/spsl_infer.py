# spsl_infer.py - DeepfakeBench-aligned SPSL model adapter

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


def compute_phase_channel(rgb_batch: torch.Tensor) -> torch.Tensor:
    """
    Compute phase channel from RGB batch using exact DeepfakeBench FFT method.

    Based on training/detectors/spsl_detector.py lines 135-148.
    This is the exact "phase_without_amplitude" implementation.

    Args:
        rgb_batch: Normalized RGB tensor [N, 3, 256, 256]

    Returns:
        Phase channel tensor [N, 1, 256, 256]
    """
    # Convert to grayscale by averaging RGB channels
    # Note: This happens on normalized RGB input (post ToTensor+Normalize)
    gray_img = torch.mean(rgb_batch, dim=1, keepdim=True)  # [N, 1, 256, 256]

    # Compute the DFT of the input signal (2D FFT)
    X = torch.fft.fftn(gray_img, dim=(-1, -2))

    # Extract the phase information from the DFT
    phase_spectrum = torch.angle(X)

    # Create a new complex spectrum with phase information and zero magnitude
    reconstructed_X = torch.exp(1j * phase_spectrum)

    # Use the IDFT to obtain the reconstructed signal
    reconstructed_x = torch.real(torch.fft.ifftn(reconstructed_X, dim=(-1, -2)))

    return reconstructed_x


# TODO: This is a skeleton implementation
# For real SPSL inference, need complete Xception architecture with 4-channel conv1
class SPSLBackboneSkeleton(nn.Module):
    """Skeleton SPSL backbone for interface compatibility."""

    def __init__(self, config: Dict[str, Any]):
        super(SPSLBackboneSkeleton, self).__init__()
        self.num_classes = config["num_classes"]
        self.mode = config["mode"]

        # 4-channel conv1 for RGB + Phase input
        self.conv1 = nn.Conv2d(4, 32, 3, 2, 0, bias=False)
        self.features_net = nn.Sequential(
            nn.BatchNorm2d(32), nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d((1, 1)), nn.Flatten()
        )
        self.last_linear = nn.Linear(32, self.num_classes)

    def features(self, input_tensor: torch.Tensor) -> torch.Tensor:
        x = self.conv1(input_tensor)
        return self.features_net(x)

    def classifier(self, features: torch.Tensor) -> torch.Tensor:
        return self.last_linear(features)


def load_spsl(weights_path: str, device: str) -> torch.nn.Module:
    """
    Load SPSL model with DeepfakeBench-compatible weights (skeleton).

    Follows exact DeepfakeBench sequence from spsl_detector.py lines 77-88.
    """
    config = {"mode": "original", "num_classes": 2, "inc": 3, "dropout": False}  # Start with 3-ch
    model = SPSLBackboneSkeleton(config)

    # TODO: Real weight loading sequence:
    # 1. map_location = map_location_for_device(device)
    # 2. state_dict = torch.load(weights_path, map_location=map_location)
    # 3. state_dict = strip_module_prefix(state_dict)
    # 4. state_dict = fix_pointwise_separable_convs(state_dict)
    # 5. state_dict = drop_fc_keys(state_dict)
    # 6. conv1_data = state_dict.pop('conv1.weight')  # [32, 3, 3, 3] - CRITICAL!
    # 7. model.load_state_dict(state_dict, strict=False)
    # 8. model.conv1 = nn.Conv2d(4, 32, 3, 2, 0, bias=False)  # Replace with 4-ch
    # 9. avg_conv1_data = conv1_data.mean(dim=1, keepdim=True)  # [32, 1, 3, 3]
    # 10. model.conv1.weight.data = avg_conv1_data.repeat(1, 4, 1, 1)  # [32, 4, 3, 3]

    # For skeleton: manually create 4-channel conv1
    import torch.nn as nn
    model.conv1 = nn.Conv2d(4, 32, 3, 2, 0, bias=False)

    model = ensure_eval(model).to(device)

    # Assertion checks
    assert model.conv1.in_channels == 4, f"SPSL conv1 should have 4 input channels, got {model.conv1.in_channels}"

    logger.warning(f"Using skeleton SPSL model - replace with full implementation")
    return model


def predict_probs_spsl(model: torch.nn.Module, batch_rgb: torch.Tensor) -> Dict[str, torch.Tensor]:
    """
    Predict per-frame fake probabilities using SPSL model.

    Follows exact DeepfakeBench return format matching other detectors.

    Args:
        model: Loaded SPSL model in eval mode
        batch_rgb: Normalized RGB tensor [N, 3, 256, 256] on model's device

    Returns:
        Dict with keys:
            - 'cls': logits [N, 2] on CPU
            - 'prob': fake probabilities [N] on CPU
            - 'feat': features [N, feat_dim] on CPU
    """
    if batch_rgb.numel() == 0:
        return {
            'cls': torch.empty(0, 2, dtype=torch.float32),
            'prob': torch.empty(0, dtype=torch.float32),
            'feat': torch.empty(0, 512, dtype=torch.float32)  # Typical feature dim
        }

    with inference_guard():
        # Compute phase channel using exact DeepfakeBench method
        phase_channel = compute_phase_channel(batch_rgb)  # [N, 1, 256, 256]

        # Validation checks
        assert phase_channel.dtype == batch_rgb.dtype, f"Phase dtype mismatch: {phase_channel.dtype} vs {batch_rgb.dtype}"
        assert phase_channel.shape[1] == 1, f"Phase channel should be 1, got {phase_channel.shape[1]}"

        # Concatenate RGB + Phase to create 4-channel input
        batch_4ch = torch.cat([batch_rgb, phase_channel], dim=1)  # [N, 4, 256, 256]

        # Forward through SPSL model
        features = model.features(batch_4ch)
        logits = model.classifier(features)  # [N, 2]
        probs = softmax_fake(logits)  # [N]

        # Runtime hygiene checks
        assert not logits.requires_grad and not probs.requires_grad
        assert logits.device == batch_rgb.device

        # Return DeepfakeBench-format dictionary
        return {
            'cls': to_cpu(logits),
            'prob': to_cpu(probs),
            'feat': to_cpu(features)
        }