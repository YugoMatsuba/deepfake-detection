# spsl_infer.py - DeepfakeBench-aligned SPSL model adapter
'''
This file implements SPSL (Spatial-Phase Shallow Learning) inference using exact
DeepfakeBench patterns from training/detectors/spsl_detector.py.

Original paper:
@inproceedings{liu2021spatial,
  title={Spatial-phase shallow learning: rethinking face forgery detection in frequency domain},
  author={Liu, Honggu and Li, Xiaodan and Zhou, Wenbo and Chen, Yuefeng and He, Yuan and Xue, Hui and Zhang, Weiming and Yu, Nenghai},
  booktitle={Proceedings of the IEEE/CVF conference on computer vision and pattern recognition},
  pages={772--781},
  year={2021}
}

Key implementation details copied from DeepfakeBench:
- Conv1 3→4 channel replacement with mean-tiling (lines 84-87)
- FFT phase extraction without amplitude (lines 135-148)
- Forward pass with 4-channel input (lines 97-99, 121-133)
'''

import logging
from typing import Dict, Optional

import torch
import torch.nn as nn
import torch.nn.functional as F

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
    # Handle empty batch case (robustness improvement over DeepfakeBench)
    if rgb_batch.size(0) == 0:
        return torch.empty(0, 1, 256, 256, dtype=rgb_batch.dtype, device=rgb_batch.device)

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


def _replace_conv1_with_4ch(model: torch.nn.Module, conv1_data: Optional[torch.Tensor] = None) -> None:
    """
    Replace Xception conv1 (3-ch) with 4-channel version using exact DeepfakeBench pattern.

    Based on spsl_detector.py lines 84-87:
    backbone.conv1 = nn.Conv2d(4, 32, 3, 2, 0, bias=False)
    avg_conv1_data = conv1_data.mean(dim=1, keepdim=True)  # average across RGB channels
    backbone.conv1.weight.data = avg_conv1_data.repeat(1, 4, 1, 1)  # repeat across 4 channels

    Args:
        model: Xception model with original 3-channel conv1
        conv1_data: Original conv1 weights [32, 3, 3, 3] from checkpoint, or None for default init
    """
    # Replace conv1 with 4-channel version (exact DFB pattern)
    model.conv1 = nn.Conv2d(4, 32, 3, 2, 0, bias=False)

    if conv1_data is not None:
        # Seed new conv1 with averaged/tiled original weights (DFB pattern)
        avg_conv1_data = conv1_data.mean(dim=1, keepdim=True)  # [32, 1, 3, 3]
        model.conv1.weight.data = avg_conv1_data.repeat(1, 4, 1, 1)  # [32, 4, 3, 3]
    # Else: use default PyTorch initialization for PR2 (no weights)


def load_spsl(weights_path: str, device: str) -> torch.nn.Module:
    """
    Load SPSL model with DeepfakeBench-compatible weights.

    Follows exact DeepfakeBench sequence from spsl_detector.py lines 64-89:
    1. Build Xception backbone with original config (inc=3)
    2. Load ImageNet pretrained weights and apply fixes
    3. Replace conv1 with 4-channel version and seed from original weights

    Args:
        weights_path: Path to .pth checkpoint file (unused in PR2)
        device: Device string ("cpu" or "cuda")

    Returns:
        SPSL model ready for 4-channel inference
    """
    # Exact config from DeepfakeBench spsl.yaml with inc=3 (not inc=4!)
    # The inc=4 in yaml is misleading - build starts with 3-ch then replaces conv1
    config = {"mode": "original", "num_classes": 2, "inc": 3, "dropout": False}

    # Build Xception backbone using exact DFB architecture from PR1
    model = Xception(config)

    # TODO: Weight loading sequence for PR4:
    # 1. map_location = map_location_for_device(device)
    # 2. state_dict = torch.load(weights_path, map_location=map_location)
    # 3. state_dict = strip_module_prefix(state_dict)
    # 4. state_dict = fix_pointwise_separable_convs(state_dict)
    # 5. state_dict = drop_fc_keys(state_dict)
    # 6. conv1_data = state_dict.pop('conv1.weight')  # [32, 3, 3, 3] - CRITICAL!
    # 7. model.load_state_dict(state_dict, strict=False)
    # 8. _replace_conv1_with_4ch(model, conv1_data)  # DFB pattern

    # For PR2: Replace conv1 without checkpoint weights
    _replace_conv1_with_4ch(model, conv1_data=None)

    model = ensure_eval(model).to(device)

    # Validation assertions (dev feedback)
    assert model.conv1.in_channels == 4, f"SPSL conv1 should have 4 input channels, got {model.conv1.in_channels}"
    assert model.conv1.bias is None, "SPSL conv1 should be bias-free"
    assert model.mode == "original", f"Expected mode='original', got {model.mode}"

    logger.info("Loaded SPSL with Xception backbone (conv1 replaced 3→4 channels)")
    return model


def predict_probs_spsl(model: torch.nn.Module, batch_rgb: torch.Tensor) -> Dict[str, torch.Tensor]:
    """
    Predict per-frame fake probabilities using SPSL model.

    Follows exact DeepfakeBench pattern from spsl_detector.py lines 121-133:
    - phase_fea = self.phase_without_amplitude(data_dict['image'])
    - features = self.features(data_dict, phase_fea)
    - pred = self.classifier(features)
    - prob = torch.softmax(pred, dim=1)[:, 1]
    - return {'cls': pred, 'prob': prob, 'feat': features}

    Args:
        model: Loaded SPSL model in eval mode
        batch_rgb: Normalized RGB tensor [N, 3, 256, 256] on model's device

    Returns:
        Dict with keys:
            - 'cls': logits [N, 2] on CPU
            - 'prob': fake probabilities [N] on CPU
            - 'feat': pooled embeddings [N, 2048] on CPU (mode="original")
    """
    if batch_rgb.numel() == 0:
        # Empty batch: return exact shapes per dev feedback
        return {
            'cls': torch.empty(0, 2, dtype=torch.float32),
            'prob': torch.empty(0, dtype=torch.float32),
            'feat': torch.empty(0, 2048, dtype=torch.float32)  # mode="original" → 2048
        }

    # Strict validation per dev feedback
    assert not model.training, "SPSL: model must be in eval() for inference"
    try:
        dev_model = next(model.parameters()).device
    except StopIteration:
        dev_model = batch_rgb.device  # Fallback for mock models with no parameters
    assert batch_rgb.device == dev_model, f"Batch on {batch_rgb.device}, model on {dev_model}"
    assert batch_rgb.dtype == torch.float32, f"SPSL: expected float32 tensor [N,3,256,256], got {batch_rgb.dtype}"

    with torch.no_grad():  # Dev feedback: explicit no_grad
        # Compute phase channel using exact DeepfakeBench method
        phase_channel = compute_phase_channel(batch_rgb)  # [N, 1, 256, 256]

        # Strict assertions per dev feedback
        assert phase_channel.shape == (batch_rgb.size(0), 1, 256, 256), f"Phase shape mismatch: expected {(batch_rgb.size(0), 1, 256, 256)}, got {phase_channel.shape}"
        assert phase_channel.dtype == batch_rgb.dtype, f"Phase dtype mismatch: {phase_channel.dtype} vs {batch_rgb.dtype}"
        assert phase_channel.device == batch_rgb.device, f"Phase device mismatch: {phase_channel.device} vs {batch_rgb.device}"

        # Concatenate RGB + Phase to create 4-channel input (DFB line 98)
        batch_4ch = torch.cat([batch_rgb, phase_channel], dim=1)  # [N, 4, 256, 256]

        # Forward through SPSL model (DFB lines 125-127)
        features = model.features(batch_4ch)  # May be 4D feature map
        logits = model.classifier(features)   # [N, 2] and sets model.last_emb

        # Dev feedback: Return 2048-D embedding, not 4D feature map
        emb = getattr(model, "last_emb", None)
        if emb is None:
            # Fallback: pool and flatten manually
            emb = F.adaptive_avg_pool2d(features, (1, 1)).flatten(1)
        assert emb.shape == (batch_rgb.size(0), 2048), f"Expected embedding [N, 2048], got {emb.shape}"  # mode="original"

        # Dev feedback: softmax column 1 only (DFB line 129)
        assert logits.shape[-1] == 2, f"Expected 2-class logits, got {logits.shape}"
        prob = torch.softmax(logits, dim=1)[:, 1]  # Exact DFB pattern

        # Return exact DeepfakeBench format with CPU tensors
        return {
            'cls': to_cpu(logits),
            'prob': to_cpu(prob),
            'feat': to_cpu(emb)  # 2048-D embedding, not 4D map
        }