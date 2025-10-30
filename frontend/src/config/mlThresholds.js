/**
 * ML Classification Threshold Configuration
 *
 * Single source of truth for classification bands.
 * To modify thresholds or add/remove categories, edit this file only.
 *
 * Based on evaluation findings: k=5, thresh=0.80 → Acc=0.920
 */

/**
 * Classification thresholds (descending order by minScore).
 * Each score is classified by the first matching threshold.
 *
 * Format: { minScore: number, label: string }
 */
export const ML_THRESHOLDS = [
  { minScore: 0.9, label: "Very likely fake" },
  { minScore: 0.85, label: "Likely fake" },
  { minScore: 0.8, label: "Possibly fake" },
  { minScore: 0.7, label: "Uncertain" },
  { minScore: 0.6, label: "Likely real" },
  { minScore: 0, label: "Very likely real" }  // Catch-all for < 0.6
];

/**
 * Get classification label for a given score.
 *
 * @param {number} score - Score between 0.0 and 1.0
 * @returns {string} Classification label
 */
export function getClassification(score) {
  for (const threshold of ML_THRESHOLDS) {
    if (score >= threshold.minScore) {
      return threshold.label;
    }
  }
  // Fallback (should never reach here if thresholds include minScore: 0)
  return "Unknown";
}

/**
 * Get methodology info text for InfoButton tooltip.
 * Dynamically builds the classification bands from ML_THRESHOLDS.
 *
 * @returns {string} Formatted methodology description
 */
export function getMethodologyInfo() {
  // Build classification bands text
  const bands = [];

  for (let i = 0; i < ML_THRESHOLDS.length; i++) {
    const current = ML_THRESHOLDS[i];
    const next = ML_THRESHOLDS[i + 1];

    const minPercent = Math.round(current.minScore * 100);

    if (next) {
      const nextPercent = Math.round(next.minScore * 100);
      if (minPercent === nextPercent) {
        // Skip if range would be empty (e.g., 0% - 0%)
        continue;
      }
      bands.push(`• ${current.label}: ${nextPercent + 1}-${minPercent}%`);
    } else {
      // Last threshold (catch-all)
      bands.push(`• ${current.label}: < ${minPercent}%`);
    }
  }

  // Special note for binary decision threshold (0.80)
  const binaryThresholdIndex = ML_THRESHOLDS.findIndex(t => t.minScore === 0.8);
  if (binaryThresholdIndex !== -1) {
    const binaryPercent = Math.round(ML_THRESHOLDS[binaryThresholdIndex].minScore * 100);
    bands[binaryThresholdIndex] += ` (binary decision flips to "fake" at ${binaryPercent}%)`;
  }

  return `This score represents the average of the 5 highest-scoring frames from the analysis.

Each frame's score is calculated as the ensemble average across all 3 ML models (Xception, SPSL, UCF).

Classification Bands:
${bands.join('\n')}`;
}
