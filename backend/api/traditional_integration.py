# backend/api/traditional_integration.py
"""
Traditional forensics integration wrapper.

Bridges Flask backend with traditional forensics module.
Handles traditional forensics execution and output transformation for API responses.
"""
from __future__ import annotations
import os
import tempfile
from pathlib import Path
from typing import Any, Optional

from api.traditional_forensics_utils.frame_extraction import extract_frames
from api.traditional_forensics_utils.ela_analysis import run_ela
from api.traditional_forensics_utils.noise_analysis import run_noise_analysis
from api.traditional_forensics_utils.lbp_analysis import run_lbp_analysis


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


def run_traditional_forensics(video_path: str, modules: list[str]) -> dict[str, Any]:
    """
    Run traditional forensics analysis on video.

    Args:
        video_path: Absolute path to video file
        modules: List of forensics module names (e.g., ["ela", "noise", "lbp"])

    Returns:
        {
            "ela": {
                "score": 0.65,
                "overlay": "data:image/jpeg;base64,..."  // ELA heatmap
            },
            "noise": {
                "confidence": 0.42,
                "overlay": "data:image/jpeg;base64,..."  // Noise residual
            },
            "lbp": {
                "score": 0.73,
                "overlay": "data:image/jpeg;base64,..."  // LBP pattern
            }
        }

    Raises:
        Exception: If forensics analysis fails
    """
    if not modules:
        return {}

    # Extract frames to temporary directory
    with tempfile.TemporaryDirectory(prefix="forensics_") as tmp_dir:
        try:
            frame_paths = extract_frames(video_path, output_base=tmp_dir)
            if not frame_paths:
                raise ValueError(f"No frames extracted from video: {video_path}")

            # Use the frames folder (parent of first frame)
            frames_folder = str(Path(frame_paths[0]).parent)

            results = {}

            for module_name in modules:
                try:
                    if module_name == "ela":
                        raw_result = run_ela(frames_folder, top_percent=10)
                        results["ela"] = transform_ela_result(raw_result)

                    elif module_name == "noise":
                        raw_result = run_noise_analysis(frames_folder, top_percent=10)
                        results["noise"] = transform_noise_result(raw_result)

                    elif module_name == "lbp":
                        raw_result = run_lbp_analysis(frames_folder, top_percent=10)
                        results["lbp"] = transform_lbp_result(raw_result)

                    else:
                        results[module_name] = {
                            "score": None,
                            "error": f"Unknown forensics module: {module_name}"
                        }

                except Exception as e:
                    results[module_name] = {
                        "score": None,
                        "error": f"Analysis failed: {str(e)}"
                    }

            return results

        except Exception as e:
            # If frame extraction fails, return error for all modules
            return {
                module: {
                    "score": None,
                    "error": f"Frame extraction failed: {str(e)}"
                }
                for module in modules
            }


def transform_ela_result(raw_result: dict[str, Any]) -> dict[str, Any]:
    """Transform ELA result to API response format."""
    if raw_result.get("mode") == "single_frame":
        frame_entry = {
            "frame": raw_result.get("frame"),
            "score": raw_result.get("score", 0.0),
            "overlay": raw_result.get("ela_image_base64", "")
        }
        frame_entry["frame_number"] = _parse_frame_number(frame_entry.get("frame"))
        return {
            "score": frame_entry["score"],
            "frames": [frame_entry]
        }

    # Multi-frame: use first top frame as representative
    top_frames = raw_result.get("top_frames", [])
    if top_frames:
        frame_list = [
            {
                "frame": frame.get("frame"),
                "score": frame.get("score", 0.0),
                "overlay": frame.get("ela_image_base64", ""),
                "frame_number": _parse_frame_number(frame.get("frame")),
            }
            for frame in top_frames
        ]
        return {
            "score": frame_list[0]["score"],
            "frames": frame_list
        }

    return {"score": 0.0, "frames": []}


def transform_noise_result(raw_result: dict[str, Any]) -> dict[str, Any]:
    """Transform noise result to API response format."""
    if raw_result.get("mode") == "single_frame":
        frame_entry = {
            "frame": raw_result.get("frame"),
            "confidence": raw_result.get("confidence", 0.0),
            "overlay": raw_result.get("residual_image_base64", "")
        }
        frame_entry["frame_number"] = _parse_frame_number(frame_entry.get("frame"))
        return {
            "confidence": frame_entry["confidence"],
            "score": frame_entry["confidence"],  # Also set "score" for DB compatibility
            "frames": [frame_entry]
        }

    # Multi-frame: use first top frame (z-scores can be negative)
    top_frames = raw_result.get("top_frames", [])
    if top_frames:
        frame_list = [
            {
                "frame": frame.get("frame"),
                "confidence": frame.get("score", 0.0),
                "score": frame.get("score", 0.0),  # Also set "score" for DB compatibility
                "overlay": frame.get("residual_image_base64", ""),
                "frame_number": _parse_frame_number(frame.get("frame")),
            }
            for frame in top_frames
        ]
        return {
            "confidence": frame_list[0]["confidence"],
            "score": frame_list[0]["score"],  # Also set "score" for DB compatibility
            "frames": frame_list
        }

    return {"confidence": 0.0, "score": 0.0, "frames": []}


def transform_lbp_result(raw_result: dict[str, Any]) -> dict[str, Any]:
    """Transform LBP result to API response format."""
    if raw_result.get("mode") == "single_frame":
        frame_entry = {
            "frame": raw_result.get("frame"),
            "score": raw_result.get("score", 0.0),
            "overlay": raw_result.get("lbp_image_base64", "")
        }
        frame_entry["frame_number"] = _parse_frame_number(frame_entry.get("frame"))
        return {
            "score": frame_entry["score"],
            "frames": [frame_entry]
        }

    # Multi-frame: use first top frame
    top_frames = raw_result.get("top_frames", [])
    if top_frames:
        frame_list = [
            {
                "frame": frame.get("frame"),
                "score": frame.get("normalized_score", frame.get("score", 0.0)),
                "overlay": frame.get("lbp_image_base64", ""),
                "frame_number": _parse_frame_number(frame.get("frame")),
            }
            for frame in top_frames
        ]
        return {
            "score": frame_list[0]["score"],
            "frames": frame_list
        }

    return {"score": 0.0, "frames": []}
