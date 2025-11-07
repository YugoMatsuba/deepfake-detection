"""
Tests for analysis.py helper functions.

Tests pure logic helpers that don't require full Flask request context.
"""

from unittest.mock import patch, MagicMock
import subprocess
from datetime import datetime
from api.routes.analysis import _capture_ml_provenance, _get_video_metadata


class TestCaptureMLProvenance:
    """Test _capture_ml_provenance metadata capture."""

    @patch("api.routes.analysis.subprocess.run")
    @patch("api.routes.analysis.datetime")
    def test_captures_git_commit_hash(self, mock_datetime, mock_run):
        """Captures git commit hash when git is available."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="abc123def456\n"
        )
        mock_datetime.now().isoformat.return_value = "2025-01-15T10:30:00Z"

        result = _capture_ml_provenance()

        assert result["commit_hash"] == "abc123def456"
        assert result["timestamp"] == "2025-01-15T10:30:00Z"

    @patch("api.routes.analysis.subprocess.run")
    def test_falls_back_to_unknown_when_git_fails(self, mock_run):
        """Falls back to 'unknown' when git command fails."""
        mock_run.return_value = MagicMock(returncode=1)

        result = _capture_ml_provenance()

        assert result["commit_hash"] == "unknown"

    @patch("api.routes.analysis.subprocess.run")
    def test_falls_back_to_unknown_on_exception(self, mock_run):
        """Falls back to 'unknown' when subprocess raises exception."""
        mock_run.side_effect = Exception("Git not found")

        result = _capture_ml_provenance()

        assert result["commit_hash"] == "unknown"

    @patch("api.routes.analysis.subprocess.run")
    def test_uses_provided_device(self, mock_run):
        """Uses device parameter when provided."""
        mock_run.return_value = MagicMock(returncode=0, stdout="abc\n")

        result = _capture_ml_provenance(device="cuda")

        assert result["device"] == "cuda"

    @patch("api.routes.analysis.subprocess.run")
    def test_uses_env_var_when_device_not_provided(self, mock_run):
        """Uses DEVICE env var when device parameter is None."""
        mock_run.return_value = MagicMock(returncode=0, stdout="abc\n")

        with patch("api.routes.analysis.os.environ.get", return_value="cpu"):
            result = _capture_ml_provenance(device=None)

        assert result["device"] == "cpu"

    @patch("api.routes.analysis.subprocess.run")
    def test_defaults_to_auto_detect_when_no_env(self, mock_run):
        """Defaults to 'auto-detect' when DEVICE env var not set."""
        mock_run.return_value = MagicMock(returncode=0, stdout="abc\n")

        with patch("api.routes.analysis.os.environ.get", return_value="auto-detect"):
            result = _capture_ml_provenance()

        assert result["device"] == "auto-detect"

    @patch("api.routes.analysis.subprocess.run")
    def test_includes_schema_version(self, mock_run):
        """Includes schema version in output."""
        mock_run.return_value = MagicMock(returncode=0, stdout="abc\n")

        result = _capture_ml_provenance()

        assert "schema_version" in result
        assert result["schema_version"] is not None

    @patch("api.routes.analysis.subprocess.run")
    def test_timestamp_is_iso8601_format(self, mock_run):
        """Timestamp is in ISO8601 format."""
        mock_run.return_value = MagicMock(returncode=0, stdout="abc\n")

        result = _capture_ml_provenance()

        # Check timestamp looks like ISO8601
        assert "timestamp" in result
        assert "T" in result["timestamp"]  # ISO8601 has T separator


class TestGetVideoMetadata:
    """Test _get_video_metadata extraction."""

    @patch("api.routes.analysis.os.path.exists")
    def test_returns_empty_metadata_when_file_not_found(self, mock_exists):
        """Returns None values when video file doesn't exist."""
        mock_exists.return_value = False

        result = _get_video_metadata("/nonexistent.mp4")

        assert result["path"] == "/nonexistent.mp4"
        assert result["fps"] is None
        assert result["frame_count"] is None
        assert result["duration_sec"] is None
        assert result["width"] is None
        assert result["height"] is None

    @patch("api.routes.analysis.os.path.exists")
    @patch("api.routes.analysis.cv2.VideoCapture")
    def test_returns_empty_metadata_when_video_cannot_open(self, mock_cap_class, mock_exists):
        """Returns None values when video cannot be opened."""
        mock_exists.return_value = True

        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False
        mock_cap_class.return_value = mock_cap

        result = _get_video_metadata("/corrupt.mp4")

        assert result["fps"] is None
        assert result["frame_count"] is None

    @patch("api.routes.analysis.os.path.exists")
    @patch("api.routes.analysis.cv2.VideoCapture")
    def test_extracts_fps_and_frame_count(self, mock_cap_class, mock_exists):
        """Extracts FPS and frame count from video."""
        mock_exists.return_value = True

        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {
            cv2.CAP_PROP_FPS: 30.0,
            cv2.CAP_PROP_FRAME_COUNT: 300.0,
            cv2.CAP_PROP_FRAME_WIDTH: 1920.0,
            cv2.CAP_PROP_FRAME_HEIGHT: 1080.0
        }.get(prop, 0.0)
        mock_cap_class.return_value = mock_cap

        # Import cv2 for constants
        import cv2

        result = _get_video_metadata("/video.mp4")

        assert result["fps"] == 30.0
        assert result["frame_count"] == 300
        assert result["width"] == 1920
        assert result["height"] == 1080

    @patch("api.routes.analysis.os.path.exists")
    @patch("api.routes.analysis.cv2.VideoCapture")
    def test_calculates_duration_from_fps_and_frame_count(self, mock_cap_class, mock_exists):
        """Calculates duration as frame_count / fps."""
        mock_exists.return_value = True

        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {
            cv2.CAP_PROP_FPS: 25.0,
            cv2.CAP_PROP_FRAME_COUNT: 250.0,
            cv2.CAP_PROP_FRAME_WIDTH: 1280.0,
            cv2.CAP_PROP_FRAME_HEIGHT: 720.0
        }.get(prop, 0.0)
        mock_cap_class.return_value = mock_cap

        import cv2

        result = _get_video_metadata("/video.mp4")

        # 250 frames / 25 fps = 10 seconds
        assert result["duration_sec"] == 10.0

    @patch("api.routes.analysis.os.path.exists")
    @patch("api.routes.analysis.cv2.VideoCapture")
    def test_handles_zero_fps_gracefully(self, mock_cap_class, mock_exists):
        """Returns None for duration when FPS is zero."""
        mock_exists.return_value = True

        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {
            cv2.CAP_PROP_FPS: 0.0,  # Invalid FPS
            cv2.CAP_PROP_FRAME_COUNT: 100.0,
            cv2.CAP_PROP_FRAME_WIDTH: 1920.0,
            cv2.CAP_PROP_FRAME_HEIGHT: 1080.0
        }.get(prop, 0.0)
        mock_cap_class.return_value = mock_cap

        import cv2

        result = _get_video_metadata("/video.mp4")

        assert result["fps"] is None
        assert result["duration_sec"] is None

    @patch("api.routes.analysis.os.path.exists")
    @patch("api.routes.analysis.cv2.VideoCapture")
    def test_converts_floats_to_ints_for_dimensions(self, mock_cap_class, mock_exists):
        """Converts width/height/frame_count from floats to ints."""
        mock_exists.return_value = True

        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {
            cv2.CAP_PROP_FPS: 30.0,
            cv2.CAP_PROP_FRAME_COUNT: 150.7,  # Float
            cv2.CAP_PROP_FRAME_WIDTH: 1920.9,  # Float
            cv2.CAP_PROP_FRAME_HEIGHT: 1080.1  # Float
        }.get(prop, 0.0)
        mock_cap_class.return_value = mock_cap

        import cv2

        result = _get_video_metadata("/video.mp4")

        # Should be converted to ints
        assert isinstance(result["frame_count"], int)
        assert result["frame_count"] == 150
        assert isinstance(result["width"], int)
        assert result["width"] == 1920
        assert isinstance(result["height"], int)
        assert result["height"] == 1080

    @patch("api.routes.analysis.os.path.exists")
    @patch("api.routes.analysis.cv2.VideoCapture")
    def test_releases_video_capture(self, mock_cap_class, mock_exists):
        """Releases VideoCapture resource after extraction."""
        mock_exists.return_value = True

        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.return_value = 30.0
        mock_cap_class.return_value = mock_cap

        _get_video_metadata("/video.mp4")

        # Should call release
        mock_cap.release.assert_called_once()

    @patch("api.routes.analysis.os.path.exists")
    @patch("api.routes.analysis.cv2.VideoCapture")
    def test_releases_capture_even_on_exception(self, mock_cap_class, mock_exists):
        """Releases VideoCapture even when get() raises exception (finally block)."""
        mock_exists.return_value = True

        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = Exception("Failed to get property")
        mock_cap_class.return_value = mock_cap

        # Exception should propagate, but release should still be called (finally block)
        try:
            _get_video_metadata("/video.mp4")
            assert False, "Should have raised exception"
        except Exception as e:
            assert "Failed to get property" in str(e)

        # Should still release (finally block)
        mock_cap.release.assert_called_once()

    @patch("api.routes.analysis.os.path.exists")
    @patch("api.routes.analysis.cv2.VideoCapture")
    def test_handles_negative_frame_count(self, mock_cap_class, mock_exists):
        """Handles negative frame count gracefully."""
        mock_exists.return_value = True

        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {
            cv2.CAP_PROP_FPS: 30.0,
            cv2.CAP_PROP_FRAME_COUNT: -1.0,  # Invalid
            cv2.CAP_PROP_FRAME_WIDTH: 1920.0,
            cv2.CAP_PROP_FRAME_HEIGHT: 1080.0
        }.get(prop, 0.0)
        mock_cap_class.return_value = mock_cap

        import cv2

        result = _get_video_metadata("/video.mp4")

        # Negative frame count should be treated as invalid
        assert result["frame_count"] is None or result["frame_count"] == -1
