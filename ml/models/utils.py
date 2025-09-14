# utils.py - Shared utilities for DeepfakeBench-aligned model loading

import hashlib
import logging
from collections import OrderedDict
from contextlib import contextmanager
from typing import Dict, Any

import torch


logger = logging.getLogger(__name__)


def map_location_for_device(device: str) -> torch.device:
    """Get appropriate map_location for torch.load based on device string."""
    if device.startswith("cuda"):
        return torch.device(device)
    return torch.device("cpu")


def strip_module_prefix(state_dict: Dict[str, Any]) -> OrderedDict:
    """
    Remove 'module.' prefix from state_dict keys.

    DeepfakeBench checkpoints saved with DataParallel have 'module.' prefixes
    that need to be stripped for single-GPU loading.

    Args:
        state_dict: Original state dict potentially with module prefixes

    Returns:
        OrderedDict with module prefixes removed
    """
    new_state_dict = OrderedDict()
    for key, value in state_dict.items():
        # Remove 'module.' prefix if present
        new_key = key[7:] if key.startswith('module.') else key
        new_state_dict[new_key] = value
    return new_state_dict


def fix_pointwise_separable_convs(state_dict: Dict[str, Any]) -> OrderedDict:
    """
    Fix pointwise convolution weights in SeparableConv2d layers.

    Based on DeepfakeBench's xception_detector.py lines 70-72:
    Some checkpoints store pointwise weights as 2D [C_out, C_in] tensors,
    but PyTorch Conv2d expects 4D [C_out, C_in, 1, 1] tensors.

    Args:
        state_dict: State dict with potentially 2D pointwise weights

    Returns:
        OrderedDict with pointwise weights unsqueezed to 4D
    """
    fixed_state_dict = OrderedDict()
    pointwise_fixes = 0

    for name, weights in state_dict.items():
        if 'pointwise' in name and weights.ndim == 2:
            # Unsqueeze 2D pointwise weights to 4D: [C_out, C_in] -> [C_out, C_in, 1, 1]
            fixed_weights = weights.unsqueeze(-1).unsqueeze(-1)
            fixed_state_dict[name] = fixed_weights
            pointwise_fixes += 1
        else:
            fixed_state_dict[name] = weights

    if pointwise_fixes > 0:
        logger.debug(f"Fixed {pointwise_fixes} pointwise convolution weights")

    return fixed_state_dict


def drop_fc_keys(state_dict: Dict[str, Any]) -> OrderedDict:
    """
    Remove final classification layer keys from state dict.

    Based on DeepfakeBench's xception_detector.py line 73:
    Remove FC layer keys so model can attach its own classification head.

    Args:
        state_dict: State dict potentially containing FC layer weights

    Returns:
        OrderedDict with FC keys removed
    """
    filtered_state_dict = OrderedDict()
    dropped_keys = []

    for key, value in state_dict.items():
        if 'fc' in key:
            dropped_keys.append(key)
        else:
            filtered_state_dict[key] = value

    if dropped_keys:
        logger.debug(f"Dropped FC keys: {dropped_keys}")

    return filtered_state_dict


def softmax_fake(logits: torch.Tensor) -> torch.Tensor:
    """
    Extract fake class probabilities from 2-class logits.

    Based on DeepfakeBench pattern in all detectors:
    torch.softmax(pred, dim=1)[:, 1] - always column 1 for "fake" class

    Args:
        logits: Tensor with shape [N, 2] - 2-class logits

    Returns:
        Tensor with shape [N] - fake class probabilities in [0, 1]
    """
    assert logits.shape[-1] == 2, f"Expected 2-class logits, got shape {logits.shape}"
    return torch.softmax(logits, dim=1)[:, 1]


@contextmanager
def inference_guard():
    """
    Context manager for inference mode.

    Disables gradient computation and ensures deterministic behavior.
    """
    with torch.no_grad():
        yield


def to_cpu(tensor: torch.Tensor) -> torch.Tensor:
    """Move tensor to CPU for consistent output format."""
    return tensor.cpu()


def hash_file(file_path: str) -> str:
    """
    Compute SHA-256 hash of a file for weight provenance tracking.

    Args:
        file_path: Path to file to hash

    Returns:
        Hex string of SHA-256 hash
    """
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Read in chunks for memory efficiency with large weight files
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def ensure_eval(model: torch.nn.Module) -> torch.nn.Module:
    """Ensure model is in eval mode and return it."""
    model.eval()
    return model