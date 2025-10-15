# ucf_arch.py - DeepfakeBench-aligned UCF model architecture components
"""
UCF (Uncovering Common Features) architecture components copied from DeepfakeBench.

This file contains only the components used in inference mode:
- Conv2d1x1: 1x1 convolution projection for feature splitting
- Head: Shared/specific classification head with adaptive pooling
- UCFDetector: Main detector class for dual-encoder architecture

Reference:
DeepfakeBench/training/detectors/ucf_detector.py

Original paper:
@article{yan2023ucf,
  title={UCF: Uncovering Common Features for Generalizable Deepfake Detection},
  author={Yan, Zhiyuan and Zhang, Yong and Fan, Yanbo and Wu, Baoyuan},
  journal={arXiv preprint arXiv:2304.13949},
  year={2023}
}
"""

import logging
from typing import Dict, Any, Tuple

import torch
import torch.nn as nn

from .xception_arch import Xception

logger = logging.getLogger(__name__)


class Conv2d1x1(nn.Module):
    """
    1x1 convolution projection module for feature dimension reduction.

    Copied exactly from DeepfakeBench ucf_detector.py lines 439-450.
    Used to split encoder features into specific and shared components.
    """
    def __init__(self, in_f, hidden_dim, out_f):
        super(Conv2d1x1, self).__init__()
        self.conv2d = nn.Sequential(
            nn.Conv2d(in_f, hidden_dim, 1, 1),
            nn.LeakyReLU(inplace=True),
            nn.Conv2d(hidden_dim, hidden_dim, 1, 1),
            nn.LeakyReLU(inplace=True),
            nn.Conv2d(hidden_dim, out_f, 1, 1),
        )

    def forward(self, x):
        x = self.conv2d(x)
        return x


class Head(nn.Module):
    """
    Classification head with adaptive pooling and MLP.

    Copied exactly from DeepfakeBench ucf_detector.py lines 452-466.
    Returns both logits and pooled feature vector for embedding.
    """
    def __init__(self, in_f, hidden_dim, out_f):
        super(Head, self).__init__()
        self.do = nn.Dropout(0.2)
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.mlp = nn.Sequential(
            nn.Linear(in_f, hidden_dim),
            nn.LeakyReLU(inplace=True),
            nn.Linear(hidden_dim, out_f),
        )

    def forward(self, x):
        bs = x.size()[0]
        x_feat = self.pool(x).view(bs, -1)  # Global average pooling + flatten
        x = self.mlp(x_feat)  # MLP for classification
        x = self.do(x)  # Dropout on logits
        return x, x_feat  # Return (logits, pooled_features)


class UCFDetector(nn.Module):
    """
    UCF detector with dual Xception encoders and shared-head inference.

    Based on DeepfakeBench ucf_detector.py but only includes inference-relevant components.
    Architecture follows exact DeepfakeBench patterns:
    - Two Xception backbones with mode="adjust_channel"
    - Conv2d1x1 projections for feature splitting
    - Shared head for binary classification in inference mode
    """

    def __init__(self, config: Dict[str, Any]):
        super(UCFDetector, self).__init__()
        self.config = config
        self.num_classes = config['num_classes']  # Should be 2
        self.encoder_feat_dim = config['encoder_feat_dim']  # Should be 512 for adjust_channel
        self.half_fingerprint_dim = self.encoder_feat_dim // 2  # 256

        # Build two Xception encoders (DeepfakeBench lines 61-62)
        self.encoder_f = self._build_backbone(config)  # Forgery encoder
        self.encoder_c = self._build_backbone(config)  # Content encoder (not used in inference)

        # Feature projection blocks (DeepfakeBench lines 88-97)
        self.block_spe = Conv2d1x1(
            in_f=self.encoder_feat_dim,      # 512
            hidden_dim=self.half_fingerprint_dim,  # 256
            out_f=self.half_fingerprint_dim  # 256
        )
        self.block_sha = Conv2d1x1(
            in_f=self.encoder_feat_dim,      # 512
            hidden_dim=self.half_fingerprint_dim,  # 256
            out_f=self.half_fingerprint_dim  # 256
        )

        # Classification heads (DeepfakeBench lines 78-87)
        # Specific head for different forgery types (not used in inference, but needed for weight compatibility)
        specific_task_number = config.get('specific_task_number', 5)  # Default FF++ has 5 forgery types
        self.head_spe = Head(
            in_f=self.half_fingerprint_dim,    # 256
            hidden_dim=self.encoder_feat_dim,  # 512
            out_f=specific_task_number         # 5 (or configured)
        )
        # Shared head for binary classification (real/fake)
        self.head_sha = Head(
            in_f=self.half_fingerprint_dim,    # 256
            hidden_dim=self.encoder_feat_dim,  # 512
            out_f=self.num_classes            # 2
        )

        # Store dimensions for adapter validation
        self.shared_feat_dim = self.half_fingerprint_dim  # 256

    def _build_backbone(self, config: Dict[str, Any]) -> nn.Module:
        """
        Build Xception backbone with exact DeepfakeBench configuration.

        Uses mode="adjust_channel" to get 512-dimensional features instead of 2048.
        This matches ucf.yaml backbone_config settings.
        """
        backbone_config = {
            "mode": config["mode"],           # "adjust_channel"
            "num_classes": config["num_classes"],  # 2
            "inc": config["inc"],             # 3
            "dropout": config["dropout"]      # False
        }

        backbone = Xception(backbone_config)

        # Validate backbone configuration
        assert backbone.mode == "adjust_channel", f"UCF requires mode='adjust_channel', got {backbone.mode}"
        assert hasattr(backbone, 'features'), "Backbone must have features() method"

        return backbone

    def features(self, data_dict: Dict[str, torch.Tensor]) -> Dict[str, torch.Tensor]:
        """
        Extract features from dual encoders.

        Follows DeepfakeBench ucf_detector.py lines 131-137.
        Only forgery encoder features are used in inference mode.
        """
        cat_data = data_dict['image']

        # Extract features from both encoders
        f_all = self.encoder_f.features(cat_data)  # Forgery features [N, 512, H, W]
        c_all = self.encoder_c.features(cat_data)  # Content features [N, 512, H, W] (unused in inference)

        feat_dict = {'forgery': f_all, 'content': c_all}
        return feat_dict

    def classifier(self, features: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Split features into specific and shared components using 1x1 projections.

        Follows exact DeepfakeBench ucf_detector.py lines 139-144.
        Returns both specific and shared features for architectural compatibility.
        """
        # Project forgery features to specific and shared spaces
        f_spe = self.block_spe(features)   # [N, 256, H, W] - specific features
        f_share = self.block_sha(features)  # [N, 256, H, W] - shared features
        return f_spe, f_share

    def forward_inference(self, data_dict: Dict[str, torch.Tensor]) -> Dict[str, torch.Tensor]:
        """
        Forward pass for inference mode only.

        Follows exact DeepfakeBench ucf_detector.py lines 237-264 inference branch.
        Returns logits and pooled features for the adapter.
        """
        # Extract features from dual encoders
        features = self.features(data_dict)
        forgery_features = features['forgery']  # Only use forgery encoder in inference

        # Project to specific and shared feature spaces
        f_spe, f_share = self.classifier(forgery_features)  # [N, 256, H, W] each

        # Classify using shared head
        out_sha, sha_feat = self.head_sha(f_share)  # logits [N, 2], features [N, 256]

        # Return in DeepfakeBench format for adapter consumption
        pred_dict = {
            'cls': out_sha,     # [N, 2] logits
            'feat': sha_feat    # [N, 256] pooled features
        }
        return pred_dict