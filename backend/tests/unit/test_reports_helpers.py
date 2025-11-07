"""
Unit tests for reports helper functions.

Tests isolated computational logic without external dependencies:
- _calculate_top5_ensemble_score: Top-5 ensemble averaging from ML results
- _get_assessment: Score-to-risk threshold classification
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from api.routes.reports import _calculate_top5_ensemble_score, _get_assessment


class TestCalculateTop5EnsembleScore:
    """Test top-5 ensemble score calculation from ML results."""

    def test_normal_case_more_than_5_frames(self):
        """Test with more than 5 frames (all models present)."""
        ml_results = {
            "xception": {
                "frames": [
                    {"index": 0, "score": 0.9},
                    {"index": 1, "score": 0.8},
                    {"index": 2, "score": 0.7},
                    {"index": 3, "score": 0.6},
                    {"index": 4, "score": 0.5},
                    {"index": 5, "score": 0.4},
                ]
            },
            "spsl": {
                "frames": [
                    {"index": 0, "score": 0.85},
                    {"index": 1, "score": 0.75},
                    {"index": 2, "score": 0.65},
                    {"index": 3, "score": 0.55},
                    {"index": 4, "score": 0.45},
                    {"index": 5, "score": 0.35},
                ]
            },
            "ucf": {
                "frames": [
                    {"index": 0, "score": 0.95},
                    {"index": 1, "score": 0.85},
                    {"index": 2, "score": 0.75},
                    {"index": 3, "score": 0.65},
                    {"index": 4, "score": 0.55},
                    {"index": 5, "score": 0.45},
                ]
            },
        }

        result = _calculate_top5_ensemble_score(ml_results)

        # Should return a dict with score and classification
        assert result is not None
        assert "score" in result
        assert "classification" in result

        # Calculate expected ensemble scores
        # Frame 0: (0.9 + 0.85 + 0.95) / 3 = 0.9
        # Frame 1: (0.8 + 0.75 + 0.85) / 3 = 0.8
        # Frame 2: (0.7 + 0.65 + 0.75) / 3 = 0.7
        # Frame 3: (0.6 + 0.55 + 0.65) / 3 = 0.6
        # Frame 4: (0.5 + 0.45 + 0.55) / 3 = 0.5
        # Frame 5: (0.4 + 0.35 + 0.45) / 3 = 0.4
        # Top 5: [0.9, 0.8, 0.7, 0.6, 0.5]
        # Mean: (0.9 + 0.8 + 0.7 + 0.6 + 0.5) / 5 = 0.7

        assert abs(result["score"] - 0.7) < 0.01

    def test_exactly_5_frames(self):
        """Test with exactly 5 frames."""
        ml_results = {
            "xception": {
                "frames": [
                    {"index": 0, "score": 0.9},
                    {"index": 1, "score": 0.8},
                    {"index": 2, "score": 0.7},
                    {"index": 3, "score": 0.6},
                    {"index": 4, "score": 0.5},
                ]
            },
            "spsl": {
                "frames": [
                    {"index": 0, "score": 0.9},
                    {"index": 1, "score": 0.8},
                    {"index": 2, "score": 0.7},
                    {"index": 3, "score": 0.6},
                    {"index": 4, "score": 0.5},
                ]
            },
            "ucf": {
                "frames": [
                    {"index": 0, "score": 0.9},
                    {"index": 1, "score": 0.8},
                    {"index": 2, "score": 0.7},
                    {"index": 3, "score": 0.6},
                    {"index": 4, "score": 0.5},
                ]
            },
        }

        result = _calculate_top5_ensemble_score(ml_results)

        assert result is not None
        # All frames have same score across models, so ensemble = model score
        # Mean of [0.9, 0.8, 0.7, 0.6, 0.5] = 0.7
        assert abs(result["score"] - 0.7) < 0.01

    def test_fewer_than_5_frames(self):
        """Test with fewer than 5 frames (takes all available)."""
        ml_results = {
            "xception": {
                "frames": [
                    {"index": 0, "score": 0.9},
                    {"index": 1, "score": 0.7},
                    {"index": 2, "score": 0.5},
                ]
            },
            "spsl": {
                "frames": [
                    {"index": 0, "score": 0.8},
                    {"index": 1, "score": 0.6},
                    {"index": 2, "score": 0.4},
                ]
            },
            "ucf": {
                "frames": [
                    {"index": 0, "score": 1.0},
                    {"index": 1, "score": 0.8},
                    {"index": 2, "score": 0.6},
                ]
            },
        }

        result = _calculate_top5_ensemble_score(ml_results)

        assert result is not None
        # Ensemble scores:
        # Frame 0: (0.9 + 0.8 + 1.0) / 3 = 0.9
        # Frame 1: (0.7 + 0.6 + 0.8) / 3 = 0.7
        # Frame 2: (0.5 + 0.4 + 0.6) / 3 = 0.5
        # Mean: (0.9 + 0.7 + 0.5) / 3 = 0.7
        assert abs(result["score"] - 0.7) < 0.01

    def test_missing_model_data(self):
        """Test with one model missing (frames must have all 3 models)."""
        ml_results = {
            "xception": {
                "frames": [
                    {"index": 0, "score": 0.9},
                    {"index": 1, "score": 0.8},
                ]
            },
            "spsl": {
                "frames": [
                    {"index": 0, "score": 0.85},
                    # Frame 1 missing
                ]
            },
            "ucf": {
                "frames": [
                    {"index": 0, "score": 0.95},
                    {"index": 1, "score": 0.75},
                ]
            },
        }

        result = _calculate_top5_ensemble_score(ml_results)

        # Only frame 0 has all 3 models
        # Frame 0 ensemble: (0.9 + 0.85 + 0.95) / 3 = 0.9
        assert result is not None
        assert abs(result["score"] - 0.9) < 0.01

    def test_empty_ml_results(self):
        """Test with empty ML results."""
        result = _calculate_top5_ensemble_score({})
        assert result is None

        result_none = _calculate_top5_ensemble_score(None)
        assert result_none is None

    def test_no_frames_with_all_models(self):
        """Test when no frames have all 3 models."""
        ml_results = {
            "xception": {
                "frames": [
                    {"index": 0, "score": 0.9},
                ]
            },
            "spsl": {
                "frames": [
                    {"index": 1, "score": 0.85},
                ]
            },
            "ucf": {
                "frames": [
                    {"index": 2, "score": 0.95},
                ]
            },
        }

        result = _calculate_top5_ensemble_score(ml_results)

        # No frame has all 3 models
        assert result is None

    def test_partial_model_data(self):
        """Test with only some models present."""
        ml_results = {
            "xception": {
                "frames": [
                    {"index": 0, "score": 0.9},
                ]
            },
            "spsl": None,
            "ucf": None,
        }

        result = _calculate_top5_ensemble_score(ml_results)

        # Need all 3 models for ensemble
        assert result is None

    def test_missing_score_or_index(self):
        """Test handling of frames with missing score or index."""
        ml_results = {
            "xception": {
                "frames": [
                    {"index": 0, "score": 0.9},
                    {"index": 1},  # Missing score
                ]
            },
            "spsl": {
                "frames": [
                    {"index": 0, "score": 0.85},
                    {"score": 0.75},  # Missing index
                ]
            },
            "ucf": {
                "frames": [
                    {"index": 0, "score": 0.95},
                    {"index": 1, "score": 0.85},
                ]
            },
        }

        result = _calculate_top5_ensemble_score(ml_results)

        # Only frame 0 should be valid (has all 3 models with valid data)
        assert result is not None
        assert abs(result["score"] - 0.9) < 0.01

    def test_classification_included(self):
        """Test that classification is correctly determined based on score."""
        # High score (>= 0.9)
        ml_results_high = {
            "xception": {"frames": [{"index": 0, "score": 0.95}]},
            "spsl": {"frames": [{"index": 0, "score": 0.95}]},
            "ucf": {"frames": [{"index": 0, "score": 0.95}]},
        }

        result = _calculate_top5_ensemble_score(ml_results_high)
        assert result is not None
        assert result["classification"] == "Very likely fake"

        # Very low score (< 0.4) -> "Very likely real"
        ml_results_very_low = {
            "xception": {"frames": [{"index": 0, "score": 0.2}]},
            "spsl": {"frames": [{"index": 0, "score": 0.2}]},
            "ucf": {"frames": [{"index": 0, "score": 0.2}]},
        }

        result = _calculate_top5_ensemble_score(ml_results_very_low)
        assert result is not None
        assert result["classification"] == "Very likely real"

        # Medium-low score (0.4-0.6) -> "Likely real"
        ml_results_med_low = {
            "xception": {"frames": [{"index": 0, "score": 0.5}]},
            "spsl": {"frames": [{"index": 0, "score": 0.5}]},
            "ucf": {"frames": [{"index": 0, "score": 0.5}]},
        }

        result = _calculate_top5_ensemble_score(ml_results_med_low)
        assert result is not None
        assert result["classification"] == "Likely real"


class TestGetAssessment:
    """Test score-to-assessment threshold classification."""

    def test_low_risk_thresholds(self):
        """Test Low Risk classification (< 0.3)."""
        assert _get_assessment(0.0) == "Low Risk"
        assert _get_assessment(0.1) == "Low Risk"
        assert _get_assessment(0.29) == "Low Risk"

    def test_medium_risk_thresholds(self):
        """Test Medium Risk classification (0.3 <= score < 0.5)."""
        assert _get_assessment(0.3) == "Medium Risk"
        assert _get_assessment(0.4) == "Medium Risk"
        assert _get_assessment(0.49) == "Medium Risk"

    def test_high_risk_thresholds(self):
        """Test High Risk classification (0.5 <= score < 0.7)."""
        assert _get_assessment(0.5) == "High Risk"
        assert _get_assessment(0.6) == "High Risk"
        assert _get_assessment(0.69) == "High Risk"

    def test_critical_risk_thresholds(self):
        """Test Critical classification (>= 0.7)."""
        assert _get_assessment(0.7) == "Critical"
        assert _get_assessment(0.85) == "Critical"
        assert _get_assessment(1.0) == "Critical"

    def test_boundary_values(self):
        """Test exact threshold boundaries."""
        # Exact boundaries
        assert _get_assessment(0.3) == "Medium Risk"  # Exactly 0.3
        assert _get_assessment(0.5) == "High Risk"  # Exactly 0.5
        assert _get_assessment(0.7) == "Critical"  # Exactly 0.7

        # Just below boundaries
        assert _get_assessment(0.2999) == "Low Risk"
        assert _get_assessment(0.4999) == "Medium Risk"
        assert _get_assessment(0.6999) == "High Risk"

    def test_extreme_values(self):
        """Test edge case values."""
        # Minimum valid score
        assert _get_assessment(0.0) == "Low Risk"

        # Maximum valid score
        assert _get_assessment(1.0) == "Critical"

        # Values slightly outside normal range (should still work)
        assert _get_assessment(-0.1) == "Low Risk"  # Negative (below threshold)
        assert _get_assessment(1.5) == "Critical"  # Above 1.0

    def test_precision_handling(self):
        """Test that function handles floating point precision correctly."""
        # Test values very close to thresholds
        assert _get_assessment(0.30000001) == "Medium Risk"
        assert _get_assessment(0.29999999) == "Low Risk"
        assert _get_assessment(0.50000001) == "High Risk"
        assert _get_assessment(0.49999999) == "Medium Risk"
