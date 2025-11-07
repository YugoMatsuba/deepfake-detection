"""
ML inference package for deepfake detection.

This package provides inference-only functionality for deepfake detection models.
No training or evaluation loops - only loading and running published checkpoints.

Public API:
    run: Full video analysis with multiple models
    analyze_single_frame: Single frame analysis
    MLAnalysisError: Base exception for ML errors
    classify_error: Error classification helper

Note: Imports are not performed at package level to avoid loading heavy
dependencies (torch, cv2, etc.) until actually needed.
"""

__all__ = [
    "run",
    "analyze_single_frame",
    "MLAnalysisError",
    "classify_error",
]
