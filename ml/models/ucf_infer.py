# ucf_infer.py - DeepfakeBench-aligned UCF model adapter
"""
UCF (Uncovering Common Features) inference adapter using exact DeepfakeBench architecture.

This adapter implements the inference-only path from DeepfakeBench's UCFDetector,
using dual Xception encoders with shared-head classification.

Reference:
DeepfakeBench/training/detectors/ucf_detector.py lines 237-264 (inference=True branch)
"""

import logging
import os
from typing import Dict, Any

import torch
import torch.nn as nn

from .ucf_arch import UCFDetector
from .utils import (
    load_dfb_checkpoint,
    softmax_fake,
    inference_guard,
    to_cpu,
    ensure_eval
)

logger = logging.getLogger(__name__)


def load_ucf(weights_path: str, device: str) -> torch.nn.Module:
    """
    Load UCF model with DeepfakeBench-compatible dual-encoder architecture.

    Builds two Xception backbones with mode="adjust_channel" and shared-head inference.
    Follows exact DeepfakeBench ucf.yaml configuration and ucf_detector.py architecture.

    Args:
        weights_path: Path to .pth checkpoint file (ImageNet xception-b5690688.pth)
        device: Device string ("cpu" or "cuda")

    Returns:
        UCF model in eval mode ready for inference, with weights_hash stored as model._weights_hash
    """
    # Exact config from DeepfakeBench ucf.yaml
    config = {
        "mode": "adjust_channel",       # Reduces Xception output to 512D
        "num_classes": 2,               # Binary classification
        "inc": 3,                       # RGB input channels
        "dropout": False,               # No dropout in backbone
        "encoder_feat_dim": 512,        # Feature dimension (adjust_channel mode)
        "specific_task_number": 5,      # FF++ has 5 forgery types (for weight compatibility)
    }

    # Build UCF detector with dual Xception encoders
    model = UCFDetector(config)

    # PR4: Load weights using centralized DFB checkpoint loader
    # Follows ucf_detector.py lines 105-111 (build_backbone)
    # NOTE: UCF loads trained detector weights (not ImageNet) with both encoders + heads
    # FAIL FAST: Production should never run with untrained weights
    if not weights_path:
        raise ValueError("UCF: weights_path is required but not provided")

    if not os.path.isfile(weights_path):
        raise FileNotFoundError(f"UCF weights not found: {weights_path}")

    report = load_dfb_checkpoint(
        model,
        weights_path,
        device=device,
        arch="ucf",
        expected_num_classes=2
    )
    # Store weights hash for provenance (used by runner.py for JSON output)
    model._weights_hash = report['weights_hash']
    # Log detailed per-encoder loading info
    logger.info(
        f"Loaded UCF from {weights_path} (sha256={report['weights_hash'][:16]}...), "
        f"total keys: {report['keys_loaded']}/{report['keys_total']*2} across dual encoders, "
        f"pointwise fixes: {report['fixed_pointwise_count']}"
    )
    if report['notes']:
        logger.debug(f"UCF loading details: {report['notes']}")

    # Move to device and set eval mode
    model = ensure_eval(model).to(device)

    # Validation assertions (fail fast on architecture mismatches)
    assert not model.training, "UCF model must be in eval mode for inference"
    assert model.encoder_feat_dim == 512, f"Expected encoder_feat_dim=512 (adjust_channel), got {model.encoder_feat_dim}"
    assert model.half_fingerprint_dim == 256, f"Expected half_fingerprint_dim=256, got {model.half_fingerprint_dim}"
    assert model.head_sha.mlp[-1].out_features == 2, f"Expected 2-class shared head, got {model.head_sha.mlp[-1].out_features}"
    assert model.head_spe.mlp[-1].out_features == 5, f"Expected 5-class specific head, got {model.head_spe.mlp[-1].out_features}"
    assert hasattr(model, 'shared_feat_dim'), "Model must expose shared_feat_dim for adapter"

    # Validate architectural components exist
    assert hasattr(model, 'block_spe'), "Model must have block_spe for weight compatibility"
    assert hasattr(model, 'block_sha'), "Model must have block_sha"
    assert hasattr(model, 'head_spe'), "Model must have head_spe for weight compatibility"
    assert hasattr(model, 'head_sha'), "Model must have head_sha"

    # Validate backbone configurations
    for encoder_name in ['encoder_f', 'encoder_c']:
        encoder = getattr(model, encoder_name)
        assert encoder.mode == "adjust_channel", f"{encoder_name} should use adjust_channel mode, got {encoder.mode}"
        assert encoder.num_classes == 2, f"{encoder_name} should have 2 classes, got {encoder.num_classes}"

    return model


def predict_probs_ucf(model: torch.nn.Module, batch_rgb: torch.Tensor, inference=True) -> Dict[str, torch.Tensor]:
    """
    Predict per-frame fake probabilities using UCF shared head only.

    Follows exact DeepfakeBench pattern from ucf_detector.py lines 237-264.
    Uses forgery encoder + shared-head inference path only.

    Args:
        model: Loaded UCF model in eval mode
        batch_rgb: Normalized RGB tensor [N, 3, 256, 256] on model's device
        inference: If True, use shared head path only (default True)

    Returns:
        Dict with keys:
            - 'cls': shared head logits [N, 2] on CPU
            - 'prob': fake probabilities [N] on CPU
            - 'feat': shared features [N, shared_feat_dim] on CPU
    """
    if batch_rgb.numel() == 0:
        # Empty batch: determine feature dimension from model
        feat_dim = getattr(model, "shared_feat_dim", 256)  # Should be 256 for UCF
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
        dev_model = batch_rgb.device  # Fallback for mock models with no parameters
    assert batch_rgb.device == dev_model, f"Batch on {batch_rgb.device}, model on {dev_model}"
    assert batch_rgb.dtype == torch.float32, f"Expected float32 normalized input, got {batch_rgb.dtype}"

    with inference_guard():
        if inference:
            # UCF inference path: shared features and shared head only
            # Follows DeepfakeBench ucf_detector.py lines 237-264
            data_dict = {'image': batch_rgb}
            pred_dict = model.forward_inference(data_dict)

            out_sha = pred_dict['cls']      # [N, 2] logits
            sha_feat = pred_dict['feat']    # [N, 256] pooled features

            # Apply softmax to get fake probabilities (DeepfakeBench line 241)
            prob_sha = softmax_fake(out_sha)  # [N] fake probabilities (standardized)

            # Runtime hygiene checks
            assert out_sha.shape[1] == 2, f"UCF logits should be [N, 2], got {out_sha.shape}"
            assert prob_sha.ndim == 1 and prob_sha.shape[0] == out_sha.shape[0]
            assert not out_sha.requires_grad and not prob_sha.requires_grad
            assert out_sha.device == batch_rgb.device

            # Validate feature dimensions match expected shared_feat_dim
            expected_feat_dim = getattr(model, "shared_feat_dim", 256)
            assert sha_feat.shape == (batch_rgb.size(0), expected_feat_dim), \
                f"Expected shared features [{batch_rgb.size(0)}, {expected_feat_dim}], got {sha_feat.shape}"

            # Ensure all outputs are finite
            assert torch.isfinite(out_sha).all(), "UCF logits contain non-finite values"
            assert torch.isfinite(prob_sha).all(), "UCF probabilities contain non-finite values"
            assert torch.isfinite(sha_feat).all(), "UCF features contain non-finite values"

            # Return DeepfakeBench-format dictionary with CPU tensors
            return {
                'cls': to_cpu(out_sha),      # [N, 2] logits
                'prob': to_cpu(prob_sha),    # [N] fake probabilities
                'feat': to_cpu(sha_feat)     # [N, shared_feat_dim] pooled features
            }
        else:
            raise NotImplementedError("UCF training mode not implemented in adapter")