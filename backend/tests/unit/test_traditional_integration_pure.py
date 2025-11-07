"""
Pure function tests for traditional forensics integration transforms.

Tests the dict transformation functions from api/traditional_integration.py
that convert forensics module outputs to API response format.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch
from api.traditional_integration import (
    _parse_frame_number,
    transform_ela_result,
    transform_noise_result,
    transform_lbp_result,
    run_traditional_forensics,
)


class TestParseFrameNumber:
    """Test _parse_frame_number regex parsing."""

    def test_parse_standard_frame_filename(self):
        """Parse standard frame filename format."""
        assert _parse_frame_number("frame_0005.jpg") == 5

    def test_parse_frame_with_leading_zeros(self):
        """Parse frame number with leading zeros."""
        assert _parse_frame_number("frame_0123.png") == 123

    def test_parse_frame_without_extension(self):
        """Parse frame number from filename without extension."""
        assert _parse_frame_number("frame_42") == 42

    def test_parse_frame_with_path(self):
        """Parse frame number from full path."""
        assert _parse_frame_number("/data/analyses/abc123/frames/frame_0007.jpg") == 7

    def test_parse_frame_no_digits(self):
        """Return None when no digits in filename."""
        assert _parse_frame_number("frame_abc.jpg") is None

    def test_parse_frame_none_input(self):
        """Return None for None input."""
        assert _parse_frame_number(None) is None

    def test_parse_frame_empty_string(self):
        """Return None for empty string."""
        assert _parse_frame_number("") is None

    def test_parse_frame_single_digit(self):
        """Parse single digit frame number."""
        assert _parse_frame_number("frame_0.jpg") == 0


class TestTransformElaResult:
    """Test transform_ela_result dict transformation."""

    def test_single_frame_mode(self):
        """Transform single-frame ELA result."""
        raw_result = {"mode": "single_frame", "frame": "frame_0005.jpg", "score": 2.34}
        result = transform_ela_result(raw_result, "test_analysis_id")

        assert result["score"] == 2.34
        assert len(result["frames"]) == 1
        assert result["frames"][0]["frame"] == "frame_0005.jpg"
        assert result["frames"][0]["score"] == 2.34
        assert result["frames"][0]["frame_number"] == 5
        assert result["frames"][0]["overlay_url"] == "/api/analyses/test_analysis_id/forensics/ela/frames/5/overlay"
        assert result["frames"][0]["requested_adhoc"] is True

    def test_single_frame_no_parse_frame_number(self):
        """Single-frame mode with unparseable frame name."""
        raw_result = {"mode": "single_frame", "frame": "invalid_frame.jpg", "score": 1.5}
        result = transform_ela_result(raw_result, "test_id")

        assert result["frames"][0]["frame_number"] is None
        assert result["frames"][0]["overlay_url"] is None

    def test_multi_frame_mode(self):
        """Transform multi-frame ELA result."""
        raw_result = {
            "mode": "multi_frame",
            "top_frames": [
                {"frame": "frame_0003.jpg", "score": 3.2, "raw_score": 3.2, "flagged": True},
                {"frame": "frame_0007.jpg", "score": 2.8, "raw_score": 2.8, "flagged": False},
            ],
        }
        result = transform_ela_result(raw_result, "analysis_abc")

        # Overall score should be MAX of all frames
        assert result["score"] == 3.2
        assert len(result["frames"]) == 2

        # First frame
        assert result["frames"][0]["frame"] == "frame_0003.jpg"
        assert result["frames"][0]["score"] == 3.2
        assert result["frames"][0]["raw_score"] == 3.2
        assert result["frames"][0]["frame_number"] == 3
        assert result["frames"][0]["overlay_url"] == "/api/analyses/analysis_abc/forensics/ela/frames/3/overlay"
        assert result["frames"][0]["flagged"] is True
        assert result["frames"][0]["requested_adhoc"] is False

        # Second frame
        assert result["frames"][1]["frame_number"] == 7
        assert result["frames"][1]["flagged"] is False

    def test_multi_frame_raw_score_fallback(self):
        """Multi-frame mode falls back to 'score' if no 'raw_score'."""
        raw_result = {"top_frames": [{"frame": "frame_0001.jpg", "score": 1.5}]}  # No raw_score
        result = transform_ela_result(raw_result, "test_id")

        assert result["frames"][0]["raw_score"] == 1.5
        assert result["frames"][0]["score"] == 1.5

    def test_empty_top_frames(self):
        """Empty top_frames list returns defaults."""
        raw_result = {"top_frames": []}
        result = transform_ela_result(raw_result, "test_id")

        assert result["score"] == 0.0
        assert result["frames"] == []

    def test_missing_top_frames_key(self):
        """Missing top_frames key returns defaults."""
        raw_result = {}
        result = transform_ela_result(raw_result, "test_id")

        assert result["score"] == 0.0
        assert result["frames"] == []


class TestTransformNoiseResult:
    """Test transform_noise_result dict transformation."""

    def test_single_frame_mode(self):
        """Transform single-frame noise result."""
        raw_result = {"mode": "single_frame", "frame": "frame_0010.jpg", "confidence": 0.82}
        result = transform_noise_result(raw_result, "test_analysis_id")

        assert result["confidence"] == 0.82
        assert result["score"] == 0.82  # DB compatibility
        assert len(result["frames"]) == 1
        assert result["frames"][0]["frame"] == "frame_0010.jpg"
        assert result["frames"][0]["confidence"] == 0.82
        assert result["frames"][0]["frame_number"] == 10
        assert result["frames"][0]["overlay_url"] == "/api/analyses/test_analysis_id/forensics/noise/frames/10/overlay"
        assert result["frames"][0]["requested_adhoc"] is True

    def test_single_frame_no_parse_frame_number(self):
        """Single-frame mode with unparseable frame name."""
        raw_result = {"mode": "single_frame", "frame": "bad_name.jpg", "confidence": 0.5}
        result = transform_noise_result(raw_result, "test_id")

        assert result["frames"][0]["frame_number"] is None
        assert result["frames"][0]["overlay_url"] is None

    def test_multi_frame_mode(self):
        """Transform multi-frame noise result."""
        raw_result = {
            "mode": "multi_frame",
            "top_frames": [
                {"frame": "frame_0002.jpg", "score": 2.1, "raw_score": 2.1, "flagged": True},
                {"frame": "frame_0008.jpg", "score": 1.7, "raw_score": 1.7, "flagged": False},
            ],
        }
        result = transform_noise_result(raw_result, "analysis_xyz")

        # Overall score/confidence should be MAX z-score
        assert result["confidence"] == 2.1
        assert result["score"] == 2.1
        assert len(result["frames"]) == 2

        # First frame
        assert result["frames"][0]["frame"] == "frame_0002.jpg"
        assert result["frames"][0]["confidence"] == 2.1
        assert result["frames"][0]["score"] == 2.1
        assert result["frames"][0]["raw_score"] == 2.1
        assert result["frames"][0]["frame_number"] == 2
        assert result["frames"][0]["overlay_url"] == "/api/analyses/analysis_xyz/forensics/noise/frames/2/overlay"
        assert result["frames"][0]["flagged"] is True
        assert result["frames"][0]["requested_adhoc"] is False

        # Second frame
        assert result["frames"][1]["frame_number"] == 8
        assert result["frames"][1]["flagged"] is False

    def test_multi_frame_raw_score_fallback(self):
        """Multi-frame mode falls back to 'score' if no 'raw_score'."""
        raw_result = {"top_frames": [{"frame": "frame_0003.jpg", "score": 0.9}]}  # No raw_score
        result = transform_noise_result(raw_result, "test_id")

        assert result["frames"][0]["raw_score"] == 0.9
        assert result["frames"][0]["confidence"] == 0.9
        assert result["frames"][0]["score"] == 0.9

    def test_empty_top_frames(self):
        """Empty top_frames list returns defaults."""
        raw_result = {"top_frames": []}
        result = transform_noise_result(raw_result, "test_id")

        assert result["confidence"] == 0.0
        assert result["score"] == 0.0
        assert result["frames"] == []

    def test_missing_top_frames_key(self):
        """Missing top_frames key returns defaults."""
        raw_result = {}
        result = transform_noise_result(raw_result, "test_id")

        assert result["confidence"] == 0.0
        assert result["score"] == 0.0
        assert result["frames"] == []


class TestTransformLbpResult:
    """Test transform_lbp_result dict transformation."""

    def test_single_frame_mode(self):
        """Transform single-frame LBP result."""
        raw_result = {"mode": "single_frame", "frame": "frame_0012.jpg", "score": 0.67}
        result = transform_lbp_result(raw_result, "test_analysis_id")

        assert result["score"] == 0.67
        assert len(result["frames"]) == 1
        assert result["frames"][0]["frame"] == "frame_0012.jpg"
        assert result["frames"][0]["score"] == 0.67
        assert result["frames"][0]["frame_number"] == 12
        assert result["frames"][0]["overlay_url"] == "/api/analyses/test_analysis_id/forensics/lbp/frames/12/overlay"
        assert result["frames"][0]["requested_adhoc"] is True

    def test_single_frame_no_parse_frame_number(self):
        """Single-frame mode with unparseable frame name."""
        raw_result = {"mode": "single_frame", "frame": "unknown.jpg", "score": 0.4}
        result = transform_lbp_result(raw_result, "test_id")

        assert result["frames"][0]["frame_number"] is None
        assert result["frames"][0]["overlay_url"] is None

    def test_multi_frame_mode(self):
        """Transform multi-frame LBP result."""
        raw_result = {
            "mode": "multi_frame",
            "top_frames": [
                {"frame": "frame_0004.jpg", "score": 0.85, "normalized_score": 0.85, "raw_score": 0.85, "flagged": True},
                {"frame": "frame_0009.jpg", "score": 0.72, "normalized_score": 0.72, "raw_score": 0.72, "flagged": False},
            ],
        }
        result = transform_lbp_result(raw_result, "analysis_lbp")

        # Overall score should be MAX of all frames
        assert result["score"] == 0.85
        assert len(result["frames"]) == 2

        # First frame
        assert result["frames"][0]["frame"] == "frame_0004.jpg"
        assert result["frames"][0]["score"] == 0.85
        assert result["frames"][0]["raw_score"] == 0.85
        assert result["frames"][0]["frame_number"] == 4
        assert result["frames"][0]["overlay_url"] == "/api/analyses/analysis_lbp/forensics/lbp/frames/4/overlay"
        assert result["frames"][0]["flagged"] is True
        assert result["frames"][0]["requested_adhoc"] is False

        # Second frame
        assert result["frames"][1]["frame_number"] == 9
        assert result["frames"][1]["flagged"] is False

    def test_multi_frame_normalized_score_fallback(self):
        """Multi-frame mode falls back to 'score' if no 'normalized_score'."""
        raw_result = {"top_frames": [{"frame": "frame_0001.jpg", "score": 0.6, "raw_score": 0.6}]}  # No normalized_score
        result = transform_lbp_result(raw_result, "test_id")

        assert result["frames"][0]["score"] == 0.6
        assert result["frames"][0]["raw_score"] == 0.6

    def test_multi_frame_raw_score_fallback_to_score(self):
        """Multi-frame mode falls back to 'score' if no 'raw_score'."""
        raw_result = {"top_frames": [{"frame": "frame_0001.jpg", "normalized_score": 0.55}]}  # No raw_score or score
        result = transform_lbp_result(raw_result, "test_id")

        # raw_score falls back to score field (0.0 default)
        assert result["frames"][0]["raw_score"] == 0.0
        assert result["frames"][0]["score"] == 0.55

    def test_empty_top_frames(self):
        """Empty top_frames list returns defaults."""
        raw_result = {"top_frames": []}
        result = transform_lbp_result(raw_result, "test_id")

        assert result["score"] == 0.0
        assert result["frames"] == []

    def test_missing_top_frames_key(self):
        """Missing top_frames key returns defaults."""
        raw_result = {}
        result = transform_lbp_result(raw_result, "test_id")

        assert result["score"] == 0.0
        assert result["frames"] == []


class TestRunTraditionalForensics:
    """Test run_traditional_forensics orchestration."""

    def test_empty_modules_list_returns_empty_dict(self):
        """Empty modules list returns empty dict immediately."""
        result = run_traditional_forensics("/video.mp4", [], "test_id")
        assert result == {}

    @patch("api.traditional_integration.extract_frames")
    @patch("api.traditional_integration.DATA_ROOT")
    def test_frame_extraction_failure_returns_errors_for_all_modules(self, mock_data_root, mock_extract):
        """Frame extraction failure returns error for all requested modules."""
        # Mock DATA_ROOT to use temp directory
        mock_data_root.__truediv__ = lambda self, x: Path(tempfile.gettempdir()) / x
        mock_extract.side_effect = RuntimeError("Failed to extract frames")

        result = run_traditional_forensics("/video.mp4", ["ela", "noise", "lbp"], "test_id")

        # All modules should have error
        assert "ela" in result
        assert "noise" in result
        assert "lbp" in result

        for module_name in ["ela", "noise", "lbp"]:
            assert result[module_name]["score"] is None
            assert "Frame extraction failed" in result[module_name]["error"]

    @patch("api.traditional_integration.extract_frames")
    @patch("api.traditional_integration.DATA_ROOT")
    def test_empty_frames_extraction_returns_error(self, mock_data_root, mock_extract):
        """Empty frames list from extraction returns error."""
        mock_data_root.__truediv__ = lambda self, x: Path(tempfile.gettempdir()) / x
        mock_extract.return_value = []  # No frames extracted

        result = run_traditional_forensics("/video.mp4", ["ela"], "test_id")

        assert result["ela"]["score"] is None
        assert "No frames extracted" in result["ela"]["error"]

    @patch("api.traditional_integration.extract_frames")
    @patch("api.traditional_integration.run_ela")
    @patch("api.traditional_integration.DATA_ROOT")
    def test_unknown_module_returns_error(self, mock_data_root, mock_ela, mock_extract):
        """Unknown module name returns error result."""
        mock_data_root.__truediv__ = lambda self, x: Path(tempfile.gettempdir()) / x
        mock_extract.return_value = ["/path/frame1.jpg"]

        result = run_traditional_forensics("/video.mp4", ["unknown_module"], "test_id")

        assert "unknown_module" in result
        assert result["unknown_module"]["score"] is None
        assert "Unknown forensics module" in result["unknown_module"]["error"]

    @patch("api.traditional_integration.extract_frames")
    @patch("api.traditional_integration.run_ela")
    @patch("api.traditional_integration.DATA_ROOT")
    def test_module_analysis_failure_returns_error_for_that_module(self, mock_data_root, mock_ela, mock_extract):
        """Individual module failure returns error for that module only."""
        mock_data_root.__truediv__ = lambda self, x: Path(tempfile.gettempdir()) / x
        mock_extract.return_value = ["/path/frame1.jpg"]
        mock_ela.side_effect = ValueError("ELA processing failed")

        result = run_traditional_forensics("/video.mp4", ["ela"], "test_id")

        assert result["ela"]["score"] is None
        assert "Analysis failed: ELA processing failed" in result["ela"]["error"]

    @patch("api.traditional_integration.extract_frames")
    @patch("api.traditional_integration.run_ela")
    @patch("api.traditional_integration.run_noise_analysis")
    @patch("api.traditional_integration.DATA_ROOT")
    def test_one_module_fails_others_succeed(self, mock_data_root, mock_noise, mock_ela, mock_extract):
        """One module failure doesn't affect other modules."""
        mock_data_root.__truediv__ = lambda self, x: Path(tempfile.gettempdir()) / x
        mock_extract.return_value = ["/path/frame1.jpg"]
        mock_ela.return_value = {"mode": "single_frame", "frame": "frame1.jpg", "score": 1.5}
        mock_noise.side_effect = RuntimeError("Noise analysis crashed")

        result = run_traditional_forensics("/video.mp4", ["ela", "noise"], "test_id")

        # ELA should succeed
        assert result["ela"]["score"] == 1.5
        assert "error" not in result["ela"]

        # Noise should have error
        assert result["noise"]["score"] is None
        assert "Analysis failed" in result["noise"]["error"]
