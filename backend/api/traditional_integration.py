# backend/api/traditional_integration.py
"""
Traditional forensics integration wrapper.

Bridges Flask backend with traditional forensics module.
Handles traditional forensics execution and output transformation for API responses.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any, Optional

from api.traditional_forensics_utils.frame_extraction import extract_frames
from api.traditional_forensics_utils.ela_analysis import run_ela
from api.traditional_forensics_utils.noise_analysis import run_noise_analysis
from api.traditional_forensics_utils.lbp_analysis import run_lbp_analysis
from storage import DATA_ROOT


def _parse_frame_number(frame_label: Optional[str]) -> Optional[int]:
    """
    Attempt to parse a numeric frame index from a frame label (e.g., 'frame_0005.jpg').
    Returns None if no numeric portion is found.
    """
    if not frame_label:
        return None

    stem = Path(frame_label).stem
    digits = "".join(ch for ch in stem if ch.isdigit())
    if digits:
        try:
            return int(digits)
        except ValueError:
            return None
    return None


def run_traditional_forensics(video_path: str, modules: list[str], analysis_id: str) -> dict[str, Any]:
    """
    Run traditional forensics analysis on video.

    Args:
        video_path: Absolute path to video file
        modules: List of forensics module names (e.g., ["ela", "noise", "lbp"])
        analysis_id: Analysis UUID for persistent storage

    Returns:
        {
            "ela": {
                "score": 0.65,
                "frames": [{"frame": "frame_0001.jpg", "frame_number": 1, "score": 0.65, "overlay_url": "/api/..."}]
            },
            "noise": {
                "confidence": 0.42,
                "frames": [{"frame": "frame_0001.jpg", "frame_number": 1, "confidence": 0.42, "overlay_url": "/api/..."}]
            },
            "lbp": {
                "score": 0.73,
                "frames": [{"frame": "frame_0001.jpg", "frame_number": 1, "score": 0.73, "overlay_url": "/api/..."}]
            }
        }

    Raises:
        Exception: If forensics analysis fails
    """
    if not modules:
        return {}

    # Extract frames to persistent directory
    frames_dir = DATA_ROOT / analysis_id / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    try:
        frame_paths = extract_frames(video_path, output_base=str(frames_dir))
        if not frame_paths:
            raise ValueError(f"No frames extracted from video: {video_path}")

        # Use the frames folder (parent of first frame)
        frames_folder = str(Path(frame_paths[0]).parent)

        # Create forensics output directory
        forensics_dir = DATA_ROOT / analysis_id / "forensics"
        forensics_dir.mkdir(parents=True, exist_ok=True)

        results = {}

        for module_name in modules:
            try:
                # Create method-specific directory
                method_dir = forensics_dir / module_name
                method_dir.mkdir(parents=True, exist_ok=True)

                if module_name == "ela":
                    raw_result = run_ela(frames_folder, top_percent=10, output_dir=str(method_dir), analysis_id=analysis_id)
                    results["ela"] = transform_ela_result(raw_result, analysis_id)

                elif module_name == "noise":
                    raw_result = run_noise_analysis(
                        frames_folder, top_percent=10, output_dir=str(method_dir), analysis_id=analysis_id
                    )
                    results["noise"] = transform_noise_result(raw_result, analysis_id)

                elif module_name == "lbp":
                    raw_result = run_lbp_analysis(
                        frames_folder, top_percent=10, output_dir=str(method_dir), analysis_id=analysis_id
                    )
                    results["lbp"] = transform_lbp_result(raw_result, analysis_id)

                else:
                    results[module_name] = {"score": None, "error": f"Unknown forensics module: {module_name}"}

            except Exception as e:
                results[module_name] = {"score": None, "error": f"Analysis failed: {str(e)}"}

        return results

    except Exception as e:
        # If frame extraction fails, return error for all modules
        return {module: {"score": None, "error": f"Frame extraction failed: {str(e)}"} for module in modules}


def transform_ela_result(raw_result: dict[str, Any], analysis_id: str) -> dict[str, Any]:
    """Transform ELA result to API response format with overlay URLs."""
    if raw_result.get("mode") == "single_frame":
        frame_number = _parse_frame_number(raw_result.get("frame"))
        frame_entry = {
            "frame": raw_result.get("frame"),
            "score": raw_result.get("score", 0.0),
            "frame_number": frame_number,
            "overlay_url": (
                f"/api/analyses/{analysis_id}/forensics/ela/frames/{frame_number}/overlay"
                if frame_number is not None
                else None
            ),
            "requested_adhoc": True,  # Ad-hoc single-frame analysis
        }
        return {"score": frame_entry["score"], "frames": [frame_entry]}

    # Multi-frame: use first top frame as representative
    top_frames = raw_result.get("top_frames", [])
    if top_frames:
        frame_list = []
        for frame in top_frames:
            frame_number = _parse_frame_number(frame.get("frame"))
            frame_list.append(
                {
                    "frame": frame.get("frame"),
                    "raw_score": frame.get("raw_score", frame.get("score", 0.0)),  # Preserve raw score
                    "score": frame.get("score", 0.0),
                    "frame_number": frame_number,
                    "overlay_url": (
                        f"/api/analyses/{analysis_id}/forensics/ela/frames/{frame_number}/overlay"
                        if frame_number is not None
                        else None
                    ),
                    "flagged": frame.get("flagged", False),  # Pass through flagged status
                    "requested_adhoc": False,  # Initial analysis frames
                }
            )
        # Overall score = MAX z-score (most suspicious frame)
        max_score = max(f["score"] for f in frame_list)
        return {"score": max_score, "frames": frame_list}

    return {"score": 0.0, "frames": []}


def transform_noise_result(raw_result: dict[str, Any], analysis_id: str) -> dict[str, Any]:
    """Transform noise result to API response format with overlay URLs."""
    if raw_result.get("mode") == "single_frame":
        frame_number = _parse_frame_number(raw_result.get("frame"))
        frame_entry = {
            "frame": raw_result.get("frame"),
            "confidence": raw_result.get("confidence", 0.0),
            "frame_number": frame_number,
            "overlay_url": (
                f"/api/analyses/{analysis_id}/forensics/noise/frames/{frame_number}/overlay"
                if frame_number is not None
                else None
            ),
            "requested_adhoc": True,  # Ad-hoc single-frame analysis
        }
        return {
            "confidence": frame_entry["confidence"],
            "score": frame_entry["confidence"],  # Also set "score" for DB compatibility
            "frames": [frame_entry],
        }

    # Multi-frame: use first top frame (z-scores can be negative)
    top_frames = raw_result.get("top_frames", [])
    if top_frames:
        frame_list = []
        for frame in top_frames:
            frame_number = _parse_frame_number(frame.get("frame"))
            z_score = frame.get("score", 0.0)
            frame_list.append(
                {
                    "frame": frame.get("frame"),
                    "raw_score": frame.get("raw_score", z_score),  # Preserve raw score
                    "confidence": z_score,  # Z-score
                    "score": z_score,  # Also store as "score" for consistency
                    "frame_number": frame_number,
                    "overlay_url": (
                        f"/api/analyses/{analysis_id}/forensics/noise/frames/{frame_number}/overlay"
                        if frame_number is not None
                        else None
                    ),
                    "flagged": frame.get("flagged", False),  # Pass through flagged status
                    "requested_adhoc": False,  # Initial analysis frames
                }
            )
        # Overall score = MAX z-score (most suspicious frame)
        max_score = max(f["score"] for f in frame_list)
        return {"confidence": max_score, "score": max_score, "frames": frame_list}

    return {"confidence": 0.0, "score": 0.0, "frames": []}


def transform_lbp_result(raw_result: dict[str, Any], analysis_id: str) -> dict[str, Any]:
    """Transform LBP result to API response format with overlay URLs."""
    if raw_result.get("mode") == "single_frame":
        frame_number = _parse_frame_number(raw_result.get("frame"))
        frame_entry = {
            "frame": raw_result.get("frame"),
            "score": raw_result.get("score", 0.0),
            "frame_number": frame_number,
            "overlay_url": (
                f"/api/analyses/{analysis_id}/forensics/lbp/frames/{frame_number}/overlay"
                if frame_number is not None
                else None
            ),
            "requested_adhoc": True,  # Ad-hoc single-frame analysis
        }
        return {"score": frame_entry["score"], "frames": [frame_entry]}

    # Multi-frame: use first top frame
    top_frames = raw_result.get("top_frames", [])
    if top_frames:
        frame_list = []
        for frame in top_frames:
            frame_number = _parse_frame_number(frame.get("frame"))
            frame_list.append(
                {
                    "frame": frame.get("frame"),
                    "raw_score": frame.get("raw_score", frame.get("score", 0.0)),  # Preserve raw score
                    "score": frame.get("normalized_score", frame.get("score", 0.0)),
                    "frame_number": frame_number,
                    "overlay_url": (
                        f"/api/analyses/{analysis_id}/forensics/lbp/frames/{frame_number}/overlay"
                        if frame_number is not None
                        else None
                    ),
                    "flagged": frame.get("flagged", False),  # Pass through flagged status
                    "requested_adhoc": False,  # Initial analysis frames
                }
            )
        # Overall score = MAX z-score (most suspicious frame)
        max_score = max(f["score"] for f in frame_list)
        return {"score": max_score, "frames": frame_list}

    return {"score": 0.0, "frames": []}
