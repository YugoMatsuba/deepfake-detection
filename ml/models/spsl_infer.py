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
import os
from typing import Dict, Optional

import torch
import torch.nn as nn
import torch.nn.functional as F

from .xception_arch import Xception
from .utils import (
    load_dfb_checkpoint,
    _spsl_replace_conv1_with_4ch,
    softmax_fake,
    inference_guard,
    to_cpu,
    ensure_eval
)

# Re-export for tests that import from spsl_infer
_replace_conv1_with_4ch = _spsl_replace_conv1_with_4ch

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


# NOTE: _replace_conv1_with_4ch removed - now handled by centralized loader in utils.py


def load_spsl(weights_path: str, device: str) -> torch.nn.Module:
    """
    Load SPSL model with DeepfakeBench-compatible weights.

    Follows EXACT DeepfakeBench sequence from spsl_detector.py lines 64-89:
    1. Build Xception backbone with inc=3 (NOT inc=4!)
    2. Load pretrained weights and fix pointwise/drop fc keys
    3. POP conv1.weight from state_dict BEFORE loading
    4. load_state_dict with strict=False
    5. Replace conv1 with 4-ch version and seed from popped weights

    Args:
        weights_path: Path to .pth checkpoint file (ImageNet xception-b5690688.pth)
        device: Device string ("cpu" or "cuda")

    Returns:
        SPSL model ready for 4-channel inference, with weights_hash stored as model._weights_hash
    """
    # Exact config from DeepfakeBench spsl.yaml
    # NOTE: spsl.yaml says inc=4, but build_backbone builds with inc=3 then replaces conv1!
    config = {"mode": "original", "num_classes": 2, "inc": 3, "dropout": False}

    # Build Xception backbone using exact DFB architecture from PR1
    model = Xception(config)

    # PR4: Load weights using centralized DFB checkpoint loader (if path provided)
    # CRITICAL: For SPSL, the loader handles conv1 popping and 4-ch replacement
    # Follows spsl_detector.py lines 71-88
    if weights_path and os.path.isfile(weights_path):
        report = load_dfb_checkpoint(
            model,
            weights_path,
            device=device,
            arch="spsl",
            expected_num_classes=2
        )
        # Store weights hash for provenance (used by runner.py for JSON output)
        model._weights_hash = report['weights_hash']
        seeded_msg = "seeded from checkpoint" if report['spsl_conv1_seeded'] else "default init (no conv1 in ckpt)"
        logger.info(f"Loaded SPSL with {report['keys_loaded']}/{report['keys_total']} backbone weights, conv1 4-ch {seeded_msg}")
    else:
        # No weights loaded (for testing)
        logger.info("SPSL: no weights_path; build 3-ch then replace conv1→4-ch with default init")
        _spsl_replace_conv1_with_4ch(model, conv1_data=None)
        model._weights_hash = ""

    # Move to device and set eval mode
    model = ensure_eval(model).to(device)

    # Validation assertions
    assert model.conv1.in_channels == 4, f"SPSL conv1 should have 4 input channels after replacement, got {model.conv1.in_channels}"
    assert model.conv1.bias is None, "SPSL conv1 should be bias-free"
    assert model.mode == "original", f"Expected mode='original', got {model.mode}"

    # PR5: Validate 2-class head with probe forward pass
    with torch.no_grad():
        _probe = torch.zeros(1, 4, 256, 256, device=device, dtype=torch.float32)  # 4-ch for SPSL
        _feat = model.features(_probe)
        _logits = model.classifier(_feat)
        assert _logits.shape[-1] == 2, (
            f"SPSL head must output 2 classes, got {_logits.shape[-1]}."
        )

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

        # Return 2048-D embedding from last_emb (set by classifier)
        emb = getattr(model, "last_emb", None)
        if emb is None:
            # Fallback: pool and flatten manually
            emb = F.adaptive_avg_pool2d(features, (1, 1)).flatten(1)
        assert emb.shape == (batch_rgb.size(0), 2048), f"Expected embedding [N, 2048], got {emb.shape}"  # mode="original"

        # Use softmax_fake helper for consistency (exact DFB pattern)
        prob = softmax_fake(logits)  # softmax[:,1] for "fake" class

        # PR5: Runtime validation guards
        assert prob.ndim == 1, f"prob must be 1-D, got shape {tuple(prob.shape)}"
        assert torch.isfinite(prob).all(), "prob contains non-finite values"
        assert (prob >= 0).all() and (prob <= 1).all(), "prob outside [0,1]"

        # Return exact DeepfakeBench format with CPU tensors
        return {
            'cls': to_cpu(logits),
            'prob': to_cpu(prob),
            'feat': to_cpu(emb)  # 2048-D embedding, not 4D map
        }