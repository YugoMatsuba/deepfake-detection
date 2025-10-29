/**
 * Forensics method explanations for info buttons.
 * Provides detailed explanations of how each metric is calculated.
 */

export const forensicsInfo = {
  // Single Image Explanations (Raw Scores)
  singleImage: {
    ela: {
      title: "ELA Score (Single Image)",
      content: `Error Level Analysis measures compression artifacts to detect manipulation.

How it's calculated:
1. The image is resaved as JPEG (quality=90)
2. Pixel-level differences between original and compressed version are computed
3. Score = standard deviation of the difference array

Interpretation:
• Higher values indicate more compression artifacts
• Suggests potential manipulation or editing`
    },

    noise: {
      title: "Noise Score (Single Image)",
      content: `Noise analysis detects inconsistent noise patterns that indicate splicing or manipulation.

How it's calculated:
1. Image is divided into 8×8 sliding windows (4px stride)
2. Standard deviation is computed for each block
3. Blocks are converted to z-scores within the image
4. Score = mean of top 10% block z-scores

Interpretation:
• Higher values indicate inconsistent noise patterns
• Suggests potential splicing or local manipulation`
    },

    lbp: {
      title: "LBP Score (Single Image)",
      content: `Local Binary Patterns analyze texture features to detect manipulation boundaries.

How it's calculated:
1. Compute local binary patterns (8 neighbors, radius=1)
2. Build normalized histogram of LBP values
3. Score = standard deviation of the histogram

Interpretation:
• Higher values indicate more texture variation/diversity
• Suggests potential manipulation boundaries or edits`
    }
  },

  // Video Explanations (Z-Scores)
  video: {
    ela: {
      title: "ELA Score (Video Frame)",
      content: `Error Level Analysis for video frames uses z-scores to compare frames relative to each other.

How it's calculated:
1. Raw ELA score computed for each frame
2. Frames are compared relative to video average with a z-score

Interpretation:
• Z = 0: Average compression artifacts
• Z > 0: Above-average artifacts (more suspicious)
• Z < 0: Below-average artifacts (less suspicious)`
    },

    noise: {
      title: "Noise Score (Video Frame)",
      content: `Noise analysis for video frames uses z-scores to identify frames with anomalous noise patterns.

How it's calculated:
1. Raw noise score computed for each frame
2. Frames are compared relative to video average with a z-score

Interpretation:
• Z = 0: Average noise patterns
• Z > 0: Above-average noise inconsistency (more suspicious)
• Z < 0: Below-average noise inconsistency (less suspicious)`
    },

    lbp: {
      title: "LBP Score (Video Frame)",
      content: `Local Binary Patterns for video frames uses z-scores to identify frames with unusual textures.

How it's calculated:
1. Raw LBP score computed for each frame
2. Frames are compared relative to video average with a z-score

Interpretation:
• Z = 0: Average texture variation
• Z > 0: Above-average texture diversity (more suspicious)
• Z < 0: Below-average texture diversity (less suspicious)`
    }
  }
};
