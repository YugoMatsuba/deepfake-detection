# test_transforms.py - Unit tests for tensor preprocessing

import numpy as np
import torch
import pytest
from ml.transforms import preprocess_crops


class TestPreprocessCrops:
    """Test tensor preprocessing with DeepfakeBench-aligned normalization."""

    def test_empty_crops_list(self):
        """Test behavior with empty crops list."""
        result = preprocess_crops([])

        assert result.shape == (0, 3, 256, 256)
        assert result.dtype == torch.float32
        assert result.device.type == "cpu"

    def test_single_crop_shape(self):
        """Test tensor shape with single crop."""
        crop = np.zeros((256, 256, 3), dtype=np.uint8)
        result = preprocess_crops([crop])

        assert result.shape == (1, 3, 256, 256)
        assert result.dtype == torch.float32

    def test_multiple_crops_shape(self):
        """Test tensor shape with multiple crops."""
        crops = [np.zeros((256, 256, 3), dtype=np.uint8) for _ in range(32)]
        result = preprocess_crops(crops)

        assert result.shape == (32, 3, 256, 256)
        assert result.dtype == torch.float32

    def test_normalization_values(self):
        """Test DeepfakeBench normalization: mean=[0.5,0.5,0.5], std=[0.5,0.5,0.5]."""
        # Create test crops with known pixel values
        black = np.zeros((256, 256, 3), dtype=np.uint8)      # 0 -> -1
        mid_gray = np.full((256, 256, 3), 127, dtype=np.uint8)  # 127/255≈0.498 -> ~0
        white = np.full((256, 256, 3), 255, dtype=np.uint8)     # 1.0 -> +1

        result = preprocess_crops([black, mid_gray, white])

        # Check tensor shape
        assert result.shape == (3, 3, 256, 256)

        # Normalization formula: (pixel/255 - 0.5) / 0.5
        # Black (0): (0 - 0.5) / 0.5 = -1.0
        # Mid (127/255≈0.498): (0.498 - 0.5) / 0.5 ≈ -0.004
        # White (1): (1.0 - 0.5) / 0.5 = +1.0

        black_mean = result[0].mean().item()
        mid_mean = result[1].mean().item()
        white_mean = result[2].mean().item()

        assert black_mean < -0.95, f"Black crop should be ~-1, got {black_mean}"
        assert -0.05 < mid_mean < 0.05, f"Mid-gray crop should be ~0, got {mid_mean}"
        assert white_mean > 0.95, f"White crop should be ~+1, got {white_mean}"

    def test_device_placement_cpu(self):
        """Test CPU device placement."""
        crop = np.zeros((256, 256, 3), dtype=np.uint8)
        result = preprocess_crops([crop], device="cpu")

        assert result.device.type == "cpu"

    def test_device_placement_cuda(self):
        """Test CUDA device placement (if available)."""
        if not torch.cuda.is_available():
            pytest.skip("CUDA not available")

        crop = np.zeros((256, 256, 3), dtype=np.uint8)
        result = preprocess_crops([crop], device="cuda")

        assert result.device.type == "cuda"

    def test_batch_consistency(self):
        """Test that identical crops produce identical tensors."""
        # Create two identical crops
        crop1 = np.full((256, 256, 3), 100, dtype=np.uint8)
        crop2 = np.full((256, 256, 3), 100, dtype=np.uint8)

        result = preprocess_crops([crop1, crop2])

        # Both tensors should be identical
        assert torch.allclose(result[0], result[1])

    def test_rgb_channel_order(self):
        """Test RGB channel ordering is preserved."""
        # Create crop with distinct R, G, B values
        crop = np.zeros((256, 256, 3), dtype=np.uint8)
        crop[:, :, 0] = 255  # Red channel
        crop[:, :, 1] = 127  # Green channel
        crop[:, :, 2] = 0    # Blue channel

        result = preprocess_crops([crop])

        # Check that channels are in correct order after ToTensor (HWC -> CHW)
        # Red channel (index 0) should be highest
        # Blue channel (index 2) should be lowest
        red_mean = result[0, 0].mean().item()   # Channel 0 (Red)
        green_mean = result[0, 1].mean().item() # Channel 1 (Green)
        blue_mean = result[0, 2].mean().item()  # Channel 2 (Blue)

        assert red_mean > green_mean > blue_mean, \
            f"RGB order wrong: R={red_mean}, G={green_mean}, B={blue_mean}"

    def test_value_range(self):
        """Test that normalized values are in expected range [-1, 1]."""
        # Use random crop with full value range
        np.random.seed(42)
        crop = np.random.randint(0, 256, (256, 256, 3), dtype=np.uint8)

        result = preprocess_crops([crop])

        # Values should be roughly in [-1, 1] range
        min_val = result.min().item()
        max_val = result.max().item()

        assert -1.1 < min_val < -0.9, f"Min value {min_val} outside expected range"
        assert 0.9 < max_val < 1.1, f"Max value {max_val} outside expected range"