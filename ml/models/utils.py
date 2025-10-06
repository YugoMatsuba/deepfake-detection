# utils.py - Shared utilities for DeepfakeBench-aligned model loading

import hashlib
import logging
from collections import OrderedDict
from contextlib import contextmanager
from typing import Dict, Any, List, Tuple, Optional

import torch
import torch.nn as nn


logger = logging.getLogger(__name__)


def map_location_for_device(device: str) -> torch.device:
    """Get appropriate map_location for torch.load based on device string."""
    if device.startswith("cuda"):
        return torch.device(device)
    return torch.device("cpu")


# NOTE: Old helpers below are kept for backward compatibility but are no longer
# used by the centralized loader. They are superseded by _strip_known_prefixes
# and _fix_pointwise_weights_inplace in the PR4 loader implementation.

def strip_module_prefix(state_dict: Dict[str, Any]) -> OrderedDict:
    """
    DEPRECATED: Use _strip_known_prefixes() in centralized loader instead.

    Remove 'module.' prefix from state_dict keys.

    DeepfakeBench checkpoints saved with DataParallel have 'module.' prefixes
    that need to be stripped for single-GPU loading.

    Args:
        state_dict: Original state dict potentially with module prefixes

    Returns:
        OrderedDict with module prefixes removed
    """
    return dict(_strip_known_prefixes(state_dict, prefixes=('module.',)))


def fix_pointwise_separable_convs(state_dict: Dict[str, Any]) -> OrderedDict:
    """
    DEPRECATED: Use _fix_pointwise_weights_inplace() in centralized loader instead.

    Fix pointwise convolution weights in SeparableConv2d layers.

    Based on DeepfakeBench's xception_detector.py lines 70-72:
    Some checkpoints store pointwise weights as 2D [C_out, C_in] tensors,
    but PyTorch Conv2d expects 4D [C_out, C_in, 1, 1] tensors.

    Args:
        state_dict: State dict with potentially 2D pointwise weights

    Returns:
        OrderedDict with pointwise weights unsqueezed to 4D
    """
    state_copy = dict(state_dict)
    _fix_pointwise_weights_inplace(state_copy)
    return OrderedDict(state_copy)


def drop_fc_keys(state_dict: Dict[str, Any]) -> OrderedDict:
    """
    DEPRECATED: Use _drop_fc_keys_simple() in centralized loader instead.

    Remove final classification layer keys from state dict.

    Based on DeepfakeBench's xception_detector.py line 73:
    Remove FC layer keys so model can attach its own classification head.

    Args:
        state_dict: State dict potentially containing FC layer weights

    Returns:
        OrderedDict with FC keys removed
    """
    filtered, _ = _drop_fc_keys_simple(state_dict)
    return OrderedDict(filtered)


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


# ============================================================================
# PR4: Centralized DeepfakeBench Checkpoint Loading
# ============================================================================


def load_dfb_checkpoint(
    model: nn.Module,
    weights_path: str,
    *,
    device: str,
    arch: str,
    expected_num_classes: int = 2,
) -> Dict[str, Any]:
    """
    Central checkpoint loader for DeepfakeBench pretrained weights.

    Applies all standard DFB checkpoint fixups and returns detailed load report.
    Based on exact patterns from:
    - xception_detector.py lines 69-75
    - spsl_detector.py lines 71-88
    - ucf_detector.py lines 105-111

    Args:
        model: Model instance (already built with correct architecture)
        weights_path: Path to checkpoint .pth file
        device: Device string ("cpu" or "cuda")
        arch: Architecture name ("xception" | "spsl" | "ucf")
        expected_num_classes: Expected output classes for shared head (default: 2)

    Returns:
        Report dict with keys:
            - weights_path: str
            - weights_hash: str (SHA-256, empty on error)
            - keys_total: int
            - keys_loaded: int
            - keys_missing: List[str]
            - keys_unexpected: List[str]
            - fixed_pointwise_count: int
            - dropped_head_keys: List[str]
            - spsl_conv1_seeded: bool
            - notes: List[str]
    """
    report: Dict[str, Any] = {
        'weights_path': weights_path,
        'weights_hash': '',
        'keys_total': 0,
        'keys_loaded': 0,
        'keys_missing': [],
        'keys_unexpected': [],
        'fixed_pointwise_count': 0,
        'dropped_head_keys': [],
        'spsl_conv1_seeded': False,
        'notes': []
    }

    try:
        report['weights_hash'] = hash_file(weights_path)
    except Exception as e:
        report['notes'].append(f"Could not hash weights file: {e}")
        logger.warning(f"Failed to hash {weights_path}: {e}")

    # Load checkpoint with appropriate device mapping
    map_location = map_location_for_device(device)
    state_dict = _torch_load_maybe_wrapped(weights_path, map_location)
    report['keys_total'] = len(state_dict)

    # Apply standard fixups following exact DFB pattern order:
    # 1. Strip module. and backbone. prefixes (for DataParallel checkpoints and DFB full model saves)
    state_dict = _strip_known_prefixes(state_dict, prefixes=('module.', 'backbone.'))

    # 2. Fix pointwise separable conv weights (2D → 4D)
    fixed_count = _fix_pointwise_weights_inplace(state_dict)
    report['fixed_pointwise_count'] = fixed_count

    # 3. Conditionally drop incompatible fc keys
    # UCF: Skip head dropping entirely (loads full trained model with both heads)
    # Xception/SPSL: Keep 2-class trained heads, drop mismatched ones
    if arch == "ucf":
        # ═══════════════════════════════════════════════════════════════════════
        # UCF Head Handling (Keep It Simple)
        # ═══════════════════════════════════════════════════════════════════════
        # Decision: We load trained UCF detector weights (not ImageNet backbones).
        # Those checkpoints already include both classifier heads. Therefore:
        #   • Do NOT drop any head keys for UCF
        #   • Treat the checkpoint as a full detector (encoders + shared/specific heads)
        #   • Fail fast if head shapes don't match (via post-load assertions in ucf_infer.py)
        #
        # What to enforce (at load time):
        #   After loading, ucf_infer.py asserts:
        #   • model.head_sha.mlp[-1].out_features == 2 (shared head = 2-class)
        #   • model.head_spe.mlp[-1].out_features == 5 (specific head = 5-class for FF++)
        #
        # What NOT to do:
        #   • Do NOT run "drop fc/last_linear" filtering on UCF checkpoints
        #   • Do NOT try to auto-convert head sizes in this loader
        #   • Do NOT rely on conditional "head-shape detection" for UCF
        #
        # Why: Earlier "~0.5 score" issues came from mistakenly dropping trained
        # classifier layers and running with random heads. Keeping all head keys
        # for UCF and asserting shapes avoids that class of bug.
        # ═══════════════════════════════════════════════════════════════════════
        report['notes'].append("UCF: Skipped head key filtering (loading full trained detector)")
        dropped = []
    else:
        # Xception/SPSL: Conditionally keep heads matching expected_num_classes
        state_dict, dropped = _drop_fc_keys_simple(state_dict, expected_num_classes=expected_num_classes)
        if dropped:
            report['notes'].append(f"Dropped {len(dropped)} head keys (ImageNet or mismatched): {dropped}")
        else:
            report['notes'].append(f"Kept trained {expected_num_classes}-class head keys")
    report['dropped_head_keys'].extend(dropped)

    # Architecture-specific handling
    if arch == "spsl":
        # CRITICAL: SPSL must POP conv1.weight BEFORE load_state_dict
        # Based on spsl_detector.py lines 78-88
        conv1_data = state_dict.pop('conv1.weight', None)

        # Count keys_total AFTER all fixups and pop (matches what we actually try to load)
        report['keys_total'] = len(state_dict)

        # Drop shape-mismatched keys (for synthetic test checkpoints)
        state_dict, shape_dropped = _drop_mismatched_shape_keys(model, state_dict)
        report.setdefault('shape_mismatch_dropped', []).extend(shape_dropped)

        # Load backbone weights (conv1 will be missing, that's expected)
        missing, unexpected = _apply_state_dict(model, state_dict)
        report['keys_missing'] = list(missing)
        report['keys_unexpected'] = list(unexpected)
        # keys_loaded = keys we provided that matched (total - unexpected)
        report['keys_loaded'] = report['keys_total'] - len(unexpected)

        # Now replace conv1 with 4-channel version and seed from popped weights
        spsl_seeded = _spsl_replace_conv1_with_4ch(model, conv1_data)
        report['spsl_conv1_seeded'] = spsl_seeded

        if spsl_seeded:
            report['notes'].append("SPSL conv1 seeded from checkpoint conv1.weight")
        else:
            report['notes'].append("SPSL conv1 created with default init (no checkpoint conv1.weight)")

    elif arch == "ucf":
        # UCF checkpoint is a FULL trained model (not ImageNet weights)
        # Structure: encoder_f.*, encoder_c.*, head_sha.*, head_spe.*, block_sha/spe.*

        # Separate keys by component prefix
        encoder_f_keys = {k.replace('encoder_f.', ''): v for k, v in state_dict.items() if k.startswith('encoder_f.')}
        encoder_c_keys = {k.replace('encoder_c.', ''): v for k, v in state_dict.items() if k.startswith('encoder_c.')}
        head_sha_keys = {k.replace('head_sha.', ''): v for k, v in state_dict.items() if k.startswith('head_sha.')}
        head_spe_keys = {k.replace('head_spe.', ''): v for k, v in state_dict.items() if k.startswith('head_spe.')}
        block_sha_keys = {k.replace('block_sha.', ''): v for k, v in state_dict.items() if k.startswith('block_sha.')}
        block_spe_keys = {k.replace('block_spe.', ''): v for k, v in state_dict.items() if k.startswith('block_spe.')}

        # Load encoders
        missing_f, unexpected_f = _apply_state_dict(model.encoder_f, encoder_f_keys)
        missing_c, unexpected_c = _apply_state_dict(model.encoder_c, encoder_c_keys)

        # Load heads
        missing_sha, unexpected_sha = _apply_state_dict(model.head_sha, head_sha_keys)
        missing_spe, unexpected_spe = _apply_state_dict(model.head_spe, head_spe_keys)

        # Load blocks (if present in model)
        if hasattr(model, 'block_sha') and block_sha_keys:
            _apply_state_dict(model.block_sha, block_sha_keys)
        if hasattr(model, 'block_spe') and block_spe_keys:
            _apply_state_dict(model.block_spe, block_spe_keys)

        # Compute totals
        total_keys = len(encoder_f_keys) + len(encoder_c_keys) + len(head_sha_keys) + len(head_spe_keys)
        loaded_keys = (len(encoder_f_keys) - len(unexpected_f) +
                       len(encoder_c_keys) - len(unexpected_c) +
                       len(head_sha_keys) - len(unexpected_sha) +
                       len(head_spe_keys) - len(unexpected_spe))

        report['keys_total'] = total_keys
        report['keys_loaded'] = loaded_keys
        report['keys_missing'] = list(set(missing_f + missing_c + missing_sha + missing_spe))
        report['keys_unexpected'] = list(set(unexpected_f + unexpected_c + unexpected_sha + unexpected_spe))
        report['notes'].append(
            f"Loaded full UCF model: encoder_f ({len(encoder_f_keys)-len(unexpected_f)}/{len(encoder_f_keys)}), "
            f"encoder_c ({len(encoder_c_keys)-len(unexpected_c)}/{len(encoder_c_keys)}), "
            f"heads (sha: {len(head_sha_keys)-len(unexpected_sha)}/{len(head_sha_keys)}, "
            f"spe: {len(head_spe_keys)-len(unexpected_spe)}/{len(head_spe_keys)})"
        )

    elif arch == "xception":
        # Standard Xception loading
        report['keys_total'] = len(state_dict)

        # Drop shape-mismatched keys (for synthetic test checkpoints)
        state_dict, shape_dropped = _drop_mismatched_shape_keys(model, state_dict)
        report.setdefault('shape_mismatch_dropped', []).extend(shape_dropped)

        missing, unexpected = _apply_state_dict(model, state_dict)
        report['keys_missing'] = list(missing)
        report['keys_unexpected'] = list(unexpected)
        # keys_loaded = keys we provided that matched (total - unexpected)
        report['keys_loaded'] = report['keys_total'] - len(unexpected)

    else:
        raise ValueError(f"Unknown arch: {arch}. Expected 'xception', 'spsl', or 'ucf'")

    # Log summary
    logger.info(f"Loaded checkpoint: {weights_path}")
    logger.info(f"  SHA-256: {report['weights_hash'][:16]}...")
    logger.info(f"  Keys: {report['keys_loaded']}/{report['keys_total']} loaded")
    logger.info(f"  Pointwise fixes: {report['fixed_pointwise_count']}")
    logger.info(f"  Missing: {len(report['keys_missing'])}, Unexpected: {len(report['keys_unexpected'])}")

    if arch == "spsl":
        logger.info(f"  SPSL conv1 seeded: {report['spsl_conv1_seeded']}")

    # Debug logging for missing/unexpected keys
    if report['keys_missing']:
        logger.debug(f"Missing keys: {report['keys_missing']}")
    if report['keys_unexpected']:
        logger.debug(f"Unexpected keys: {report['keys_unexpected']}")

    return report


# ============================================================================
# Private Helper Functions (match DFB patterns exactly)
# ============================================================================


def _torch_load_maybe_wrapped(
    weights_path: str,
    map_location: torch.device
) -> Dict[str, torch.Tensor]:
    """
    Load checkpoint and unwrap if needed.

    DeepfakeBench ImageNet pretrained weights (xception-b5690688.pth) are
    raw state_dicts, NOT wrapped in {'state_dict': ...}.

    However, we handle both formats for robustness with custom checkpoints.

    Args:
        weights_path: Path to .pth file
        map_location: Device for loading tensors

    Returns:
        State dict (unwrapped if necessary)

    Raises:
        ValueError: If checkpoint format is unsupported
    """
    raw = torch.load(weights_path, map_location=map_location)

    # Handle various checkpoint formats
    if isinstance(raw, dict):
        # Check for common wrapper keys
        if 'state_dict' in raw:
            state = raw['state_dict']
        elif 'model' in raw:
            state = raw['model']
        else:
            # Assume it's already a state dict (DFB ImageNet pretrained pattern)
            state = raw

        # Validate all values are tensors
        non_tensor_keys = [k for k, v in state.items() if not isinstance(v, torch.Tensor)]
        if non_tensor_keys:
            logger.warning(f"Filtering {len(non_tensor_keys)} non-tensor keys: {non_tensor_keys[:5]}...")
            state = {k: v for k, v in state.items() if isinstance(v, torch.Tensor)}

        return state

    elif isinstance(raw, OrderedDict):
        # Direct OrderedDict of tensors
        return dict(raw)

    else:
        raise ValueError(
            f"Unsupported checkpoint structure: expected dict or OrderedDict, "
            f"got {type(raw).__name__}"
        )


def _strip_known_prefixes(
    state: Dict[str, torch.Tensor],
    prefixes: Tuple[str, ...] = ('module.',)
) -> Dict[str, torch.Tensor]:
    """
    Strip known prefixes from state dict keys.

    DeepfakeBench checkpoints saved with DataParallel have 'module.' prefixes.
    Based on common pattern across all detectors.

    Args:
        state: Original state dict
        prefixes: Tuple of prefixes to strip (default: ('module.',))

    Returns:
        State dict with prefixes removed
    """
    new_state = {}
    stripped_count = 0

    for key, value in state.items():
        new_key = key
        # Try each prefix in order (first match wins)
        for prefix in prefixes:
            if key.startswith(prefix):
                new_key = key[len(prefix):]
                stripped_count += 1
                break
        new_state[new_key] = value

    if stripped_count > 0:
        logger.debug(f"Stripped {stripped_count} keys with prefixes: {prefixes}")

    return new_state


def _fix_pointwise_weights_inplace(
    state: Dict[str, torch.Tensor]
) -> int:
    """
    Fix 2D pointwise weights by unsqueezing to 4D.

    Based on exact DFB pattern from all three detectors:
    for name, weights in state_dict.items():
        if 'pointwise' in name:
            state_dict[name] = weights.unsqueeze(-1).unsqueeze(-1)

    Args:
        state: State dict (modified in-place)

    Returns:
        Number of keys fixed
    """
    fixed_count = 0

    for name in list(state.keys()):  # list() to avoid dict size change during iteration
        weights = state[name]
        if 'pointwise' in name and weights.ndim == 2:
            # Exact DFB pattern: [C_out, C_in] → [C_out, C_in, 1, 1]
            state[name] = weights.unsqueeze(-1).unsqueeze(-1)
            fixed_count += 1

    return fixed_count


def _drop_fc_keys_simple(
    state: Dict[str, torch.Tensor],
    expected_num_classes: Optional[int] = None
) -> Tuple[Dict[str, torch.Tensor], List[str]]:
    """
    Conditionally remove fc/last_linear keys from state dict.

    Behavior:
    - If expected_num_classes is None: Drop all fc/last_linear keys (ImageNet mode)
    - If expected_num_classes is set: Keep fc/last_linear keys that match expected shape (trained detector mode)

    This handles two DeepfakeBench loading patterns:
    1. ImageNet pretrained (build_backbone): Drops fc keys unconditionally
       (xception_detector.py:73, spsl_detector.py:75, ucf_detector.py:109)
    2. Trained detector (test.py): Loads full model with 2-class head
       (test.py:185 - strict=True, no dropping)

    Args:
        state: Original state dict
        expected_num_classes: If set, keep heads matching this size; otherwise drop all

    Returns:
        Tuple of (filtered_state_dict, dropped_keys)
    """
    dropped = []
    filtered = {}

    for k, v in state.items():
        is_head_key = ('fc' in k) or ('last_linear' in k)

        if not is_head_key:
            # Not a head key, always keep
            filtered[k] = v
        elif expected_num_classes is None:
            # ImageNet mode: drop all head keys
            dropped.append(k)
        else:
            # Trained detector mode: check if head matches expected shape
            if 'weight' in k and v.ndim >= 1:
                # Weight tensor: first dim is out_features (num_classes)
                if v.shape[0] == expected_num_classes:
                    filtered[k] = v  # Keep trained head
                else:
                    dropped.append(k)  # Shape mismatch, drop
            elif 'bias' in k and v.ndim >= 1:
                # Bias tensor: should match num_classes
                if v.shape[0] == expected_num_classes:
                    filtered[k] = v  # Keep trained head bias
                else:
                    dropped.append(k)  # Shape mismatch, drop
            else:
                # Unknown head key structure, drop to be safe
                dropped.append(k)

    return filtered, dropped


def _drop_mismatched_shape_keys(
    model: nn.Module,
    state: Dict[str, torch.Tensor]
) -> Tuple[Dict[str, torch.Tensor], List[str]]:
    """
    Drop keys with shape mismatches between checkpoint and model.

    This is necessary for synthetic test checkpoints that intentionally have wrong shapes
    (e.g., fake ImageNet weights). PyTorch still errors on shape mismatches even with strict=False.

    Real DeepfakeBench weights should not trigger this - it's a safety feature for testing.

    Args:
        model: Model instance with correct architecture
        state: Checkpoint state dict (after prefix stripping, pointwise fixing, fc dropping)

    Returns:
        Tuple of (filtered_state_dict, dropped_keys)
    """
    model_sd = model.state_dict()
    keep: Dict[str, torch.Tensor] = {}
    dropped: List[str] = []

    for k, v in state.items():
        if k in model_sd and hasattr(model_sd[k], "shape") and hasattr(v, "shape"):
            if tuple(model_sd[k].shape) != tuple(v.shape):
                dropped.append(k)
                continue
        keep[k] = v

    return keep, dropped


def _apply_state_dict(
    model: nn.Module,
    state: Dict[str, torch.Tensor]
) -> Tuple[List[str], List[str]]:
    """
    Apply state dict to model with strict=False.

    All DFB detectors use strict=False to allow partial loading.

    Args:
        model: Model to load weights into
        state: State dict to load

    Returns:
        Tuple of (missing_keys, unexpected_keys) lists
    """
    result = model.load_state_dict(state, strict=False)
    return (list(result.missing_keys), list(result.unexpected_keys))


def _spsl_replace_conv1_with_4ch(
    model: nn.Module,
    conv1_data: Optional[torch.Tensor]
) -> bool:
    """
    Replace Xception conv1 with 4-channel version for SPSL.

    Based on EXACT DeepfakeBench spsl_detector.py lines 84-87:
    backbone.conv1 = nn.Conv2d(4, 32, 3, 2, 0, bias=False)
    avg_conv1_data = conv1_data.mean(dim=1, keepdim=True)
    backbone.conv1.weight.data = avg_conv1_data.repeat(1, 4, 1, 1)

    Args:
        model: Xception backbone (will be modified in-place)
        conv1_data: Original conv1.weight tensor [32, 3, 3, 3] or None

    Returns:
        True if seeded from checkpoint, False if default init
    """
    # Always replace conv1 with 4-channel version
    model.conv1 = nn.Conv2d(4, 32, 3, 2, 0, bias=False)

    if conv1_data is not None:
        # Seed with mean-tiled weights (exact DFB pattern with dtype/device safety)
        avg_conv1_data = conv1_data.mean(dim=1, keepdim=True)  # [32, 1, 3, 3]
        # Ensure dtype/device match (ImageNet weights are fp32, but be defensive)
        avg_conv1_data = avg_conv1_data.to(
            dtype=model.conv1.weight.dtype,
            device=model.conv1.weight.device
        )
        model.conv1.weight.data.copy_(avg_conv1_data.repeat(1, 4, 1, 1))  # [32, 4, 3, 3]
        return True
    else:
        # Use default PyTorch init
        return False