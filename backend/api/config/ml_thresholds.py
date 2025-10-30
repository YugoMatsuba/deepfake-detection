"""
ML Classification Threshold Configuration

Single source of truth for classification bands.
To modify thresholds or add/remove categories, edit this file only.

Based on evaluation findings: k=5, thresh=0.80 → Acc=0.920
"""
from typing import Tuple, List


# Classification thresholds (descending order by min_score)
# Format: (min_score: float, label: str)
ML_THRESHOLDS: List[Tuple[float, str]] = [
    (0.9, "Very likely fake"),
    (0.85, "Likely fake"),
    (0.8, "Possibly fake"),
    (0.6, "Uncertain"),
    (0.4, "Likely real"),
    (0.0, "Very likely real"),
]


def get_classification(score: float) -> str:
    """
    Get classification label for a given score.

    Args:
        score: Float between 0.0 and 1.0

    Returns:
        Classification label string
    """
    for min_score, label in ML_THRESHOLDS:
        if score >= min_score:
            return label

    # Fallback (should never reach here if thresholds include 0.0)
    return "Unknown"


def get_methodology_description() -> str:
    """
    Get methodology description for PDF footer.
    Dynamically builds text from ML_THRESHOLDS.

    Returns:
        Formatted methodology description
    """
    # Build classification bands text
    bands = []

    for i in range(len(ML_THRESHOLDS)):
        current_score, current_label = ML_THRESHOLDS[i]
        current_pct = int(current_score * 100)

        if i == 0:
            # First threshold: goes up to 100%
            bands.append(f"{current_label}: {current_pct}-100%")
        else:
            # Other thresholds: range from current to (previous - 1)
            previous_score, _ = ML_THRESHOLDS[i - 1]
            previous_pct = int(previous_score * 100)
            bands.append(f"{current_label}: {current_pct}-{previous_pct - 1}%")

    bands_text = ", ".join(bands)

    return (
        f"The overall score represents the average of the top 5 highest-scoring frames, "
        f"where each frame's score is the ensemble average across all ML models (Xception, SPSL, UCF). "
        f"Classification bands: {bands_text}. "
        f"Higher scores indicate greater likelihood of manipulation."
    )
