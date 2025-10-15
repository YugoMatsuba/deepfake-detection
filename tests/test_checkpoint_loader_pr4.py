"""
PR4: Checkpoint Loader Tests

Tests for centralized DeepfakeBench checkpoint loading (load_dfb_checkpoint).
These tests validate architecture compatibility and loading patterns without
requiring actual weight files.

Run with: pytest tests/test_checkpoint_loader_pr4.py -v
"""

import pytest
import torch
import torch.nn as nn
from pathlib import Path
import tempfile
import os

# Import the loader and models
from ml.models.utils import (
    load_dfb_checkpoint,
    _drop_fc_keys_simple,
    _fix_pointwise_weights_inplace,
    _strip_known_prefixes,
    _torch_load_maybe_wrapped,
)
from ml.models.xception_arch import Xception
from ml.models.ucf_arch import UCFDetector


# ============================================================================
# Fixtures: Create Fake Checkpoints
# ============================================================================

@pytest.fixture
def fake_imagenet_checkpoint():
    """Create a minimal fake ImageNet checkpoint matching xception structure."""
    return {
        'conv1.weight': torch.randn(32, 3, 3, 3),
        'bn1.weight': torch.randn(32),
        'bn1.bias': torch.randn(32),
        'bn1.running_mean': torch.randn(32),
        'bn1.running_var': torch.randn(32),
        # Add a pointwise layer that needs fixing (2D instead of 4D)
        'block1.rep.0.pointwise.weight': torch.randn(128, 32),  # Should be [128, 32, 1, 1]
        # Add fc layer that should be dropped
        'last_linear.weight': torch.randn(1000, 2048),
        'last_linear.bias': torch.randn(1000),
    }


@pytest.fixture
def fake_checkpoint_with_module_prefix(fake_imagenet_checkpoint):
    """Add 'module.' prefix to all keys (DataParallel format)."""
    return {f"module.{k}": v for k, v in fake_imagenet_checkpoint.items()}


@pytest.fixture
def fake_wrapped_checkpoint(fake_imagenet_checkpoint):
    """Wrap checkpoint in {'state_dict': ...} format."""
    return {'state_dict': fake_imagenet_checkpoint}


# ============================================================================
# Test Helper Functions
# ============================================================================

def test_drop_fc_keys_simple(fake_imagenet_checkpoint):
    """Test that fc keys are correctly identified and dropped."""
    filtered, dropped = _drop_fc_keys_simple(fake_imagenet_checkpoint)

    # FC keys should be in dropped list
    assert 'last_linear.weight' in dropped
    assert 'last_linear.bias' in dropped
    assert len(dropped) == 2

    # FC keys should NOT be in filtered dict
    assert 'last_linear.weight' not in filtered
    assert 'last_linear.bias' not in filtered

    # Other keys should remain
    assert 'conv1.weight' in filtered
    assert 'bn1.weight' in filtered


def test_fix_pointwise_weights_inplace():
    """Test that 2D pointwise weights are fixed to 4D."""
    state = {
        'block1.rep.0.pointwise.weight': torch.randn(128, 32),  # 2D - should be fixed
        'conv1.weight': torch.randn(32, 3, 3, 3),  # 4D - should stay as-is
    }

    fixed_count = _fix_pointwise_weights_inplace(state)

    assert fixed_count == 1
    assert state['block1.rep.0.pointwise.weight'].shape == (128, 32, 1, 1)
    assert state['conv1.weight'].shape == (32, 3, 3, 3)


def test_strip_known_prefixes(fake_checkpoint_with_module_prefix):
    """Test that 'module.' prefixes are stripped."""
    stripped = _strip_known_prefixes(fake_checkpoint_with_module_prefix, prefixes=('module.',))

    # Original keys should be gone
    assert 'module.conv1.weight' not in stripped

    # Stripped keys should exist
    assert 'conv1.weight' in stripped
    assert 'bn1.weight' in stripped

    # Count should match
    assert len(stripped) == len(fake_checkpoint_with_module_prefix)


def test_torch_load_maybe_wrapped_raw(fake_imagenet_checkpoint, tmp_path):
    """Test loading raw state dict (unwrapped)."""
    ckpt_path = tmp_path / "raw_checkpoint.pth"
    torch.save(fake_imagenet_checkpoint, ckpt_path)

    loaded = _torch_load_maybe_wrapped(str(ckpt_path), torch.device('cpu'))

    assert 'conv1.weight' in loaded
    assert len(loaded) == len(fake_imagenet_checkpoint)


def test_torch_load_maybe_wrapped_wrapped(fake_wrapped_checkpoint, tmp_path):
    """Test loading wrapped checkpoint {'state_dict': ...}."""
    ckpt_path = tmp_path / "wrapped_checkpoint.pth"
    torch.save(fake_wrapped_checkpoint, ckpt_path)

    loaded = _torch_load_maybe_wrapped(str(ckpt_path), torch.device('cpu'))

    # Should unwrap automatically
    assert 'conv1.weight' in loaded
    assert 'state_dict' not in loaded  # Wrapper key removed


# ============================================================================
# Test Xception Loading
# ============================================================================

def test_xception_loader_structure(fake_imagenet_checkpoint, tmp_path):
    """Test that Xception loader handles checkpoint correctly."""
    # Create model
    config = {"mode": "original", "num_classes": 2, "inc": 3, "dropout": False}
    model = Xception(config)

    # Save fake checkpoint
    ckpt_path = tmp_path / "xception.pth"
    torch.save(fake_imagenet_checkpoint, ckpt_path)

    # Load using centralized loader
    report = load_dfb_checkpoint(
        model,
        str(ckpt_path),
        device="cpu",
        arch="xception",
        expected_num_classes=2
    )

    # Validate report structure
    assert 'weights_hash' in report
    assert 'keys_total' in report
    assert 'keys_loaded' in report
    assert 'dropped_head_keys' in report
    assert 'fixed_pointwise_count' in report

    # FC keys should be dropped
    assert 'last_linear.weight' in report['dropped_head_keys']
    assert 'last_linear.bias' in report['dropped_head_keys']

    # Pointwise fix should have been applied
    assert report['fixed_pointwise_count'] == 1


# ============================================================================
# Test SPSL Loading (conv1 pop and 4-ch replacement)
# ============================================================================

def test_spsl_loader_conv1_handling(fake_imagenet_checkpoint, tmp_path):
    """Test that SPSL pops conv1 before loading and replaces with 4-ch version."""
    # Create model
    config = {"mode": "original", "num_classes": 2, "inc": 3, "dropout": False}
    model = Xception(config)

    # Verify initial state
    assert model.conv1.in_channels == 3

    # Save fake checkpoint
    ckpt_path = tmp_path / "spsl.pth"
    torch.save(fake_imagenet_checkpoint, ckpt_path)

    # Load using SPSL loader
    report = load_dfb_checkpoint(
        model,
        str(ckpt_path),
        device="cpu",
        arch="spsl",
        expected_num_classes=2
    )

    # Verify conv1 was replaced with 4-channel version
    assert model.conv1.in_channels == 4
    assert model.conv1.bias is None

    # Verify seeding flag
    assert report['spsl_conv1_seeded'] is True

    # keys_total should NOT include conv1 (it was popped)
    # Original has 8 keys - 2 fc keys - 1 conv1 = 5 keys
    assert report['keys_total'] == 5


def test_spsl_loader_no_conv1_in_checkpoint(tmp_path):
    """Test SPSL loader when checkpoint doesn't have conv1.weight."""
    config = {"mode": "original", "num_classes": 2, "inc": 3, "dropout": False}
    model = Xception(config)

    # Create checkpoint WITHOUT conv1
    ckpt = {
        'bn1.weight': torch.randn(32),
        'bn1.bias': torch.randn(32),
    }

    ckpt_path = tmp_path / "no_conv1.pth"
    torch.save(ckpt, ckpt_path)

    report = load_dfb_checkpoint(
        model,
        str(ckpt_path),
        device="cpu",
        arch="spsl",
        expected_num_classes=2
    )

    # Conv1 should still be 4-channel but not seeded from checkpoint
    assert model.conv1.in_channels == 4
    assert report['spsl_conv1_seeded'] is False


# ============================================================================
# Test UCF Loading (dual encoder)
# ============================================================================

def test_ucf_loader_dual_encoder(fake_imagenet_checkpoint, tmp_path):
    """Test that UCF loads weights into BOTH encoder_f and encoder_c."""
    config = {
        "mode": "adjust_channel",
        "num_classes": 2,
        "inc": 3,
        "dropout": False,
        "encoder_feat_dim": 512,
        "specific_task_number": 5,
    }
    model = UCFDetector(config)

    # Save checkpoint
    ckpt_path = tmp_path / "ucf.pth"
    torch.save(fake_imagenet_checkpoint, ckpt_path)

    # Store initial encoder_f conv1 weights for comparison
    initial_f_conv1 = model.encoder_f.conv1.weight.clone()

    # Load using UCF loader
    report = load_dfb_checkpoint(
        model,
        str(ckpt_path),
        device="cpu",
        arch="ucf",
        expected_num_classes=2
    )

    # Verify weights were loaded (changed from initial)
    assert not torch.allclose(model.encoder_f.conv1.weight, initial_f_conv1)

    # Verify BOTH encoders got the SAME ImageNet weights
    assert torch.allclose(
        model.encoder_f.conv1.weight,
        model.encoder_c.conv1.weight
    ), "Both encoders should have identical ImageNet weights"

    # keys_loaded should be sum of both encoders
    # Each encoder loads same keys, so total = 2 * per_encoder
    assert report['keys_loaded'] > 0

    # Missing keys should have encoder prefixes
    assert any('encoder_f.' in k for k in report['keys_missing'])
    assert any('encoder_c.' in k for k in report['keys_missing'])


# ============================================================================
# Test Error Handling
# ============================================================================

def test_loader_unknown_arch(fake_imagenet_checkpoint, tmp_path):
    """Test that unknown architecture raises error."""
    config = {"mode": "original", "num_classes": 2, "inc": 3, "dropout": False}
    model = Xception(config)

    ckpt_path = tmp_path / "test.pth"
    torch.save(fake_imagenet_checkpoint, ckpt_path)

    with pytest.raises(ValueError, match="Unknown arch"):
        load_dfb_checkpoint(
            model,
            str(ckpt_path),
            device="cpu",
            arch="unknown_model",
            expected_num_classes=2
        )


def test_loader_missing_checkpoint_file():
    """Test that missing checkpoint file is handled."""
    config = {"mode": "original", "num_classes": 2, "inc": 3, "dropout": False}
    model = Xception(config)

    with pytest.raises(FileNotFoundError):
        load_dfb_checkpoint(
            model,
            "/nonexistent/path/to/checkpoint.pth",
            device="cpu",
            arch="xception",
            expected_num_classes=2
        )


# ============================================================================
# Integration Tests (Architecture Compatibility)
# ============================================================================

def test_xception_architecture_compatibility():
    """Verify Xception architecture matches expected structure."""
    config = {"mode": "original", "num_classes": 2, "inc": 3, "dropout": False}
    model = Xception(config)

    # Test dummy forward pass
    x = torch.randn(2, 3, 256, 256)

    # Features
    feat = model.features(x)
    assert feat.shape[0] == 2  # Batch size

    # Classifier
    logits = model.classifier(feat)
    assert logits.shape == (2, 2)  # [batch, num_classes]

    # last_emb should be set after classifier
    assert hasattr(model, 'last_emb')
    assert model.last_emb.shape == (2, 2048)  # mode="original" -> 2048D


def test_ucf_architecture_compatibility():
    """Verify UCF architecture has correct dual-encoder structure."""
    config = {
        "mode": "adjust_channel",
        "num_classes": 2,
        "inc": 3,
        "dropout": False,
        "encoder_feat_dim": 512,
        "specific_task_number": 5,
    }
    model = UCFDetector(config)

    # Verify dual encoders exist
    assert hasattr(model, 'encoder_f')
    assert hasattr(model, 'encoder_c')

    # Verify both are Xception with adjust_channel mode
    assert model.encoder_f.mode == "adjust_channel"
    assert model.encoder_c.mode == "adjust_channel"

    # Verify heads exist
    assert hasattr(model, 'head_sha')  # Shared head (2 classes)
    assert hasattr(model, 'head_spe')  # Specific head (5 classes)

    # Verify head dimensions
    assert model.head_sha.mlp[-1].out_features == 2
    assert model.head_spe.mlp[-1].out_features == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
