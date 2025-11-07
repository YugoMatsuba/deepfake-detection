"""
Tests for storage.py metadata parsing helpers.

Tests FPS parsing and fallback logic without requiring actual video files.
"""

from unittest.mock import patch, MagicMock
import subprocess
import json
from storage import probe_video_metadata, _probe_with_ffprobe


class TestProbeVideoMetadata:
    """Test probe_video_metadata fallback behavior."""

    @patch("storage._probe_with_ffprobe")
    @patch("storage._probe_with_opencv")
    def test_uses_ffprobe_when_successful(self, mock_opencv, mock_ffprobe):
        """Uses ffprobe results when available and valid."""
        mock_ffprobe.return_value = {"fps": 29.97, "frame_count": 300, "width": 1920, "height": 1080}

        result = probe_video_metadata("/video.mp4")

        # Should use ffprobe results
        assert result["fps"] == 29.97
        assert result["frame_count"] == 300
        assert result["width"] == 1920
        assert result["height"] == 1080

        # Should not call opencv fallback
        mock_opencv.assert_not_called()

    @patch("storage._probe_with_ffprobe")
    @patch("storage._probe_with_opencv")
    def test_falls_back_to_opencv_when_ffprobe_fails(self, mock_opencv, mock_ffprobe):
        """Falls back to OpenCV when ffprobe fails."""
        mock_ffprobe.return_value = None  # ffprobe failed

        mock_opencv.return_value = {"fps": 30.0, "frame_count": 150, "width": 1280, "height": 720}

        result = probe_video_metadata("/video.mp4")

        # Should use opencv results
        assert result["fps"] == 30.0
        assert result["frame_count"] == 150

    @patch("storage._probe_with_ffprobe")
    @patch("storage._probe_with_opencv")
    def test_returns_zeros_when_both_fail(self, mock_opencv, mock_ffprobe):
        """Returns zeros when both ffprobe and opencv fail."""
        mock_ffprobe.return_value = None
        mock_opencv.side_effect = Exception("OpenCV error")

        result = probe_video_metadata("/video.mp4")

        # Should return zeros
        assert result["fps"] == 0.0
        assert result["frame_count"] == 0
        assert result["width"] == 0
        assert result["height"] == 0

    @patch("storage._probe_with_ffprobe")
    @patch("storage._probe_with_opencv")
    def test_rejects_ffprobe_with_zero_values(self, mock_opencv, mock_ffprobe):
        """Falls back to opencv when ffprobe returns zeros."""
        mock_ffprobe.return_value = {"fps": 0.0, "frame_count": 0, "width": 1920, "height": 1080}  # Invalid

        mock_opencv.return_value = {"fps": 30.0, "frame_count": 100, "width": 1920, "height": 1080}

        result = probe_video_metadata("/video.mp4")

        # Should fall back to opencv (ffprobe had zeros)
        assert result["fps"] == 30.0
        assert result["frame_count"] == 100


class TestProbeWithFfprobe:
    """Test _probe_with_ffprobe FPS parsing logic."""

    @patch("storage.subprocess.run")
    def test_parses_fraction_fps(self, mock_run):
        """Parse FPS from fraction format (e.g., '30/1')."""
        mock_run.return_value = MagicMock(
            stdout=json.dumps(
                {
                    "streams": [{"codec_type": "video", "width": 1920, "height": 1080, "r_frame_rate": "30/1"}],
                    "format": {"duration": "10.0"},
                }
            )
        )

        result = _probe_with_ffprobe("/video.mp4")

        assert result["fps"] == 30.0
        assert result["frame_count"] == 300  # 30 fps * 10 sec

    @patch("storage.subprocess.run")
    def test_parses_decimal_fps(self, mock_run):
        """Parse FPS from decimal format (e.g., '29.97')."""
        mock_run.return_value = MagicMock(
            stdout=json.dumps(
                {
                    "streams": [{"codec_type": "video", "width": 1920, "height": 1080, "r_frame_rate": "29.97"}],
                    "format": {"duration": "5.0"},
                }
            )
        )

        result = _probe_with_ffprobe("/video.mp4")

        assert result["fps"] == 29.97
        assert result["frame_count"] == 149  # int(29.97 * 5)

    @patch("storage.subprocess.run")
    def test_handles_complex_fraction_fps(self, mock_run):
        """Parse FPS from complex fractions (e.g., '24000/1001' for 23.976)."""
        mock_run.return_value = MagicMock(
            stdout=json.dumps(
                {
                    "streams": [{"codec_type": "video", "width": 1920, "height": 1080, "r_frame_rate": "24000/1001"}],
                    "format": {"duration": "10.0"},
                }
            )
        )

        result = _probe_with_ffprobe("/video.mp4")

        # 24000/1001 = ~23.976
        assert 23.9 < result["fps"] < 24.0
        assert 239 <= result["frame_count"] <= 240

    @patch("storage.subprocess.run")
    def test_handles_zero_denominator_gracefully(self, mock_run):
        """Handles zero denominator in FPS fraction."""
        mock_run.return_value = MagicMock(
            stdout=json.dumps(
                {
                    "streams": [{"codec_type": "video", "width": 1920, "height": 1080, "r_frame_rate": "30/0"}],  # Invalid
                    "format": {"duration": "10.0"},
                }
            )
        )

        result = _probe_with_ffprobe("/video.mp4")

        # Should handle gracefully (fps = 0)
        assert result["fps"] == 0.0
        assert result["frame_count"] == 0

    @patch("storage.subprocess.run")
    def test_skips_audio_streams(self, mock_run):
        """Only processes video streams, not audio."""
        mock_run.return_value = MagicMock(
            stdout=json.dumps(
                {
                    "streams": [
                        {"codec_type": "audio"},  # Should be skipped
                        {"codec_type": "video", "width": 1280, "height": 720, "r_frame_rate": "25/1"},
                    ],
                    "format": {"duration": "8.0"},
                }
            )
        )

        result = _probe_with_ffprobe("/video.mp4")

        # Should use video stream, not audio
        assert result["fps"] == 25.0
        assert result["width"] == 1280
        assert result["height"] == 720

    @patch("storage.subprocess.run")
    def test_returns_none_when_no_video_stream(self, mock_run):
        """Returns None when no video stream found."""
        mock_run.return_value = MagicMock(
            stdout=json.dumps({"streams": [{"codec_type": "audio"}], "format": {}})  # Only audio
        )

        result = _probe_with_ffprobe("/video.mp4")

        assert result is None

    @patch("storage.subprocess.run")
    def test_returns_none_on_subprocess_error(self, mock_run):
        """Returns None when subprocess fails."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "ffprobe")

        result = _probe_with_ffprobe("/video.mp4")

        assert result is None

    @patch("storage.subprocess.run")
    def test_returns_none_on_json_decode_error(self, mock_run):
        """Returns None when JSON parsing fails."""
        mock_run.return_value = MagicMock(stdout="invalid json")

        result = _probe_with_ffprobe("/video.mp4")

        assert result is None

    @patch("storage.subprocess.run")
    def test_returns_none_on_timeout(self, mock_run):
        """Returns None when ffprobe times out."""
        mock_run.side_effect = subprocess.TimeoutExpired("ffprobe", 10)

        result = _probe_with_ffprobe("/video.mp4")

        assert result is None

    @patch("storage.subprocess.run")
    def test_calculates_frame_count_from_duration_and_fps(self, mock_run):
        """Calculates frame count from duration × fps."""
        mock_run.return_value = MagicMock(
            stdout=json.dumps(
                {
                    "streams": [{"codec_type": "video", "width": 1920, "height": 1080, "r_frame_rate": "60/1"}],
                    "format": {"duration": "2.5"},
                }
            )
        )

        result = _probe_with_ffprobe("/video.mp4")

        # 60 fps * 2.5 sec = 150 frames
        assert result["frame_count"] == 150

    @patch("storage.subprocess.run")
    def test_returns_zero_frame_count_when_duration_missing(self, mock_run):
        """Returns 0 frame count when duration is missing."""
        mock_run.return_value = MagicMock(
            stdout=json.dumps(
                {
                    "streams": [{"codec_type": "video", "width": 1920, "height": 1080, "r_frame_rate": "30/1"}],
                    "format": {},  # No duration
                }
            )
        )

        result = _probe_with_ffprobe("/video.mp4")

        assert result["fps"] == 30.0
        assert result["frame_count"] == 0  # No duration to calculate from
