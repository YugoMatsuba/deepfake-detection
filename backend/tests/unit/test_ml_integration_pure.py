"""
Tests for ML integration output transformation logic.

Tests the dict transformation from ml.runner output format to API response format
in api/ml_integration.py by mocking ML runner calls.
"""

from unittest.mock import patch, MagicMock
from api.ml_integration import run_ml_analysis, run_single_frame_ml_analysis


class TestRunMlAnalysisTransform:
    """Test run_ml_analysis output transformation."""

    @patch("ml.runner.run")
    def test_transforms_single_model_output(self, mock_run):
        """Transform single model output to API format."""
        mock_run.return_value = {
            "models": [
                {
                    "name": "Xception",
                    "score": 0.87,
                    "frames": [{"index": 0, "score": 0.90}, {"index": 1, "score": 0.84}],
                    "weights_hash": "abc123"
                }
            ],
            "video": {"fps": 29.97},
            "frames": [0, 1],
            "timing_ms": {"total": 1234}
        }

        result = run_ml_analysis("/path/to/video.mp4", ["xception"], device="cpu")

        # Model name should be lowercase
        assert "xception" in result["models"]
        assert result["models"]["xception"]["score"] == 0.87
        assert len(result["models"]["xception"]["frames"]) == 2
        assert result["models"]["xception"]["weights_hash"] == "abc123"

        # Metadata passthrough
        assert result["video"]["fps"] == 29.97
        assert result["frames"] == [0, 1]
        assert result["timing_ms"]["total"] == 1234

    @patch("ml.runner.run")
    def test_transforms_multiple_models_output(self, mock_run):
        """Transform multiple models output to API format."""
        mock_run.return_value = {
            "models": [
                {"name": "Xception", "score": 0.87, "frames": [], "weights_hash": "hash1"},
                {"name": "SPSL", "score": 0.92, "frames": [], "weights_hash": "hash2"},
                {"name": "UCF", "score": 0.85, "frames": [], "weights_hash": "hash3"}
            ],
            "video": {},
            "frames": [],
            "timing_ms": {}
        }

        result = run_ml_analysis("/path/to/video.mp4", ["xception", "spsl", "ucf"], device="cuda")

        # All models present with lowercase names
        assert "xception" in result["models"]
        assert "spsl" in result["models"]
        assert "ucf" in result["models"]

        # Check scores
        assert result["models"]["xception"]["score"] == 0.87
        assert result["models"]["spsl"]["score"] == 0.92
        assert result["models"]["ucf"]["score"] == 0.85

    @patch("ml.runner.run")
    def test_model_name_lowercase_conversion(self, mock_run):
        """Model names are converted to lowercase."""
        mock_run.return_value = {
            "models": [
                {"name": "Xception", "score": 0.5},
                {"name": "SPSL", "score": 0.6}
            ]
        }

        result = run_ml_analysis("/video.mp4", ["xception", "spsl"])

        assert "Xception" not in result["models"]  # Not uppercase
        assert "SPSL" not in result["models"]  # Not uppercase
        assert "xception" in result["models"]  # Lowercase
        assert "spsl" in result["models"]  # Lowercase

    @patch("ml.runner.run")
    def test_preserves_frame_data(self, mock_run):
        """Frame data is preserved in output."""
        mock_run.return_value = {
            "models": [
                {
                    "name": "xception",
                    "score": 0.75,
                    "frames": [
                        {"index": 0, "time": 0.0, "score": 0.80},
                        {"index": 5, "time": 0.17, "score": 0.70}
                    ]
                }
            ]
        }

        result = run_ml_analysis("/video.mp4", ["xception"])

        frames = result["models"]["xception"]["frames"]
        assert len(frames) == 2
        assert frames[0]["index"] == 0
        assert frames[0]["time"] == 0.0
        assert frames[0]["score"] == 0.80
        assert frames[1]["index"] == 5

    @patch("ml.runner.run")
    def test_handles_missing_frames_field(self, mock_run):
        """Handles missing frames field gracefully."""
        mock_run.return_value = {
            "models": [
                {
                    "name": "xception",
                    "score": 0.65
                    # No frames field
                }
            ]
        }

        result = run_ml_analysis("/video.mp4", ["xception"])

        assert result["models"]["xception"]["frames"] == []

    @patch("ml.runner.run")
    def test_uses_device_env_var_when_none(self, mock_run):
        """Uses DEVICE env var when device parameter is None."""
        mock_run.return_value = {"models": []}

        with patch("api.ml_integration.os.getenv", return_value="cuda"):
            run_ml_analysis("/video.mp4", ["xception"], device=None)

        # Check that run was called with device="cuda"
        mock_run.assert_called_once()
        assert mock_run.call_args[1]["device"] == "cuda"

    @patch("ml.runner.run")
    def test_defaults_to_cpu_when_device_env_not_set(self, mock_run):
        """Defaults to cpu when DEVICE env var not set."""
        mock_run.return_value = {"models": []}

        with patch("api.ml_integration.os.getenv", return_value="cpu"):
            run_ml_analysis("/video.mp4", ["xception"], device=None)

        mock_run.assert_called_once()
        assert mock_run.call_args[1]["device"] == "cpu"

    @patch("ml.runner.run")
    def test_raises_exception_on_ml_error(self, mock_run):
        """Raises exception when ML runner returns error."""
        mock_run.return_value = {
            "error": {
                "stage": "face_detection",
                "message": "No face detected in video"
            }
        }

        try:
            run_ml_analysis("/video.mp4", ["xception"])
            assert False, "Should have raised exception"
        except Exception:
            # Exception raised as expected (message gets transformed by error classifier)
            pass


class TestRunSingleFrameMlAnalysisTransform:
    """Test run_single_frame_ml_analysis output transformation."""

    @patch("ml.runner.analyze_single_frame")
    def test_transforms_single_frame_output(self, mock_analyze):
        """Transform single frame output to API format."""
        mock_analyze.return_value = {
            "frame_number": 42,
            "time": 1.4,
            "models": {
                "xception": {"score": 0.856},
                "spsl": {"score": 0.923}
            }
        }

        result = run_single_frame_ml_analysis("/video.mp4", 42, ["xception", "spsl"], device="cpu")

        # Top-level frame metadata
        assert result["frame_number"] == 42
        assert result["time"] == 1.4

        # Model results flattened to top level
        assert result["xception"]["score"] == 0.856
        assert result["xception"]["index"] == 42
        assert result["xception"]["time"] == 1.4

        assert result["spsl"]["score"] == 0.923
        assert result["spsl"]["index"] == 42
        assert result["spsl"]["time"] == 1.4

    @patch("ml.runner.analyze_single_frame")
    def test_flattens_model_results_to_top_level(self, mock_analyze):
        """Model results are flattened to top level (not nested under 'models')."""
        mock_analyze.return_value = {
            "frame_number": 10,
            "time": 0.33,
            "models": {
                "xception": {"score": 0.75},
                "ucf": {"score": 0.82}
            }
        }

        result = run_single_frame_ml_analysis("/video.mp4", 10, ["xception", "ucf"])

        # Should NOT have nested models key in output
        assert "models" not in result

        # Models should be at top level
        assert "xception" in result
        assert "ucf" in result
        assert "frame_number" in result
        assert "time" in result

    @patch("ml.runner.analyze_single_frame")
    def test_adds_index_and_time_to_each_model(self, mock_analyze):
        """Each model result gets index and time fields."""
        mock_analyze.return_value = {
            "frame_number": 99,
            "time": 3.3,
            "models": {
                "xception": {"score": 0.60},
                "spsl": {"score": 0.70},
                "ucf": {"score": 0.80}
            }
        }

        result = run_single_frame_ml_analysis("/video.mp4", 99, ["xception", "spsl", "ucf"])

        # All models should have index and time
        for model in ["xception", "spsl", "ucf"]:
            assert result[model]["index"] == 99
            assert result[model]["time"] == 3.3

    @patch("ml.runner.analyze_single_frame")
    def test_handles_empty_models(self, mock_analyze):
        """Handles empty models dict gracefully."""
        mock_analyze.return_value = {
            "frame_number": 5,
            "time": 0.17,
            "models": {}
        }

        result = run_single_frame_ml_analysis("/video.mp4", 5, [])

        assert result["frame_number"] == 5
        assert result["time"] == 0.17
        # No model keys added

    @patch("ml.runner.analyze_single_frame")
    def test_uses_device_env_var_when_none(self, mock_analyze):
        """Uses DEVICE env var when device parameter is None."""
        mock_analyze.return_value = {"frame_number": 0, "time": 0.0, "models": {}}

        with patch("api.ml_integration.os.getenv", return_value="cuda"):
            run_single_frame_ml_analysis("/video.mp4", 0, ["xception"], device=None)

        mock_analyze.assert_called_once()
        assert mock_analyze.call_args[1]["device"] == "cuda"

    @patch("ml.runner.analyze_single_frame")
    def test_raises_exception_on_error(self, mock_analyze):
        """Raises exception when ML runner returns error."""
        mock_analyze.return_value = {
            "error": {
                "message": "No face detected in frame 42"
            }
        }

        try:
            run_single_frame_ml_analysis("/video.mp4", 42, ["xception"])
            assert False, "Should have raised exception"
        except Exception as e:
            assert "No face detected" in str(e)
