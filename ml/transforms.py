# transforms.py - DeepfakeBench-aligned tensor preprocessing

from typing import List
import numpy as np
import torch
from torchvision.transforms import ToTensor, Normalize

from . import constants

# Create transform instances (reusable for efficiency)
_to_tensor = ToTensor()  # HWC uint8 RGB [0..255] -> CHW float [0..1]
_normalize = Normalize(mean=constants.MEAN, std=constants.STD)


def preprocess_crops(crops_rgb: List[np.ndarray], device: str = "cpu") -> torch.Tensor:
    """
    Convert a list of RGB uint8 crops into a normalized batch tensor.

    Follows DeepfakeBench preprocessing exactly:
    1. ToTensor(): HWC uint8 [0,255] -> CHW float32 [0,1]
    2. Normalize(): mean=[0.5,0.5,0.5], std=[0.5,0.5,0.5] -> values in [-1,1]
    3. Stack into batch tensor

    Args:
        crops_rgb: List of numpy arrays, each (256, 256, 3) uint8 RGB
        device: Target device ("cpu" or "cuda")

    Returns:
        torch.FloatTensor: Shape [N, 3, 256, 256], normalized values ~[-1, 1]
    """
    if not crops_rgb:
        # Return empty tensor with correct shape for no crops
        return torch.empty(0, 3, constants.IMG_SIZE, constants.IMG_SIZE,
                          dtype=torch.float32, device=device)

    tensors = []
    for img in crops_rgb:
        # img: (H, W, C) uint8 RGB array
        tensor = _to_tensor(img)      # -> [3, H, W] float32 in [0,1]
        tensor = _normalize(tensor)   # -> normalized to [-1,1]
        tensors.append(tensor)

    # Stack into batch: [N, 3, H, W]
    batch = torch.stack(tensors, dim=0)

    return batch.to(device)