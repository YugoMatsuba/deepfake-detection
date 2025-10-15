# test_xception_pr1.py - Pytest for PR1: Xception Architecture Copy

"""
Pytest suite for PR1 Xception architecture implementation.

Tests ONLY the architecture (no weights) with dummy batch validation.
Does NOT run full runner on video (results would be random without weights).

Expected outcomes:
- Architecture loads without errors
- Dummy batch [2,3,256,256] → logits [2,2], probs in [0,1], no NaNs
- Features have correct dimensions (2048 for original mode)
- DeepfakeBench format dictionary returned
"""

import pytest
import torch
from ml.models.xception_infer import load_xception, predict_probs_xception


@pytest.fixture
def xception_model():
    """Fixture to load Xception model for testing."""
    return load_xception("", "cpu")  # No weights for PR1


@pytest.fixture
def dummy_batch():
    """Fixture for dummy batch tensor."""
    return torch.randn(2, 3, 256, 256, dtype=torch.float32)


@pytest.fixture
def empty_batch():
    """Fixture for empty batch tensor."""
    return torch.empty(0, 3, 256, 256, dtype=torch.float32)


def test_xception_architecture_loading(xception_model):
    """Test that Xception architecture loads without errors."""
    assert xception_model is not None
    assert hasattr(xception_model, 'features'), "Missing features() method"
    assert hasattr(xception_model, 'classifier'), "Missing classifier() method"
    assert xception_model.num_classes == 2, f"Expected 2 classes, got {xception_model.num_classes}"
    assert xception_model.mode == "original", f"Expected 'original' mode, got {xception_model.mode}"
    assert xception_model.conv1.in_channels == 3, f"Expected 3 input channels, got {xception_model.conv1.in_channels}"


def test_xception_forward_pass(xception_model, dummy_batch):
    """Test basic forward pass with dummy data."""
    result = predict_probs_xception(xception_model, dummy_batch)
    assert result is not None
    assert isinstance(result, dict)


def test_output_shapes(xception_model, dummy_batch):
    """Test that output shapes match expected dimensions."""
    result = predict_probs_xception(xception_model, dummy_batch)

    # Validate shapes
    assert result['cls'].shape == (2, 2), f"Expected logits [2,2], got {result['cls'].shape}"
    assert result['prob'].shape == (2,), f"Expected probs [2], got {result['prob'].shape}"
    assert result['feat'].shape[0] == 2, f"Expected features batch size 2, got {result['feat'].shape[0]}"

    # Feature dimensions should be 2048 for original mode
    expected_feat_dim = 2048
    assert result['feat'].shape[1] == expected_feat_dim, f"Expected features dim {expected_feat_dim}, got {result['feat'].shape[1]}"


def test_output_value_ranges(xception_model, dummy_batch):
    """Test that output values are in valid ranges."""
    result = predict_probs_xception(xception_model, dummy_batch)

    # Probabilities should be in [0,1] range
    assert torch.all(result['prob'] >= 0), f"Probabilities below 0: min={result['prob'].min()}"
    assert torch.all(result['prob'] <= 1), f"Probabilities above 1: max={result['prob'].max()}"

    # No NaN values
    assert not torch.any(torch.isnan(result['cls'])), "NaN values in logits"
    assert not torch.any(torch.isnan(result['prob'])), "NaN values in probabilities"
    assert not torch.any(torch.isnan(result['feat'])), "NaN values in features"

    # Logits should be finite
    assert torch.all(torch.isfinite(result['cls'])), "Non-finite values in logits"


def test_deepfakebench_format_compliance(xception_model, dummy_batch):
    """Test that output format matches DeepfakeBench expectations."""
    result = predict_probs_xception(xception_model, dummy_batch)

    # Check required keys
    expected_keys = {'cls', 'prob', 'feat'}
    actual_keys = set(result.keys())
    assert actual_keys == expected_keys, f"Expected keys {expected_keys}, got {actual_keys}"

    # All outputs should be on CPU
    assert result['cls'].device.type == 'cpu', f"Logits not on CPU: {result['cls'].device}"
    assert result['prob'].device.type == 'cpu', f"Probs not on CPU: {result['prob'].device}"
    assert result['feat'].device.type == 'cpu', f"Features not on CPU: {result['feat'].device}"


def test_empty_batch_handling(xception_model, empty_batch):
    """Test that empty batches are handled correctly."""
    result = predict_probs_xception(xception_model, empty_batch)

    assert result['cls'].shape == (0, 2), f"Expected empty logits [0,2], got {result['cls'].shape}"
    assert result['prob'].shape == (0,), f"Expected empty probs [0], got {result['prob'].shape}"
    assert result['feat'].shape == (0, 2048), f"Expected empty features [0,2048], got {result['feat'].shape}"


def test_model_in_eval_mode(xception_model):
    """Test that model is properly set to eval mode."""
    assert not xception_model.training, "Model should be in eval mode"


def test_config_compatibility():
    """Test that config matches DeepfakeBench expectations."""
    # Test the exact config used matches DeepfakeBench xception.yaml
    model = load_xception("", "cpu")

    assert model.mode == "original", "Mode should match DeepfakeBench config"
    assert model.num_classes == 2, "Should be binary classification"

    # Test that we can create model with DeepfakeBench config format
    from ml.models.xception_arch import Xception

    config = {
        "mode": "original",
        "num_classes": 2,
        "inc": 3,
        "dropout": False
    }

    model_direct = Xception(config)
    assert model_direct.num_classes == 2
    assert model_direct.mode == "original"


@pytest.mark.parametrize("batch_size", [1, 2, 4, 8])
def test_variable_batch_sizes(xception_model, batch_size):
    """Test that model works with different batch sizes."""
    batch = torch.randn(batch_size, 3, 256, 256, dtype=torch.float32)
    result = predict_probs_xception(xception_model, batch)

    assert result['cls'].shape == (batch_size, 2)
    assert result['prob'].shape == (batch_size,)
    assert result['feat'].shape == (batch_size, 2048)