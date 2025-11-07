"""
Pure function tests for ML classification threshold configuration.

Tests the classification logic and methodology description generation
from api/config/ml_thresholds.py without any external dependencies.
"""

from api.config.ml_thresholds import (
    get_classification,
    get_methodology_description,
    ML_THRESHOLDS
)


class TestGetClassification:
    """Test get_classification score-to-label mapping."""

    # Very likely fake (0.9 - 1.0)
    def test_very_likely_fake_at_threshold(self):
        """Score of 0.9 should be classified as 'Very likely fake'."""
        assert get_classification(0.9) == "Very likely fake"

    def test_very_likely_fake_above_threshold(self):
        """Score above 0.9 should be classified as 'Very likely fake'."""
        assert get_classification(0.95) == "Very likely fake"

    def test_very_likely_fake_at_maximum(self):
        """Score of 1.0 should be classified as 'Very likely fake'."""
        assert get_classification(1.0) == "Very likely fake"

    # Likely fake (0.85 - 0.899...)
    def test_likely_fake_at_threshold(self):
        """Score of 0.85 should be classified as 'Likely fake'."""
        assert get_classification(0.85) == "Likely fake"

    def test_likely_fake_mid_range(self):
        """Score in middle of range should be classified as 'Likely fake'."""
        assert get_classification(0.87) == "Likely fake"

    def test_likely_fake_just_below_next_threshold(self):
        """Score just below 0.9 should be classified as 'Likely fake'."""
        assert get_classification(0.899) == "Likely fake"

    # Possibly fake (0.8 - 0.849...)
    def test_possibly_fake_at_threshold(self):
        """Score of 0.8 should be classified as 'Possibly fake'."""
        assert get_classification(0.8) == "Possibly fake"

    def test_possibly_fake_mid_range(self):
        """Score in middle of range should be classified as 'Possibly fake'."""
        assert get_classification(0.82) == "Possibly fake"

    def test_possibly_fake_just_below_next_threshold(self):
        """Score just below 0.85 should be classified as 'Possibly fake'."""
        assert get_classification(0.849) == "Possibly fake"

    # Uncertain (0.6 - 0.799...)
    def test_uncertain_at_threshold(self):
        """Score of 0.6 should be classified as 'Uncertain'."""
        assert get_classification(0.6) == "Uncertain"

    def test_uncertain_mid_range(self):
        """Score in middle of range should be classified as 'Uncertain'."""
        assert get_classification(0.7) == "Uncertain"

    def test_uncertain_just_below_next_threshold(self):
        """Score just below 0.8 should be classified as 'Uncertain'."""
        assert get_classification(0.799) == "Uncertain"

    # Likely real (0.4 - 0.599...)
    def test_likely_real_at_threshold(self):
        """Score of 0.4 should be classified as 'Likely real'."""
        assert get_classification(0.4) == "Likely real"

    def test_likely_real_mid_range(self):
        """Score in middle of range should be classified as 'Likely real'."""
        assert get_classification(0.5) == "Likely real"

    def test_likely_real_just_below_next_threshold(self):
        """Score just below 0.6 should be classified as 'Likely real'."""
        assert get_classification(0.599) == "Likely real"

    # Very likely real (0.0 - 0.399...)
    def test_very_likely_real_at_threshold(self):
        """Score of 0.0 should be classified as 'Very likely real'."""
        assert get_classification(0.0) == "Very likely real"

    def test_very_likely_real_mid_range(self):
        """Score in lower range should be classified as 'Very likely real'."""
        assert get_classification(0.2) == "Very likely real"

    def test_very_likely_real_just_below_next_threshold(self):
        """Score just below 0.4 should be classified as 'Very likely real'."""
        assert get_classification(0.399) == "Very likely real"

    # Edge cases
    def test_negative_score_returns_unknown(self):
        """Negative scores should return Unknown (invalid input)."""
        # While scores should be 0-1, negative scores are invalid
        # and should return fallback classification
        assert get_classification(-0.1) == "Unknown"

    def test_score_above_one_gets_very_likely_fake(self):
        """Scores above 1.0 should return highest classification."""
        # While scores should be 0-1, ensure graceful handling
        assert get_classification(1.5) == "Very likely fake"


class TestGetMethodologyDescription:
    """Test methodology description generation."""

    def test_description_contains_overall_score_explanation(self):
        """Methodology should explain how overall score is calculated."""
        desc = get_methodology_description()
        assert "average of the top 5 highest-scoring frames" in desc

    def test_description_contains_ensemble_explanation(self):
        """Methodology should explain ensemble averaging across models."""
        desc = get_methodology_description()
        assert "ensemble average across all ML models" in desc

    def test_description_mentions_model_names(self):
        """Methodology should list the ML models used."""
        desc = get_methodology_description()
        assert "Xception" in desc
        assert "SPSL" in desc
        assert "UCF" in desc

    def test_description_contains_classification_bands(self):
        """Methodology should include all classification bands."""
        desc = get_methodology_description()

        # Check all unique labels from ML_THRESHOLDS are present
        for _, label in ML_THRESHOLDS:
            assert label in desc

    def test_description_contains_very_likely_fake_band(self):
        """Methodology should include 'Very likely fake' band."""
        desc = get_methodology_description()
        assert "Very likely fake: 90-100%" in desc

    def test_description_contains_likely_fake_band(self):
        """Methodology should include 'Likely fake' band."""
        desc = get_methodology_description()
        assert "Likely fake: 85-89%" in desc

    def test_description_contains_possibly_fake_band(self):
        """Methodology should include 'Possibly fake' band."""
        desc = get_methodology_description()
        assert "Possibly fake: 80-84%" in desc

    def test_description_contains_uncertain_band(self):
        """Methodology should include 'Uncertain' band."""
        desc = get_methodology_description()
        assert "Uncertain: 60-79%" in desc

    def test_description_contains_likely_real_band(self):
        """Methodology should include 'Likely real' band."""
        desc = get_methodology_description()
        assert "Likely real: 40-59%" in desc

    def test_description_contains_very_likely_real_band(self):
        """Methodology should include 'Very likely real' band."""
        desc = get_methodology_description()
        assert "Very likely real: 0-39%" in desc

    def test_description_contains_interpretation_guidance(self):
        """Methodology should explain how to interpret scores."""
        desc = get_methodology_description()
        assert "Higher scores indicate greater likelihood of manipulation" in desc

    def test_description_is_single_paragraph(self):
        """Methodology should be a single continuous paragraph."""
        desc = get_methodology_description()
        # Should not contain newlines (single paragraph format)
        assert "\n" not in desc

    def test_description_bands_are_comma_separated(self):
        """Classification bands should be comma-separated."""
        desc = get_methodology_description()
        # Find the "Classification bands:" section and verify commas
        assert "Classification bands:" in desc
        bands_section = desc.split("Classification bands:")[1].split(".")[0]
        assert "," in bands_section

    def test_description_format_matches_expected_structure(self):
        """Methodology should follow expected structure."""
        desc = get_methodology_description()

        # Should have three sentences: overall score, classification bands, interpretation
        sentences = [s.strip() for s in desc.split(".") if s.strip()]
        assert len(sentences) == 3

        # First sentence about overall score
        assert "overall score" in sentences[0].lower()

        # Second sentence about classification bands
        assert "classification bands" in sentences[1].lower()

        # Third sentence about interpretation
        assert "higher scores" in sentences[2].lower()
