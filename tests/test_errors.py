from ml.errors import (
    ERROR_CUDA_NOT_AVAILABLE,
    ERROR_INTERNAL,
    ERROR_MODEL_LOAD_FAILED,
    ERROR_NO_FACES_DETECTED,
    ERROR_PREDICTOR_NOT_FOUND,
    ERROR_VIDEO_DECODE_FAILED,
    ERROR_VIDEO_FILE_NOT_FOUND,
    MLAnalysisError,
    classify_error,
    ERROR_MESSAGES,
)


def test_ml_analysis_error_to_dict_includes_optional_details():
    err = MLAnalysisError("E001", "Something went wrong", "stack trace info")
    assert err.to_dict() == {
        "error_code": "E001",
        "message": "Something went wrong",
        "technical_details": "stack trace info",
    }


def test_ml_analysis_error_to_dict_omits_optional_details():
    err = MLAnalysisError("E002", "Another issue")
    assert err.to_dict() == {"error_code": "E002", "message": "Another issue"}


def test_classify_error_detects_no_faces():
    err = classify_error(RuntimeError("No faces detected in sample"), stage="detect")
    assert err.error_code == ERROR_NO_FACES_DETECTED
    assert err.message == ERROR_MESSAGES[ERROR_NO_FACES_DETECTED]


def test_classify_error_predictor_missing_prefers_predictor_code():
    err = classify_error(
        FileNotFoundError("dlib predictor file not found"), stage="load_models"
    )
    assert err.error_code == ERROR_PREDICTOR_NOT_FOUND


def test_classify_error_video_file_not_found():
    err = classify_error(FileNotFoundError("file not found: clip.mp4"), stage="decode")
    assert err.error_code == ERROR_VIDEO_FILE_NOT_FOUND


def test_classify_error_cuda_not_available():
    err = classify_error(RuntimeError("CUDA not available on this machine"), stage="inference")
    assert err.error_code == ERROR_CUDA_NOT_AVAILABLE


def test_classify_error_stage_decode_without_decode_text():
    err = classify_error(ValueError("bad frame data"), stage="decode")
    assert err.error_code == ERROR_VIDEO_DECODE_FAILED


def test_classify_error_stage_load_models_without_model_text():
    err = classify_error(RuntimeError("weights checksum mismatch"), stage="load_models")
    assert err.error_code == ERROR_MODEL_LOAD_FAILED


def test_classify_error_falls_back_to_internal_error():
    err = classify_error(RuntimeError("mysterious failure"), stage="postprocess")
    assert err.error_code == ERROR_INTERNAL
