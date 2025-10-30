/**
 * ML Score Calculation Utilities
 *
 * Calculates ensemble scores from ML model results using top-5 averaging.
 */

/**
 * Calculate top-5 ensemble score from ML model data.
 *
 * For each frame:
 * 1. Calculate ensemble average: (xception + spsl + ucf) / 3
 * 2. Sort all ensemble scores descending
 * 3. Take mean of top 5 scores
 *
 * @param {Object} mlData - ML results object: {xception: {frames: [...], score: ...}, spsl: {...}, ucf: {...}}
 * @returns {Object} - {score: 0.85, scorePercent: 85, classification: "Likely fake"} or null if insufficient data
 */
export function calculateTop5EnsembleScore(mlData) {
  if (!mlData || typeof mlData !== 'object') {
    return null;
  }

  // Extract models we care about
  const models = ['xception', 'spsl', 'ucf'];
  const modelData = models.map(name => mlData[name]).filter(Boolean);

  if (modelData.length === 0) {
    return null;
  }

  // Collect all unique frame indices that have data from ALL models
  const frameScoresMap = new Map(); // frameIndex -> {xception: score, spsl: score, ucf: score}

  for (const modelName of models) {
    const modelInfo = mlData[modelName];
    if (!modelInfo) continue;

    const frames = modelInfo.frames || [];
    for (const frame of frames) {
      const index = frame.index;
      if (!frameScoresMap.has(index)) {
        frameScoresMap.set(index, {});
      }
      frameScoresMap.get(index)[modelName] = frame.score;
    }
  }

  // Filter to frames that have scores from all 3 models
  const ensembleScores = [];
  for (const [index, scores] of frameScoresMap.entries()) {
    if (scores.xception !== undefined && scores.spsl !== undefined && scores.ucf !== undefined) {
      const ensembleScore = (scores.xception + scores.spsl + scores.ucf) / 3;
      ensembleScores.push(ensembleScore);
    }
  }

  if (ensembleScores.length === 0) {
    return null;
  }

  // Sort descending
  ensembleScores.sort((a, b) => b - a);

  // Take top 5 (or all if fewer than 5)
  const topN = Math.min(5, ensembleScores.length);
  const top5Scores = ensembleScores.slice(0, topN);

  // Calculate mean
  const meanScore = top5Scores.reduce((sum, score) => sum + score, 0) / top5Scores.length;

  // Determine classification
  const classification = getClassification(meanScore);

  return {
    score: meanScore,
    scorePercent: Math.round(meanScore * 100),
    classification: classification
  };
}

/**
 * Get classification band for a given score.
 *
 * @param {number} score - Score between 0.0 and 1.0
 * @returns {string} - Classification text
 */
export function getClassification(score) {
  if (score >= 0.90) {
    return "Very likely fake";
  } else if (score >= 0.85) {
    return "Likely fake";
  } else if (score >= 0.80) {
    return "Possibly fake";
  } else if (score >= 0.60) {
    return "Likely real";
  } else {
    return "Very likely real";
  }
}

/**
 * Get info text explaining the scoring methodology.
 *
 * @returns {string} - Multi-line explanation text
 */
export function getScoringMethodologyInfo() {
  return `This score represents the average of the 5 highest-scoring frames from the analysis.

Each frame's score is calculated as the ensemble average across all 3 ML models (Xception, SPSL, UCF).

Classification Bands:
• Very likely fake: ≥ 90%
• Likely fake: 85-90%
• Possibly fake: 80-85% (binary decision flips to "fake" at 80%)
• Likely real: 60-80%
• Very likely real: < 60%`;
}
