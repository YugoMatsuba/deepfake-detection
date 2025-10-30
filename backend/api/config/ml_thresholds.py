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
    (0.7, "Uncertain"),
    (0.6, "Likely real"),
    (0.0, "Very likely real"),  # Catch-all for < 0.6
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

        if i + 1 < len(ML_THRESHOLDS):
            next_score, _ = ML_THRESHOLDS[i + 1]

            min_pct = int(current_score * 100)
            next_pct = int(next_score * 100)

            if min_pct == next_pct:
                # Skip if range would be empty
                continue

            bands.append(f"{current_label}: {next_pct + 1}-{min_pct}%")
        else:
            # Last threshold (catch-all)
            min_pct = int(current_score * 100)
            bands.append(f"{current_label}: < {min_pct}%")

    # Special note for binary decision threshold (0.80)
    binary_threshold = 0.8
    binary_pct = int(binary_threshold * 100)
    for i, (score, label) in enumerate(ML_THRESHOLDS):
        if score == binary_threshold:
            bands[i] += f' (binary decision flips to "fake" at {binary_pct}%)'
            break

    bands_text = ", ".join(bands)

    return (
        f"The overall score represents the average of the top 5 highest-scoring frames, "
        f"where each frame's score is the ensemble average across all ML models (Xception, SPSL, UCF). "
        f"Classification bands: {bands_text}. "
        f"Higher scores indicate greater likelihood of manipulation."
    )
