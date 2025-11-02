# Synthetic Media Score Metric

**Last updated:** 2 November 2025
**Status:** Validated on FaceForensics++ dataset

## Purpose

This document explains how the system calculates the overall **Synthetic Media Chance** score from machine learning model outputs, and why this approach was chosen for forensic analysis.

## Overview

The Synthetic Media Chance is a single percentage representing the likelihood that a video contains manipulated content. It is calculated using a **top-5 ensemble averaging** method designed to detect localized manipulations rather than requiring the entire video to be fake.

## Calculation Method

### Algorithm

1. **Per-frame ensemble averaging**
   For each of the 32 sampled frames, calculate the mean probability across all three ML models:
   ```
   frame_score = (xception_score + spsl_score + ucf_score) / 3
   ```

2. **Sort frames by suspicion**
   Rank all frames by their ensemble scores in descending order.

3. **Select top 5 frames**
   Take the 5 highest-scoring frames (or fewer if less than 5 frames were analyzed).

4. **Calculate final score**
   ```
   synthetic_media_chance = mean(top_5_frame_scores)
   ```

### Example

If a video's frame ensemble scores are:
`[0.95, 0.92, 0.88, 0.45, 0.41, 0.38, ..., 0.12]`

The top-5 scores are: `[0.95, 0.92, 0.88, 0.45, 0.41]`
Final score: `(0.95 + 0.92 + 0.88 + 0.45 + 0.41) / 5 = 0.722` → **72% Synthetic Media Chance**

## Forensic Rationale

### Why Top-5 Averaging?

Real-world deepfake videos often contain **localized manipulations** — only certain segments or frames are synthetic, while the majority of the video remains authentic. Common scenarios include:

- Face-swapped segments in an otherwise real video
- Spliced inserts of AI-generated content
- Partial edits where only a speaker's mouth or facial expressions are manipulated

A simple mean across all frames would **dilute strong manipulation signals**:
- Example: 5 fake frames (scores ~0.90) + 27 real frames (scores ~0.10) → overall mean = 0.24 (misleadingly low)

By averaging only the **top 5 most suspicious frames**, the metric:
- Captures localized fakes without requiring the entire video to be synthetic
- Smooths out single-frame outliers (more stable than using the maximum score)
- Remains interpretable for non-technical stakeholders

### Validation

This method was validated on the **FaceForensics++ dataset** (c23 compression):
- **K=5, threshold=0.80** achieved **92.0% accuracy** in binary classification
- Outperformed simple averaging in detecting partially manipulated videos

## Interpretation Guidelines

| Score Range | Classification | Interpretation |
|-------------|----------------|----------------|
| 90-100% | Very likely fake | Strong evidence of manipulation across top frames |
| 85-89% | Likely fake | Consistent suspicious patterns in top frames |
| 80-84% | Possibly fake | Moderate evidence; warrants further investigation |
| 60-79% | Uncertain | Mixed signals; inconclusive |
| 40-59% | Likely real | Low suspicion; typical of authentic content |
| 0-39% | Very likely real | Minimal manipulation indicators |

**Important:** The score represents the **strength of manipulation evidence in the most suspicious segments**, not the percentage of the video that is fake.

## Technical Implementation

- **Models:** Xception, SPSL (Spatial-Phase Shallow Learning), UCF (Uncovering Common Features)
- **Frame sampling:** 32 frames per video (uniform temporal sampling)
- **K value:** Fixed at 5 based on empirical validation
- **Output precision:** Rounded to nearest percentage for reports

## Limitations

- Assumes at least 5 frames were successfully analyzed (uses fewer if necessary)
- Designed for temporal deepfakes; may behave differently on spatial-only manipulations
- Score is relative to training data distribution (FaceForensics++ and similar datasets)
- Cannot distinguish between manipulation types (face swap vs. expression reenactment vs. full synthesis)

## References

- Validation dataset: FaceForensics++ (c23 compression level)
- Evaluation metric: Binary classification accuracy at 80% threshold
- Model architectures: See ML module documentation for Xception, SPSL, and UCF implementations
