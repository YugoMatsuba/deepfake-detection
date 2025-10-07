# test_models.py - Unit tests for model adapters (no real weights required)

import numpy as np
import torch
import pytest
from collections import OrderedDict
from unittest.mock import patch, MagicMock
from types import SimpleNamespace

from ml.models.utils import (
    strip_module_prefix,
    fix_pointwise_separable_convs,
    drop_fc_keys,
    softmax_fake
)
from ml.models.spsl_infer import compute_phase_channel
from ml.models.xception_infer import predict_probs_xception
from ml.models.xception_arch import Xception
from ml.models.spsl_infer import predict_probs_spsl, load_spsl
from ml.models.ucf_infer import predict_probs_ucf, load_ucf


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

    def test_softmax_fake_assertion(self):
        """Test that softmax_fake asserts on wrong logit shapes."""
        # Wrong shapes should trigger assertion
        with pytest.raises(AssertionError, match="Expected 2-class logits"):
            softmax_fake(torch.randn(4, 3))  # 3 classes instead of 2

        with pytest.raises(AssertionError, match="Expected 2-class logits"):
            softmax_fake(torch.randn(4,))  # 1D instead of 2D

        # Correct shape should work
        result = softmax_fake(torch.randn(4, 2))
        assert result.shape == (4,)


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
        mock_model.training = False
        mock_model.parameters.return_value = iter([torch.nn.Parameter(torch.empty(0))])  # real param → real device
        mock_model.last_linear = SimpleNamespace(in_features=2048)  # matches real Xception feature dim
        mock_model.mode = "original"  # Real Xception mode

        mock_features = torch.randn(4, 2048)  # Mock features matching real Xception dim
        mock_logits = torch.tensor([[0.1, 0.9], [0.7, 0.3], [0.4, 0.6], [0.2, 0.8]])
        mock_model.features.return_value = mock_features

        # Mimic real Xception behavior: classifier sets last_emb
        def _classifier_side_effect(x):
            mock_model.last_emb = mock_features  # Real Xception.classifier() sets this
            return mock_logits
        mock_model.classifier.side_effect = _classifier_side_effect

        batch = torch.randn(4, 3, 256, 256)
        result_dict = predict_probs_xception(mock_model, batch)

        # Check DeepfakeBench dictionary format
        assert isinstance(result_dict, dict)
        assert set(result_dict.keys()) == {'cls', 'prob', 'feat'}

        logits = result_dict['cls']
        probs = result_dict['prob']
        features = result_dict['feat']

        assert logits.shape == (4, 2)
        assert probs.shape == (4,)
        assert features.shape == (4, 2048)  # Match real Xception feature dim
        assert logits.device.type == "cpu" and probs.device.type == "cpu"
        assert torch.all(probs >= 0.0) and torch.all(probs <= 1.0)
        mock_model.features.assert_called_once_with(batch)
        mock_model.classifier.assert_called_once_with(mock_features)

    def test_spsl_predict_probs_interface(self):
        """Test SPSL predict_probs interface."""
        # Create mock model
        mock_model = MagicMock()
        mock_model.training = False
        mock_model.parameters.return_value = iter([torch.nn.Parameter(torch.empty(0))])  # real param → real device
        mock_model.last_linear = SimpleNamespace(in_features=2048)  # SPSL uses original Xception backbone

        mock_features = torch.randn(3, 2048, 8, 8)  # Mock 4D features from backbone
        mock_logits = torch.tensor([[0.2, 0.8], [0.6, 0.4], [0.3, 0.7]])
        mock_emb = torch.randn(3, 2048)  # Mock pooled embedding
        mock_model.features.return_value = mock_features
        mock_model.classifier.return_value = mock_logits
        mock_model.last_emb = mock_emb  # Xception sets this in classifier()

        batch_rgb = torch.randn(3, 3, 256, 256)
        result_dict = predict_probs_spsl(mock_model, batch_rgb)

        # Check DeepfakeBench dictionary format
        assert isinstance(result_dict, dict)
        assert set(result_dict.keys()) == {'cls', 'prob', 'feat'}

        logits = result_dict['cls']
        probs = result_dict['prob']
        features = result_dict['feat']

        assert logits.shape == (3, 2)
        assert probs.shape == (3,)
        assert features.shape == (3, 2048)  # SPSL uses original Xception backbone (2048 features)
        assert logits.device.type == "cpu" and probs.device.type == "cpu"
        assert torch.all(probs >= 0.0) and torch.all(probs <= 1.0)
        # Model should be called with 4-channel input (RGB + Phase)
        called_with = mock_model.features.call_args[0][0]
        assert called_with.shape == (3, 4, 256, 256)  # RGB + Phase

    def test_ucf_predict_probs_interface(self):
        """Test UCF predict_probs interface."""
        # Create mock model
        mock_model = MagicMock()
        mock_model.training = False
        mock_model.parameters.return_value = iter([torch.nn.Parameter(torch.empty(0))])  # real param → real device
        mock_model.shared_feat_dim = 256  # UCF shared features are 256-dim

        mock_features = torch.randn(2, 256)  # Mock shared features (256-dim)
        mock_logits = torch.tensor([[0.4, 0.6], [0.8, 0.2]])

        # Mock the forward_inference method that returns DeepfakeBench format
        mock_pred_dict = {'cls': mock_logits, 'feat': mock_features}
        mock_model.forward_inference.return_value = mock_pred_dict

        batch_rgb = torch.randn(2, 3, 256, 256)
        result_dict = predict_probs_ucf(mock_model, batch_rgb)

        # Check DeepfakeBench dictionary format
        assert isinstance(result_dict, dict)
        assert set(result_dict.keys()) == {'cls', 'prob', 'feat'}

        logits = result_dict['cls']
        probs = result_dict['prob']
        features = result_dict['feat']

        assert logits.shape == (2, 2)
        assert probs.shape == (2,)
        assert features.shape == (2, 256)  # UCF shared features are 256-dim
        assert logits.device.type == "cpu" and probs.device.type == "cpu"
        assert torch.all(probs >= 0.0) and torch.all(probs <= 1.0)

        # Verify forward_inference was called with correct data_dict format
        mock_model.forward_inference.assert_called_once()
        call_args = mock_model.forward_inference.call_args[0][0]
        assert 'image' in call_args
        assert torch.equal(call_args['image'], batch_rgb)

    def test_empty_batch_handling(self):
        """Test all adapters handle empty batches correctly."""
        empty_batch = torch.empty(0, 3, 256, 256)
        mock_model = MagicMock()
        mock_model.training = False
        mock_model.parameters.return_value = iter([torch.nn.Parameter(torch.empty(0))])  # real param → real device

        # Set up mock feature dimensions to match real models
        mock_model.last_linear = SimpleNamespace(in_features=2048)  # Real Xception feature dim
        mock_model.head_sha = SimpleNamespace(in_features=256)      # UCF shared head expects 256-dim input
        mock_model.shared_feat_dim = 256  # UCF shared feature dimension
        mock_model.mode = "original"  # Real Xception mode

        # All should return empty dictionaries with correct shapes
        xception_result = predict_probs_xception(mock_model, empty_batch)
        assert isinstance(xception_result, dict)
        assert xception_result['cls'].shape == (0, 2)
        assert xception_result['prob'].shape == (0,)
        assert xception_result['feat'].shape == (0, 2048)  # Real Xception feature dim

        spsl_result = predict_probs_spsl(mock_model, empty_batch)
        assert isinstance(spsl_result, dict)
        assert spsl_result['cls'].shape == (0, 2)
        assert spsl_result['prob'].shape == (0,)
        assert spsl_result['feat'].shape == (0, 2048)  # SPSL uses original Xception backbone (2048 features)
        # Verify all outputs are on CPU
        assert spsl_result['cls'].device.type == 'cpu'
        assert spsl_result['prob'].device.type == 'cpu'
        assert spsl_result['feat'].device.type == 'cpu'

        ucf_result = predict_probs_ucf(mock_model, empty_batch)
        assert isinstance(ucf_result, dict)
        assert ucf_result['cls'].shape == (0, 2)
        assert ucf_result['prob'].shape == (0,)
        assert ucf_result['feat'].shape == (0, 256)  # UCF shared features are 256-dim


class TestModelImplementations:
    """Test model implementations (real Xception + skeleton SPSL/UCF)."""

    def test_xception_real_forward(self):
        """Test real Xception architecture can forward pass."""
        config = {"mode": "original", "num_classes": 2, "inc": 3, "dropout": False}
        model = Xception(config)
        model.eval()

        batch = torch.randn(2, 3, 256, 256)
        features = model.features(batch)
        logits = model.classifier(features)

        assert logits.shape == (2, 2)  # [batch, num_classes]
        assert torch.isfinite(logits).all()
        # Real Xception should have 2048 features in original mode
        if len(features.shape) == 4:
            # Features might still be spatial, so check after global avg pooling
            import torch.nn.functional as F
            pooled_features = F.adaptive_avg_pool2d(features, (1, 1)).view(features.size(0), -1)
            assert pooled_features.shape == (2, 2048)
        else:
            assert features.shape == (2, 2048)

    def test_spsl_real_forward(self):
        """Test SPSL with real Xception can forward pass with 4-channel input."""
        model = load_spsl("", "cpu")  # No weights for testing
        model.eval()

        # Test conv1 replacement worked
        assert model.conv1.in_channels == 4, f"Expected 4 input channels, got {model.conv1.in_channels}"
        assert model.conv1.bias is None, "Conv1 should be bias-free"

        # Test forward pass with dummy RGB input (adapter handles 3→4 channel conversion)
        batch_rgb = torch.randn(2, 3, 256, 256)
        result = predict_probs_spsl(model, batch_rgb)

        assert result['cls'].shape == (2, 2)
        assert result['prob'].shape == (2,)
        assert result['feat'].shape == (2, 2048)  # Real Xception features in original mode
        assert torch.isfinite(result['cls']).all()
        assert torch.all(result['prob'] >= 0.0) and torch.all(result['prob'] <= 1.0)

    def test_spsl_conv1_replacement(self):
        """Test SPSL conv1 replacement follows exact DeepfakeBench pattern."""
        from ml.models.spsl_infer import _replace_conv1_with_4ch
        from ml.models.xception_arch import Xception

        # Start with 3-channel Xception
        config = {"mode": "original", "num_classes": 2, "inc": 3, "dropout": False}
        model = Xception(config)

        # Verify original state
        assert model.conv1.in_channels == 3
        original_weight = model.conv1.weight.data.clone()  # [32, 3, 3, 3]

        # Apply replacement without checkpoint data
        _replace_conv1_with_4ch(model, conv1_data=None)

        # Verify replacement
        assert model.conv1.in_channels == 4
        assert model.conv1.bias is None
        assert model.conv1.weight.shape == (32, 4, 3, 3)

        # Test with checkpoint data (simulate DeepfakeBench pattern)
        model2 = Xception(config)
        conv1_data = torch.randn(32, 3, 3, 3)  # Simulated checkpoint
        _replace_conv1_with_4ch(model2, conv1_data=conv1_data)

        # Verify seeding pattern matches DeepfakeBench
        expected_avg = conv1_data.mean(dim=1, keepdim=True)  # [32, 1, 3, 3]
        expected_weight = expected_avg.repeat(1, 4, 1, 1)    # [32, 4, 3, 3]
        assert torch.allclose(model2.conv1.weight.data, expected_weight)

    def test_ucf_real_forward(self):
        """Test UCF with real dual Xception encoders can forward pass."""
        model = load_ucf("", "cpu")  # No weights for testing
        model.eval()

        # Test architecture components
        assert model.encoder_feat_dim == 512, f"Expected 512 features (adjust_channel), got {model.encoder_feat_dim}"
        assert model.half_fingerprint_dim == 256, f"Expected 256 shared features, got {model.half_fingerprint_dim}"
        assert hasattr(model, 'encoder_f'), "Missing forgery encoder"
        assert hasattr(model, 'encoder_c'), "Missing content encoder"
        assert hasattr(model, 'head_sha'), "Missing shared head"
        assert hasattr(model, 'block_sha'), "Missing shared projection block"

        # Test forward pass with dummy RGB input
        batch_rgb = torch.randn(2, 3, 256, 256)
        result = predict_probs_ucf(model, batch_rgb)

        assert result['cls'].shape == (2, 2)
        assert result['prob'].shape == (2,)
        assert result['feat'].shape == (2, 256)  # UCF shared features are 256-dim
        assert torch.isfinite(result['cls']).all()
        assert torch.all(result['prob'] >= 0.0) and torch.all(result['prob'] <= 1.0)


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

    def test_spsl_phase_computation_robustness(self):
        """Test SPSL phase computation handles edge cases properly."""
        from ml.models.spsl_infer import compute_phase_channel

        # Test normal case
        batch = torch.randn(2, 3, 256, 256, dtype=torch.float32)
        phase = compute_phase_channel(batch)
        assert phase.shape == (2, 1, 256, 256)
        assert phase.dtype == torch.float32
        assert phase.device == batch.device
        assert torch.isfinite(phase).all()

        # Test empty batch
        empty_batch = torch.empty(0, 3, 256, 256, dtype=torch.float32)
        empty_phase = compute_phase_channel(empty_batch)
        assert empty_phase.shape == (0, 1, 256, 256)
        assert empty_phase.dtype == torch.float32

        # Test deterministic
        phase1 = compute_phase_channel(batch)
        phase2 = compute_phase_channel(batch)
        assert torch.allclose(phase1, phase2)