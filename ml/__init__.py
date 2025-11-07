"""
ML inference package for deepfake detection.

This package provides inference-only functionality for deepfake detection models.
No training or evaluation loops - only loading and running published checkpoints.

Public API:
    run: Full video analysis with multiple models
    analyze_single_frame: Single frame analysis
    MLAnalysisError: Base exception for ML errors
    classify_error: Error classification helper
"""

from ml.runner import run, analyze_single_frame
from ml.errors import MLAnalysisError, classify_error

__all__ = [
    "run",
    "analyze_single_frame",
    "MLAnalysisError",
    "classify_error",
]
