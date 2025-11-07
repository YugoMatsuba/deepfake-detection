"""
Unit tests for pure traditional forensics functions.

Tests isolated computational logic without external dependencies:
- stretch_to_uint8: Percentile-based contrast stretching
- downscale_overlay: Aspect ratio preserving image downscaling
- compute_ela_score: ELA anomaly detection (basic)
- compute_lbp: LBP histogram-based scoring (basic)
- compute_noise: Blockwise noise inconsistency (basic)
"""
import sys
import os
import numpy as np
from PIL import Image
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from api.traditional_forensics_utils.ela_analysis import (
    stretch_to_uint8 as ela_stretch,
    downscale_overlay as ela_downscale,
    compute_ela_score
)
from api.traditional_forensics_utils.lbp_analysis import (
    stretch_to_uint8 as lbp_stretch,
    downscale_overlay as lbp_downscale,
    compute_lbp
)
from api.traditional_forensics_utils.noise_analysis import (
    stretch_to_uint8 as noise_stretch,
    downscale_overlay as noise_downscale,
    compute_noise
)


class TestStretchToUint8:
    """Test percentile-based contrast stretching (shared across ELA/LBP/Noise)."""

    def test_stretch_normal_range(self):
        """Test stretching with normal value distribution."""
        # Create array with known percentile values
        arr = np.array([
            [0, 10, 20, 30, 40],
            [50, 60, 70, 80, 90],
            [100, 110, 120, 130, 140]
        ], dtype=np.float32)

        result = ela_stretch(arr, low_pct=5, high_pct=95)

        # Result should be uint8
        assert result.dtype == np.uint8

        # Values should be stretched to 0-255 range
        assert result.min() >= 0
        assert result.max() <= 255

    def test_stretch_identical_values(self):
        """Test stretch with all identical values (edge case)."""
        arr = np.full((5, 5), 100.0, dtype=np.float32)

        result = ela_stretch(arr, low_pct=5, high_pct=95)

        # Should not crash, all values should be clipped to valid range
        assert result.dtype == np.uint8
        assert result.shape == (5, 5)

    def test_stretch_high_contrast(self):
        """Test stretch with extreme value range."""
        arr = np.array([
            [0, 0, 0, 0],
            [0, 1000, 1000, 0],
            [0, 1000, 1000, 0],
            [0, 0, 0, 0]
        ], dtype=np.float32)

        result = ela_stretch(arr, low_pct=1, high_pct=99)

        # Stretching should map percentiles to 0-255
        assert result.dtype == np.uint8
        assert result.min() >= 0
        assert result.max() <= 255

    def test_stretch_preserves_shape(self):
        """Test that output shape matches input shape."""
        shapes = [(10, 10), (20, 30), (100, 150)]

        for shape in shapes:
            arr = np.random.rand(*shape).astype(np.float32) * 100
            result = lbp_stretch(arr, low_pct=5, high_pct=95)

            assert result.shape == arr.shape

    def test_stretch_3d_array(self):
        """Test stretch on 3D array (RGB-like)."""
        # ELA uses 3D arrays (RGB images)
        arr = np.random.rand(50, 50, 3).astype(np.float32) * 100

        result = ela_stretch(arr, low_pct=5, high_pct=95)

        assert result.dtype == np.uint8
        assert result.shape == arr.shape

    def test_different_percentiles(self):
        """Test with different percentile values."""
        arr = np.random.rand(100, 100).astype(np.float32) * 255

        # Test with different percentile ranges
        result_wide = noise_stretch(arr, low_pct=1, high_pct=99)
        result_narrow = noise_stretch(arr, low_pct=10, high_pct=90)

        # Both should be valid uint8
        assert result_wide.dtype == np.uint8
        assert result_narrow.dtype == np.uint8


class TestDownscaleOverlay:
    """Test aspect ratio preserving image downscaling."""

    def test_downscale_oversized_image(self):
        """Test downscaling image larger than max_width."""
        # Create 1920x1080 image
        img = Image.new('RGB', (1920, 1080), color=(255, 0, 0))

        result = ela_downscale(img, max_width=960)

        # Width should be capped at 960
        assert result.width == 960

        # Aspect ratio should be preserved
        expected_height = int(1080 * (960 / 1920))
        assert result.height == expected_height

    def test_no_downscale_small_image(self):
        """Test that images smaller than max_width are not upscaled."""
        img = Image.new('RGB', (640, 480), color=(0, 255, 0))

        result = lbp_downscale(img, max_width=960)

        # Should return original dimensions
        assert result.width == 640
        assert result.height == 480

    def test_downscale_exact_max_width(self):
        """Test image exactly at max_width (no scaling needed)."""
        img = Image.new('L', (960, 540), color=128)

        result = noise_downscale(img, max_width=960)

        # Should not change dimensions
        assert result.width == 960
        assert result.height == 540

    def test_downscale_preserves_aspect_ratio(self):
        """Test that aspect ratio is preserved for various sizes."""
        test_cases = [
            ((2000, 1000), 960),  # 2:1 ratio
            ((3000, 2000), 960),  # 3:2 ratio
            ((1920, 1080), 960),  # 16:9 ratio
        ]

        for (width, height), max_width in test_cases:
            img = Image.new('RGB', (width, height))
            result = ela_downscale(img, max_width=max_width)

            # Calculate expected dimensions
            ratio = max_width / width
            expected_height = int(height * ratio)

            assert result.width == max_width
            assert result.height == expected_height

            # Verify aspect ratio is preserved (within 1% tolerance)
            original_aspect = width / height
            result_aspect = result.width / result.height
            assert abs(original_aspect - result_aspect) / original_aspect < 0.01

    def test_downscale_different_modes(self):
        """Test downscaling on different image modes (RGB, L)."""
        # RGB image
        img_rgb = Image.new('RGB', (2000, 1000), color=(255, 0, 0))
        result_rgb = ela_downscale(img_rgb, max_width=800)
        assert result_rgb.mode == 'RGB'
        assert result_rgb.width == 800

        # Grayscale image
        img_l = Image.new('L', (2000, 1000), color=128)
        result_l = lbp_downscale(img_l, max_width=800)
        assert result_l.mode == 'L'
        assert result_l.width == 800


class TestComputeElaScore:
    """Test ELA score computation (basic functional tests)."""

    def create_test_image(self, size=(256, 256), pattern='solid'):
        """Helper to create test images."""
        if pattern == 'solid':
            return Image.new('RGB', size, color=(128, 128, 128))
        elif pattern == 'gradient':
            arr = np.zeros((size[1], size[0], 3), dtype=np.uint8)
            arr[:, :, 0] = np.linspace(0, 255, size[0], dtype=np.uint8)
            return Image.fromarray(arr, mode='RGB')
        elif pattern == 'noise':
            arr = np.random.randint(0, 256, (*size[::-1], 3), dtype=np.uint8)
            return Image.fromarray(arr, mode='RGB')

    def test_compute_ela_basic(self):
        """Test that compute_ela_score runs without errors."""
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            img = self.create_test_image(pattern='gradient')
            img.save(f.name, 'JPEG', quality=90)
            temp_path = f.name

        try:
            score, ela_image = compute_ela_score(temp_path, resave_quality=90)

            # Score should be a float
            assert isinstance(score, (float, np.floating))

            # ELA image should be PIL Image
            assert isinstance(ela_image, Image.Image)

            # ELA image should be RGB
            assert ela_image.mode == 'RGB'

            # Score should be non-negative (std is always >= 0)
            assert score >= 0

        finally:
            os.unlink(temp_path)

    def test_compute_ela_returns_downscaled_image(self):
        """Test that ELA image is downscaled to max width."""
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            img = self.create_test_image(size=(2000, 1500), pattern='noise')
            img.save(f.name, 'JPEG', quality=85)
            temp_path = f.name

        try:
            score, ela_image = compute_ela_score(temp_path, resave_quality=90)

            # ELA image should be downscaled to <= 960 width
            assert ela_image.width <= 960

        finally:
            os.unlink(temp_path)

    def test_compute_ela_different_qualities(self):
        """Test ELA with different resave qualities."""
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            img = self.create_test_image(pattern='gradient')
            img.save(f.name, 'JPEG', quality=95)
            temp_path = f.name

        try:
            score_90, _ = compute_ela_score(temp_path, resave_quality=90)
            score_50, _ = compute_ela_score(temp_path, resave_quality=50)

            # Lower quality should generally produce higher ELA scores
            # (more compression artifacts = higher difference)
            assert isinstance(score_90, (float, np.floating))
            assert isinstance(score_50, (float, np.floating))

        finally:
            os.unlink(temp_path)


class TestComputeLbp:
    """Test LBP computation (basic functional tests)."""

    def create_test_image(self, size=(256, 256), pattern='solid'):
        """Helper to create grayscale test images."""
        if pattern == 'solid':
            return Image.new('L', size, color=128)
        elif pattern == 'checkerboard':
            arr = np.zeros(size[::-1], dtype=np.uint8)
            arr[::2, ::2] = 255
            arr[1::2, 1::2] = 255
            return Image.fromarray(arr, mode='L')
        elif pattern == 'noise':
            arr = np.random.randint(0, 256, size[::-1], dtype=np.uint8)
            return Image.fromarray(arr, mode='L')

    def test_compute_lbp_basic(self):
        """Test that compute_lbp runs without errors."""
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            img = self.create_test_image(pattern='checkerboard')
            img.save(f.name, 'JPEG', quality=95)
            temp_path = f.name

        try:
            score, lbp_image = compute_lbp(temp_path, P=8, R=1)

            # Score should be a float
            assert isinstance(score, (float, np.floating))

            # LBP image should be PIL Image
            assert isinstance(lbp_image, Image.Image)

            # LBP image should be grayscale
            assert lbp_image.mode == 'L'

            # Score should be non-negative (std is always >= 0)
            assert score >= 0

        finally:
            os.unlink(temp_path)

    def test_compute_lbp_returns_downscaled_image(self):
        """Test that LBP image is downscaled."""
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            img = self.create_test_image(size=(2000, 1500), pattern='noise')
            img.save(f.name, 'JPEG', quality=90)
            temp_path = f.name

        try:
            score, lbp_image = compute_lbp(temp_path)

            # LBP image should be downscaled to <= 960 width
            assert lbp_image.width <= 960

        finally:
            os.unlink(temp_path)

    def test_compute_lbp_different_parameters(self):
        """Test LBP with different P and R parameters."""
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            img = self.create_test_image(pattern='checkerboard')
            img.save(f.name, 'JPEG', quality=95)
            temp_path = f.name

        try:
            # Default parameters
            score_default, _ = compute_lbp(temp_path, P=8, R=1)

            # Different parameters
            score_large, _ = compute_lbp(temp_path, P=16, R=2)

            # Both should produce valid scores
            assert isinstance(score_default, (float, np.floating))
            assert isinstance(score_large, (float, np.floating))
            assert score_default >= 0
            assert score_large >= 0

        finally:
            os.unlink(temp_path)


class TestComputeNoise:
    """Test noise analysis computation (basic functional tests)."""

    def create_test_image(self, size=(256, 256), pattern='solid'):
        """Helper to create grayscale test images."""
        if pattern == 'solid':
            return Image.new('L', size, color=128)
        elif pattern == 'gradient':
            arr = np.tile(np.linspace(0, 255, size[0], dtype=np.uint8), (size[1], 1))
            return Image.fromarray(arr, mode='L')
        elif pattern == 'noise':
            arr = np.random.randint(0, 256, size[::-1], dtype=np.uint8)
            return Image.fromarray(arr, mode='L')

    def test_compute_noise_basic(self):
        """Test that compute_noise runs without errors."""
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            img = self.create_test_image(pattern='gradient')
            img.save(f.name, 'JPEG', quality=90)
            temp_path = f.name

        try:
            score, noise_image = compute_noise(temp_path)

            # Score should be a float
            assert isinstance(score, (float, np.floating))

            # Noise image should be PIL Image (z-map overlay)
            assert isinstance(noise_image, Image.Image)

            # Noise image should be grayscale
            assert noise_image.mode == 'L'

        finally:
            os.unlink(temp_path)

    def test_compute_noise_returns_downscaled_image(self):
        """Test that noise overlay is downscaled."""
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            img = self.create_test_image(size=(2000, 1500), pattern='noise')
            img.save(f.name, 'JPEG', quality=90)
            temp_path = f.name

        try:
            score, noise_image = compute_noise(temp_path)

            # Noise overlay should be downscaled to <= 960 width
            assert noise_image.width <= 960

        finally:
            os.unlink(temp_path)

    def test_compute_noise_output_types(self):
        """Test that noise analysis returns correct types."""
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            img = self.create_test_image(pattern='noise')
            img.save(f.name, 'JPEG', quality=90)
            temp_path = f.name

        try:
            score, overlay = compute_noise(temp_path)

            # Verify types
            assert isinstance(score, (float, np.floating))
            assert isinstance(overlay, Image.Image)

            # Score is z-score of top-k blocks (can be negative)
            # Just verify it's a reasonable value
            assert -100 < score < 100  # Reasonable z-score range

        finally:
            os.unlink(temp_path)
