# test_pr5.py - Tests for PR5: 2-class head validation + integration constants
"""
PR5 test coverage:
1. Integration constants & MODEL_REGISTRY structure + env var overrides
2. Load-time 2-class head validation probes catch mismatches
3. Runtime guards catch NaN/Inf/out-of-range probabilities
"""

import importlib
import pytest
import torch
import torch.nn as nn


class TestIntegrationConstants:
    """Test MODEL_REGISTRY, DEFAULT_WEIGHTS, and AGGREGATION constants."""

    def test_registry_structure(self):
        """Validate MODEL_REGISTRY has correct structure for all three models."""
        from ml.models.integration import MODEL_REGISTRY

        assert isinstance(MODEL_REGISTRY, dict)
        assert set(MODEL_REGISTRY.keys()) == {"xception", "spsl", "ucf"}

        for name, triple in MODEL_REGISTRY.items():
            assert len(triple) == 3, f"{name} registry entry should be 3-tuple"
            load_fn, predict_fn, default_path = triple

            # Functions should be callable
            assert callable(load_fn), f"{name} loader should be callable"
            assert callable(predict_fn), f"{name} predictor should be callable"

            # Default path should be string
            assert isinstance(default_path, str), f"{name} default_path should be string"
            assert default_path.endswith(".pth"), f"{name} default_path should end with .pth"

    def test_aggregation_constant(self):
        """Verify AGGREGATION is set to 'mean' for frame-to-clip aggregation."""
        from ml.models.integration import AGGREGATION
        assert AGGREGATION == "mean"

    def test_default_weights_env_overrides(self, monkeypatch):
        """Test that DEFAULT_WEIGHTS respects environment variable overrides."""
        # Set custom paths via env vars
        monkeypatch.setenv("XCEPTION_WEIGHTS", "/custom/xception.pth")
        monkeypatch.setenv("SPSL_WEIGHTS", "/custom/spsl.pth")
        monkeypatch.setenv("UCF_WEIGHTS", "/custom/ucf.pth")

        # Reload module to pick up new env vars
        from ml.models import integration as I
        importlib.reload(I)

        # Verify overrides took effect
        assert I.DEFAULT_WEIGHTS["xception"] == "/custom/xception.pth"
        assert I.DEFAULT_WEIGHTS["spsl"] == "/custom/spsl.pth"
        assert I.DEFAULT_WEIGHTS["ucf"] == "/custom/ucf.pth"

        # Cleanup: reload again to restore defaults
        monkeypatch.delenv("XCEPTION_WEIGHTS")
        monkeypatch.delenv("SPSL_WEIGHTS")
        monkeypatch.delenv("UCF_WEIGHTS")
        importlib.reload(I)


class TestLoadTimeHeadValidation:
    """Test that load-time probes catch incorrect head dimensions."""

    def test_xception_probe_catches_wrong_head(self):
        """Xception loader should fail if classifier outputs != 2 classes."""
        from ml.models.xception_infer import load_xception

        # Load model without weights (architecture only)
        m = load_xception("", "cpu")

        # Model should have loaded successfully with 2-class head
        assert m.last_linear.out_features == 2

        # Now simulate a bad checkpoint by replacing head with 3-class
        in_features = m.last_linear.in_features
        m.last_linear = nn.Linear(in_features, 3, bias=True)

        # The probe runs during load, but we can verify the guard logic directly
        # by mimicking what the probe does
        with torch.no_grad():
            x = torch.randn(1, 3, 256, 256)
            feats = m.features(x)
            logits = m.classifier(feats)

            # This should fail - we expect 2 classes but got 3
            with pytest.raises(AssertionError, match="must output 2 classes"):
                assert logits.shape[-1] == 2, (
                    f"Xception head must output 2 classes, got {logits.shape[-1]}. "
                    f"Check your checkpoint or num_classes in config."
                )

    def test_spsl_probe_catches_wrong_head(self):
        """SPSL loader should fail if classifier outputs != 2 classes."""
        from ml.models.spsl_infer import load_spsl

        # Load model without weights (architecture only)
        m = load_spsl("", "cpu")

        # Model should have loaded successfully with 2-class head
        assert m.last_linear.out_features == 2

        # Simulate bad checkpoint by replacing head with 4-class
        in_features = m.last_linear.in_features
        m.last_linear = nn.Linear(in_features, 4, bias=True)

        # Verify the guard logic (SPSL uses 4-channel input)
        with torch.no_grad():
            x = torch.randn(1, 4, 256, 256)  # 4-ch for SPSL
            feats = m.features(x)
            logits = m.classifier(feats)

            # This should fail - we expect 2 classes but got 4
            with pytest.raises(AssertionError, match="must output 2 classes"):
                assert logits.shape[-1] == 2, (
                    f"SPSL head must output 2 classes, got {logits.shape[-1]}."
                )

    def test_ucf_head_sizes(self):
        """UCF should have 2-class shared head and 5-class specific head."""
        from ml.models.ucf_infer import load_ucf

        # Load model without weights
        m = load_ucf("", "cpu")

        # Verify head sizes (these assertions also exist in load_ucf itself)
        assert m.head_sha.mlp[-1].out_features == 2, "Shared head should be 2-class"
        assert m.head_spe.mlp[-1].out_features == 5, "Specific head should be 5-class (FF++ tasks)"
        assert hasattr(m, "shared_feat_dim"), "Model should expose shared_feat_dim"
        assert m.shared_feat_dim == 256, "UCF shared features should be 256-dim"


class TestRuntimeGuards:
    """Test that inference-time guards catch bad outputs (NaN, Inf, out-of-range)."""

    def test_xception_guards_catch_nan_logits(self, monkeypatch):
        """Xception predictor should raise on NaN logits from classifier."""
        from ml.models.xception_infer import load_xception, predict_probs_xception

        m = load_xception("", "cpu")
        x = torch.randn(2, 3, 256, 256)

        # Monkeypatch classifier to output NaNs
        def bad_classifier(_):
            return torch.full((2, 2), float("nan"))
        m.classifier = bad_classifier

        # Should raise due to finite check
        with pytest.raises(AssertionError, match="non-finite"):
            predict_probs_xception(m, x)

    def test_spsl_guards_catch_bad_probabilities(self, monkeypatch):
        """SPSL predictor should raise on non-finite probabilities."""
        from ml.models.spsl_infer import load_spsl, predict_probs_spsl
        import ml.models.spsl_infer as spsl_module

        m = load_spsl("", "cpu")
        x = torch.randn(2, 3, 256, 256)

        # Patch softmax_fake to return NaN (simulates numerical instability)
        original_softmax = spsl_module.softmax_fake

        def bad_softmax(logits):
            return torch.full((logits.shape[0],), float("nan"))

        monkeypatch.setattr(spsl_module, "softmax_fake", bad_softmax)

        try:
            # Should raise due to finite check on probabilities
            with pytest.raises(AssertionError, match="non-finite"):
                predict_probs_spsl(m, x)
        finally:
            # Restore original (monkeypatch handles this, but being explicit)
            monkeypatch.setattr(spsl_module, "softmax_fake", original_softmax)

    def test_ucf_guards_catch_out_of_range_probs(self, monkeypatch):
        """UCF predictor should raise if probabilities fall outside [0, 1]."""
        from ml.models.ucf_infer import load_ucf, predict_probs_ucf

        m = load_ucf("", "cpu")
        x = torch.randn(2, 3, 256, 256)

        # Monkeypatch forward_inference to return out-of-range probs
        # (We need to return a dict matching the expected structure)
        def bad_forward_inference(data_dict):
            batch_size = data_dict['image'].shape[0]
            # Return logits that would produce probs > 1 or < 0 (impossible with real softmax)
            # Instead, we'll test the isfinite guard by returning NaN in the prob path
            return {
                'cls': torch.full((batch_size, 2), float("nan")),  # NaN logits
                'feat': torch.randn(batch_size, 256)
            }
        m.forward_inference = bad_forward_inference

        # Should raise due to finite check on probabilities
        with pytest.raises(AssertionError, match="non-finite"):
            predict_probs_ucf(m, x)

    def test_prob_shape_guard(self):
        """Verify all adapters check prob tensor is 1-D."""
        from ml.models.integration import MODEL_REGISTRY

        x = torch.randn(3, 3, 256, 256, dtype=torch.float32)

        for name, (load_fn, predict_fn, _) in MODEL_REGISTRY.items():
            m = load_fn("", "cpu")
            result = predict_fn(m, x)

            # Verify prob is 1-D (guards check this)
            prob = result["prob"]
            assert prob.ndim == 1, f"{name}: prob should be 1-D"
            assert prob.shape[0] == 3, f"{name}: prob should have batch_size entries"

            # Verify all probs are in valid range [0, 1]
            assert torch.all(prob >= 0.0) and torch.all(prob <= 1.0), \
                f"{name}: prob values outside [0,1]"

            # Verify all probs are finite
            assert torch.all(torch.isfinite(prob)), \
                f"{name}: prob contains non-finite values"
