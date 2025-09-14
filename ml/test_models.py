# test_models.py - Unit tests for model adapters (no real weights required)

import numpy as np
import torch
import pytest
from collections import OrderedDict
from unittest.mock import patch, MagicMock

from ml.models.utils import (
    strip_module_prefix,
    fix_pointwise_separable_convs,
    drop_fc_keys,
    softmax_fake
)
from ml.models.spsl_infer import compute_phase_channel
from ml.models.xception_infer import predict_probs_xception, XceptionBackboneSkeleton
from ml.models.spsl_infer import predict_probs_spsl, SPSLBackboneSkeleton
from ml.models.ucf_infer import predict_probs_ucf, UCFBackboneSkeleton


class TestModelUtils:
    """Test shared utility functions."""

    def test_strip_module_prefix(self):
        """Test removal of 'module.' prefix from state dict keys."""
        state_dict = {
            'module.conv1.weight': torch.randn(32, 3, 3, 3),
            'module.bn1.weight': torch.randn(32),
            'conv2.weight': torch.randn(64, 32, 3, 3),  # No prefix
        }

        stripped = strip_module_prefix(state_dict)

        assert 'conv1.weight' in stripped
        assert 'bn1.weight' in stripped
        assert 'conv2.weight' in stripped
        assert 'module.conv1.weight' not in stripped
        assert len(stripped) == 3

    def test_fix_pointwise_separable_convs(self):
        """Test pointwise weight unsqueezing for separable convolutions."""
        state_dict = {
            'block1.pointwise.weight': torch.randn(64, 32),  # 2D - needs fixing
            'block2.conv.weight': torch.randn(32, 16, 3, 3),  # 4D - no change
            'block3.pointwise.weight': torch.randn(128, 64, 1, 1),  # Already 4D - no change
        }

        fixed = fix_pointwise_separable_convs(state_dict)

        # Check 2D pointwise weight was unsqueezed to 4D
        assert fixed['block1.pointwise.weight'].shape == (64, 32, 1, 1)
        # Check other weights unchanged
        assert fixed['block2.conv.weight'].shape == (32, 16, 3, 3)
        assert fixed['block3.pointwise.weight'].shape == (128, 64, 1, 1)

    def test_drop_fc_keys(self):
        """Test removal of final classification layer keys."""
        state_dict = {
            'backbone.conv1.weight': torch.randn(32, 3, 3, 3),
            'backbone.bn1.weight': torch.randn(32),
            'fc.weight': torch.randn(2, 512),  # Should be dropped
            'fc.bias': torch.randn(2),  # Should be dropped
            'classifier.fc.weight': torch.randn(2, 512),  # Should be dropped
        }

        filtered = drop_fc_keys(state_dict)

        assert 'backbone.conv1.weight' in filtered
        assert 'backbone.bn1.weight' in filtered
        assert 'fc.weight' not in filtered
        assert 'fc.bias' not in filtered
        assert 'classifier.fc.weight' not in filtered
        assert len(filtered) == 2

    def test_softmax_fake(self):
        """Test fake class probability extraction."""
        # Create logits with known softmax result
        logits = torch.tensor([[0.0, 2.0], [1.0, 0.0], [0.5, 0.5]])  # [N, 2]

        probs = softmax_fake(logits)

        assert probs.shape == (3,)
        # Check that probabilities are extracted from column 1 (fake class)
        expected_probs = torch.softmax(logits, dim=1)[:, 1]
        assert torch.allclose(probs, expected_probs)
        # All probabilities should be in [0, 1]
        assert torch.all(probs >= 0.0) and torch.all(probs <= 1.0)


class TestSPSLPhaseChannel:
    """Test SPSL phase channel computation."""

    def test_phase_channel_shape(self):
        """Test phase channel output shape."""
        # Create test RGB batch
        batch_rgb = torch.randn(4, 3, 256, 256)  # 4 frames

        phase_channel = compute_phase_channel(batch_rgb)

        assert phase_channel.shape == (4, 1, 256, 256)
        assert phase_channel.dtype == torch.float32

    def test_phase_channel_constant_input(self):
        """Test phase channel with constant input."""
        # Constant gray input should produce bounded output
        batch_rgb = torch.full((2, 3, 64, 64), 0.5)  # Smaller size for speed

        phase_channel = compute_phase_channel(batch_rgb)

        assert phase_channel.shape == (2, 1, 64, 64)
        # Values should be bounded (FFT of constant has specific properties)
        assert torch.isfinite(phase_channel).all()

    def test_phase_channel_deterministic(self):
        """Test that phase channel computation is deterministic."""
        batch_rgb = torch.randn(2, 3, 64, 64)

        phase1 = compute_phase_channel(batch_rgb)
        phase2 = compute_phase_channel(batch_rgb)

        assert torch.allclose(phase1, phase2)

    def test_phase_channel_empty_batch(self):
        """Test phase channel with empty batch."""
        empty_batch = torch.empty(0, 3, 256, 256)

        phase_channel = compute_phase_channel(empty_batch)

        assert phase_channel.shape == (0, 1, 256, 256)


class TestAdapterInterfaces:
    """Test adapter function interfaces without real models."""

    def test_xception_predict_probs_interface(self):
        """Test Xception predict_probs interface."""
        # Create mock model
        mock_model = MagicMock()
        mock_features = torch.randn(4, 512)  # Mock features
        mock_logits = torch.tensor([[0.1, 0.9], [0.7, 0.3], [0.4, 0.6], [0.2, 0.8]])
        mock_model.features.return_value = mock_features
        mock_model.classifier.return_value = mock_logits

        batch = torch.randn(4, 3, 256, 256)
        logits, probs = predict_probs_xception(mock_model, batch)

        # Check interface compliance
        assert logits.shape == (4, 2)
        assert probs.shape == (4,)
        assert logits.device.type == "cpu" and probs.device.type == "cpu"
        assert torch.all(probs >= 0.0) and torch.all(probs <= 1.0)
        mock_model.features.assert_called_once_with(batch)
        mock_model.classifier.assert_called_once_with(mock_features)

    def test_spsl_predict_probs_interface(self):
        """Test SPSL predict_probs interface."""
        # Create mock model
        mock_model = MagicMock()
        mock_features = torch.randn(3, 512)
        mock_logits = torch.tensor([[0.2, 0.8], [0.6, 0.4], [0.3, 0.7]])
        mock_model.features.return_value = mock_features
        mock_model.classifier.return_value = mock_logits

        batch_rgb = torch.randn(3, 3, 256, 256)
        logits, probs = predict_probs_spsl(mock_model, batch_rgb)

        # Check interface compliance
        assert logits.shape == (3, 2)
        assert probs.shape == (3,)
        assert logits.device.type == "cpu" and probs.device.type == "cpu"
        assert torch.all(probs >= 0.0) and torch.all(probs <= 1.0)
        # Model should be called with 4-channel input (RGB + Phase)
        called_with = mock_model.features.call_args[0][0]
        assert called_with.shape == (3, 4, 256, 256)  # RGB + Phase

    def test_ucf_predict_probs_interface(self):
        """Test UCF predict_probs interface."""
        # Create mock model
        mock_model = MagicMock()
        mock_features = torch.randn(2, 512)
        mock_logits = torch.tensor([[0.4, 0.6], [0.8, 0.2]])
        mock_model.features_shared.return_value = mock_features
        mock_model.forward_shared_head.return_value = mock_logits

        batch_rgb = torch.randn(2, 3, 256, 256)
        logits, probs = predict_probs_ucf(mock_model, batch_rgb)

        # Check interface compliance
        assert logits.shape == (2, 2)
        assert probs.shape == (2,)
        assert logits.device.type == "cpu" and probs.device.type == "cpu"
        assert torch.all(probs >= 0.0) and torch.all(probs <= 1.0)
        mock_model.features_shared.assert_called_once_with(batch_rgb)
        mock_model.forward_shared_head.assert_called_once_with(mock_features)

    def test_empty_batch_handling(self):
        """Test all adapters handle empty batches correctly."""
        empty_batch = torch.empty(0, 3, 256, 256)
        mock_model = MagicMock()

        # All should return empty tensors with correct shapes
        xception_logits, xception_probs = predict_probs_xception(mock_model, empty_batch)
        assert xception_logits.shape == (0, 2)
        assert xception_probs.shape == (0,)
        assert xception_logits.dtype == torch.float32

        spsl_logits, spsl_probs = predict_probs_spsl(mock_model, empty_batch)
        assert spsl_logits.shape == (0, 2)
        assert spsl_probs.shape == (0,)
        assert spsl_logits.dtype == torch.float32

        ucf_logits, ucf_probs = predict_probs_ucf(mock_model, empty_batch)
        assert ucf_logits.shape == (0, 2)
        assert ucf_probs.shape == (0,)
        assert ucf_logits.dtype == torch.float32


class TestSkeletonModels:
    """Test skeleton model implementations."""

    def test_xception_skeleton_forward(self):
        """Test Xception skeleton can forward pass."""
        config = {"mode": "original", "num_classes": 2, "inc": 3, "dropout": False}
        model = XceptionBackboneSkeleton(config)
        model.eval()

        batch = torch.randn(2, 3, 256, 256)
        features = model.features(batch)
        logits = model.classifier(features)

        assert logits.shape == (2, 2)  # [batch, num_classes]
        assert torch.isfinite(logits).all()

    def test_spsl_skeleton_forward(self):
        """Test SPSL skeleton can forward pass with 4-channel input."""
        config = {"mode": "original", "num_classes": 2, "inc": 4, "dropout": False}
        model = SPSLBackboneSkeleton(config)
        model.eval()

        # 4-channel input (RGB + Phase)
        batch_4ch = torch.randn(2, 4, 256, 256)
        features = model.features(batch_4ch)
        logits = model.classifier(features)

        assert logits.shape == (2, 2)
        assert torch.isfinite(logits).all()

    def test_ucf_skeleton_forward(self):
        """Test UCF skeleton can forward pass."""
        config = {"mode": "adjust_channel", "num_classes": 2, "inc": 3, "dropout": False}
        model = UCFBackboneSkeleton(config)
        model.eval()

        batch = torch.randn(2, 3, 256, 256)
        shared_features = model.features_shared(batch)
        logits = model.forward_shared_head(shared_features)

        assert logits.shape == (2, 2)
        assert torch.isfinite(logits).all()


class TestWeightLoadingPatterns:
    """Test weight loading patterns match DeepfakeBench exactly."""

    def test_spsl_conv1_replacement_pattern(self):
        """Test SPSL conv1 weight replacement matches DeepfakeBench."""
        # Simulate original conv1 weights [32, 3, 3, 3]
        original_conv1 = torch.randn(32, 3, 3, 3)

        # Apply DeepfakeBench pattern: mean across RGB channels, repeat to 4
        avg_conv1_data = original_conv1.mean(dim=1, keepdim=True)  # [32, 1, 3, 3]
        new_conv1_weights = avg_conv1_data.repeat(1, 4, 1, 1)  # [32, 4, 3, 3]

        # Verify dimensions
        assert new_conv1_weights.shape == (32, 4, 3, 3)

        # Verify each input channel is identical (tiled from mean)
        for i in range(4):
            assert torch.allclose(new_conv1_weights[:, i], avg_conv1_data[:, 0])

        # Verify the mean relationship
        original_mean = original_conv1.mean(dim=1)
        for i in range(4):
            assert torch.allclose(new_conv1_weights[:, i], original_mean)