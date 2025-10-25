# ml/errors.py
"""
User-friendly error codes and messages for ML analysis failures.

Maps low-level errors (dlib, OpenCV, torch) to structured error responses
that can be displayed to end users with actionable guidance.
"""

from typing import Dict, Optional


class MLAnalysisError(Exception):
    """Base exception for ML analysis errors with user-friendly codes."""

    def __init__(self, error_code: str, message: str, technical_details: Optional[str] = None):
        self.error_code = error_code
        self.message = message
        self.technical_details = technical_details
        super().__init__(message)

    def to_dict(self) -> Dict[str, str]:
        """Convert to JSON-serializable dict for API responses."""
        result = {
            "error_code": self.error_code,
            "message": self.message
        }
        if self.technical_details:
            result["technical_details"] = self.technical_details
        return result


# Error code constants
ERROR_NO_FACES_DETECTED = "NO_FACES_DETECTED"
ERROR_VIDEO_DECODE_FAILED = "VIDEO_DECODE_FAILED"
ERROR_VIDEO_FILE_NOT_FOUND = "VIDEO_FILE_NOT_FOUND"
ERROR_CORRUPT_VIDEO = "CORRUPT_VIDEO"
ERROR_MODEL_LOAD_FAILED = "MODEL_LOAD_FAILED"
ERROR_CUDA_NOT_AVAILABLE = "CUDA_NOT_AVAILABLE"
ERROR_INTERNAL = "INTERNAL_ERROR"
ERROR_PREDICTOR_NOT_FOUND = "PREDICTOR_NOT_FOUND"


# User-friendly error messages
ERROR_MESSAGES = {
    ERROR_NO_FACES_DETECTED: "No faces detected in the video. The ML models require at least one face to be visible in the frames.",
    ERROR_VIDEO_DECODE_FAILED: "Unable to decode the video file. The file may be corrupted or in an unsupported format.",
    ERROR_VIDEO_FILE_NOT_FOUND: "Video file not found. The file may have been moved or deleted.",
    ERROR_CORRUPT_VIDEO: "Video file appears to be corrupted or incomplete.",
    ERROR_MODEL_LOAD_FAILED: "Failed to load ML detection models. Please contact support.",
    ERROR_CUDA_NOT_AVAILABLE: "GPU (CUDA) was requested but is not available on this system.",
    ERROR_INTERNAL: "An unexpected error occurred during analysis. Please try again or contact support.",
    ERROR_PREDICTOR_NOT_FOUND: "Face detection model files not found. Please contact support.",
}


def classify_error(exception: Exception, stage: str) -> MLAnalysisError:
    """
    Classify a raw exception into a user-friendly MLAnalysisError.

    Args:
        exception: The original exception
        stage: Pipeline stage where error occurred (e.g., "decode", "load_models")

    Returns:
        MLAnalysisError with appropriate error code and message
    """
    error_str = str(exception).lower()

    # Check for specific error patterns
    if "no faces" in error_str or "no frames/faces detected" in error_str:
        return MLAnalysisError(
            ERROR_NO_FACES_DETECTED,
            ERROR_MESSAGES[ERROR_NO_FACES_DETECTED],
            technical_details=str(exception)
        )

    if "file not found" in error_str or "does not exist" in error_str:
        if "predictor" in error_str or "dlib" in error_str:
            return MLAnalysisError(
                ERROR_PREDICTOR_NOT_FOUND,
                ERROR_MESSAGES[ERROR_PREDICTOR_NOT_FOUND],
                technical_details=str(exception)
            )
        return MLAnalysisError(
            ERROR_VIDEO_FILE_NOT_FOUND,
            ERROR_MESSAGES[ERROR_VIDEO_FILE_NOT_FOUND],
            technical_details=str(exception)
        )

    if "cuda" in error_str and ("not available" in error_str or "unavailable" in error_str):
        return MLAnalysisError(
            ERROR_CUDA_NOT_AVAILABLE,
            ERROR_MESSAGES[ERROR_CUDA_NOT_AVAILABLE],
            technical_details=str(exception)
        )

    if stage == "decode" or "decode" in error_str or "video" in error_str:
        return MLAnalysisError(
            ERROR_VIDEO_DECODE_FAILED,
            ERROR_MESSAGES[ERROR_VIDEO_DECODE_FAILED],
            technical_details=str(exception)
        )

    if stage == "load_models" or "load" in error_str or "model" in error_str:
        return MLAnalysisError(
            ERROR_MODEL_LOAD_FAILED,
            ERROR_MESSAGES[ERROR_MODEL_LOAD_FAILED],
            technical_details=str(exception)
        )

    # Generic fallback
    return MLAnalysisError(
        ERROR_INTERNAL,
        ERROR_MESSAGES[ERROR_INTERNAL],
        technical_details=str(exception)
    )
