# test_video_io.py - Unit tests for DeepfakeBench-aligned video processing

"""
Unit tests for video_io.py module that validate:

1. Frame sampling math matches np.linspace exactly
2. BGR→RGB conversion with known color markers
3. Padding behavior with partial face detection
4. Error handling for edge cases
5. Metadata accuracy

These tests focus on video I/O logic without requiring the heavy dlib predictor.
Integration tests with real face detection can be added separately.
"""

import pytest
import numpy as np
import cv2
import tempfile
import os
from unittest.mock import Mock, patch
from pathlib import Path

# Import modules to test
from ml.video_io import (
    _sample_frame_indices,
    load_video_32,
    VideoMeta,
    FrameInfo,
    VideoBatch,
    create_video_processor
)
from ml.constants import FRAME_NUM


class TestFrameSampling:
    """Test frame sampling logic matches DeepfakeBench exactly."""

    def test_linspace_sampling_basic(self):
        """Test basic sampling matches np.linspace exactly."""
        frame_count = 97
        num_frames = 32

        # Our implementation
        indices = _sample_frame_indices(frame_count, num_frames)

        # Expected DeepfakeBench behavior
        expected = np.linspace(0, frame_count - 1, num=num_frames, endpoint=True, dtype=int)

        assert np.array_equal(indices, expected), f"Got {indices}, expected {expected}"
        assert indices.dtype == np.int_, f"Expected int dtype, got {indices.dtype}"

    def test_linspace_edge_cases(self):
        """Test edge cases for frame sampling."""
        # Single frame
        indices = _sample_frame_indices(1, 32)
        expected = np.linspace(0, 0, num=32, endpoint=True, dtype=int)  # All zeros
        assert np.array_equal(indices, expected)

        # Fewer frames than requested
        indices = _sample_frame_indices(10, 32)
        expected = np.linspace(0, 9, num=32, endpoint=True, dtype=int)
        assert np.array_equal(indices, expected)
        assert indices[0] == 0, "First frame should be 0"
        assert indices[-1] == 9, "Last frame should be 9"

        # Empty video
        indices = _sample_frame_indices(0, 32)
        assert len(indices) == 0

    def test_sampling_properties(self):
        """Test sampling maintains required properties."""
        for frame_count in [32, 50, 100, 270]:
            indices = _sample_frame_indices(frame_count, 32)

            # Check length
            assert len(indices) == 32, f"Expected 32 indices for {frame_count} frames"

            # Check bounds
            assert indices[0] == 0, "First index should be 0"
            assert indices[-1] == frame_count - 1, f"Last index should be {frame_count-1}"

            # Check monotonic (non-decreasing)
            assert np.all(indices[1:] >= indices[:-1]), "Indices should be non-decreasing"


class TestVideoProcessing:
    """Test video processing with mocked components."""

    def create_test_video(self, num_frames=40, fps=30.0, width=640, height=360,
                         color_pattern=None):
        """Create a test video file for testing."""
        temp_file = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
        temp_file.close()

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(temp_file.name, fourcc, fps, (width, height))

        for i in range(num_frames):
            if color_pattern == 'bgr_marker':
                # Create frame with BGR color marker (pure blue in BGR = [255,0,0])
                frame = np.zeros((height, width, 3), dtype=np.uint8)
                frame[:, :, 0] = 255  # Blue channel in BGR
            else:
                # Default: gradient pattern
                intensity = int(255 * i / num_frames)
                frame = np.full((height, width, 3), intensity, dtype=np.uint8)

            writer.write(frame)

        writer.release()
        return temp_file.name

    def teardown_method(self):
        """Clean up test files."""
        # Clean up any temp files created during testing
        for file_path in getattr(self, '_temp_files', []):
            if os.path.exists(file_path):
                os.unlink(file_path)

    def test_video_metadata_extraction(self):
        """Test video metadata is extracted correctly."""
        video_path = self.create_test_video(num_frames=50, fps=25.0, width=1280, height=720)
        self._temp_files = [video_path]

        # Mock the face processing to focus on metadata
        mock_detector = Mock()
        mock_predictor = Mock()

        def mock_align_function(rgb_frame, detector, predictor, **kwargs):
            # Return a dummy 256x256x3 RGB crop
            return np.zeros((256, 256, 3), dtype=np.uint8)

        with patch('ml.video_io.face_align_crop.align_and_crop_rgb', side_effect=mock_align_function):
            result = load_video_32(video_path, mock_detector, mock_predictor, required=False)

        meta = result.meta
        assert meta.path == video_path
        assert meta.frame_count == 50
        assert abs(meta.fps - 25.0) < 0.1  # Allow small floating point error
        assert abs(meta.duration_sec - 2.0) < 0.1  # 50 frames / 25 fps = 2 seconds
        assert meta.width == 1280
        assert meta.height == 720

    def test_bgr_to_rgb_conversion(self):
        """Test BGR→RGB conversion with known color markers."""
        # Create video with pure blue in BGR format
        video_path = self.create_test_video(num_frames=10, color_pattern='bgr_marker')
        self._temp_files = [video_path]

        mock_detector = Mock()
        mock_predictor = Mock()

        # Capture the RGB frame passed to align function
        captured_rgb_frames = []

        def mock_align_function(rgb_frame, detector, predictor, **kwargs):
            captured_rgb_frames.append(rgb_frame.copy())
            # Return dummy crop
            return np.zeros((256, 256, 3), dtype=np.uint8)

        with patch('ml.video_io.face_align_crop.align_and_crop_rgb', side_effect=mock_align_function):
            load_video_32(video_path, mock_detector, mock_predictor, required=False)

        # Check that RGB conversion happened correctly
        assert len(captured_rgb_frames) > 0, "Should have captured RGB frames"

        rgb_frame = captured_rgb_frames[0]
        # Original was pure blue in BGR [255,0,0], should become pure red in RGB [255,0,0] -> [0,0,255]
        # Actually, BGR [255,0,0] becomes RGB [0,0,255] (red in RGB)
        assert rgb_frame[0, 0, 2] > 200, "Blue channel should be high after BGR→RGB conversion"
        assert rgb_frame[0, 0, 0] < 50, "Red channel should be low"
        assert rgb_frame[0, 0, 1] < 50, "Green channel should be low"

    def test_padding_behavior(self):
        """Test padding with partial face detection."""
        video_path = self.create_test_video(num_frames=40)
        self._temp_files = [video_path]

        mock_detector = Mock()
        mock_predictor = Mock()

        # Mock align function that returns faces for only first 10 sampled frames
        call_count = 0
        def mock_align_function(rgb_frame, detector, predictor, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 10:
                # Create unique crop for each valid detection
                crop = np.full((256, 256, 3), call_count * 20, dtype=np.uint8)
                return crop
            else:
                return None  # No face detected

        with patch('ml.video_io.face_align_crop.align_and_crop_rgb', side_effect=mock_align_function):
            result = load_video_32(video_path, mock_detector, mock_predictor, required=False)

        # Should have exactly 32 crops
        assert len(result.crops_rgb) == 32
        assert len(result.frames) == 32

        # First 10 should be unique
        unique_crops = []
        for i in range(10):
            unique_crops.append(result.crops_rgb[i][0, 0, 0])  # First pixel value
        assert len(set(unique_crops)) == 10, "First 10 crops should be unique"

        # Remaining 22 should be copies of the 10th crop
        last_valid_pixel = result.crops_rgb[9][0, 0, 0]
        for i in range(10, 32):
            assert result.crops_rgb[i][0, 0, 0] == last_valid_pixel, \
                f"Crop {i} should be copy of last valid crop"

        # Frame info should also be padded
        last_valid_frame_info = result.frames[9]
        for i in range(10, 32):
            assert result.frames[i].index == last_valid_frame_info.index
            assert result.frames[i].timestamp_sec == last_valid_frame_info.timestamp_sec

    def test_timestamp_calculation(self):
        """Test timestamp calculation from frame index and fps."""
        video_path = self.create_test_video(num_frames=100, fps=25.0)
        self._temp_files = [video_path]

        mock_detector = Mock()
        mock_predictor = Mock()

        # Capture frame infos
        captured_frame_infos = []

        def mock_align_function(rgb_frame, detector, predictor, **kwargs):
            return np.zeros((256, 256, 3), dtype=np.uint8)

        with patch('ml.video_io.face_align_crop.align_and_crop_rgb', side_effect=mock_align_function):
            result = load_video_32(video_path, mock_detector, mock_predictor)

        # Check timestamps are calculated correctly
        fps = 25.0
        for i, frame_info in enumerate(result.frames):
            expected_timestamp = frame_info.index / fps
            assert abs(frame_info.timestamp_sec - expected_timestamp) < 1e-6, \
                f"Frame {i}: expected timestamp {expected_timestamp}, got {frame_info.timestamp_sec}"

    def test_error_handling_empty_video(self):
        """Test error handling for empty/unreadable video."""
        mock_detector = Mock()
        mock_predictor = Mock()

        # Test with non-existent file
        with pytest.raises(ValueError, match="empty or unreadable video"):
            load_video_32("nonexistent.mp4", mock_detector, mock_predictor, required=True)

        # Test with required=False
        result = load_video_32("nonexistent.mp4", mock_detector, mock_predictor, required=False)
        assert len(result.crops_rgb) == 0
        assert len(result.frames) == 0

    def test_error_handling_no_faces(self):
        """Test error handling when no faces are found."""
        video_path = self.create_test_video(num_frames=40)
        self._temp_files = [video_path]

        mock_detector = Mock()
        mock_predictor = Mock()

        # Mock align function that never finds faces
        def mock_align_function(rgb_frame, detector, predictor, **kwargs):
            return None

        with patch('ml.video_io.face_align_crop.align_and_crop_rgb', side_effect=mock_align_function):
            # Should raise with required=True
            with pytest.raises(ValueError, match="no faces found in any of the sampled frames"):
                load_video_32(video_path, mock_detector, mock_predictor, required=True)

            # Should return empty with required=False
            result = load_video_32(video_path, mock_detector, mock_predictor, required=False)
            assert len(result.crops_rgb) == 0
            assert len(result.frames) == 0


class TestIntegration:
    """Integration tests that might require actual files."""

    def test_create_video_processor(self):
        """Test video processor creation."""
        # This test will fail if dlib predictor file doesn't exist, which is expected
        # In a real environment, this would test the actual file path resolution

        with patch('ml.video_io.face_align_crop.create_dlib_detector_and_predictor') as mock_create:
            mock_detector = Mock()
            mock_predictor = Mock()
            mock_create.return_value = (mock_detector, mock_predictor)

            detector, predictor = create_video_processor()

            assert detector == mock_detector
            assert predictor == mock_predictor
            mock_create.assert_called_once_with(None)


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])