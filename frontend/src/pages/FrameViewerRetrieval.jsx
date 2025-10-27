import React, { useCallback, useEffect, useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import FrameViewer from './FrameViewer';
import { useAnalysis } from '../app/AnalysisProvider';

export default function FrameViewerPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const { analysisResult, setAnalysisResult } = useAnalysis();
  const state = location.state || {};

  const analysisId = state.analysisId || analysisResult?.analysis_id;
  const fps =
    state.fps ??
    analysisResult?.ml_video?.fps ??
    null;

  const mlFramesRaw = state.mlFrames ?? analysisResult?.ml_frames ?? [];
  const mlModels = state.mlModels ?? analysisResult?.ml ?? {};
  const traditionalResults = state.traditional ?? analysisResult?.traditional ?? {};

  const handleTraditionalResultsUpdate = useCallback(
    (updatedTraditional) => {
      setAnalysisResult((prev) => {
        if (!prev) {
          return prev;
        }
        return {
          ...prev,
          traditional: updatedTraditional,
        };
      });
    },
    [setAnalysisResult]
  );

  const handleMLResultsUpdate = useCallback(
    (updatedML, frameNumber) => {
      setAnalysisResult((prev) => {
        if (!prev) {
          return prev;
        }

        // Update ml models data
        const newML = updatedML;

        // Update ml_frames to include the new frame
        const currentFrames = prev.ml_frames || [];
        const updatedFrames = currentFrames.includes(frameNumber)
          ? currentFrames
          : [...currentFrames, frameNumber].sort((a, b) => a - b);

        return {
          ...prev,
          ml: newML,
          ml_frames: updatedFrames
        };
      });
    },
    [setAnalysisResult]
  );

  const flaggedFrameIndices = useMemo(() => {
    const indices = new Set();

    // Add frames from mlFramesRaw (initially filtered frames)
    if (Array.isArray(mlFramesRaw)) {
      mlFramesRaw.forEach((frame) => {
        if (typeof frame === "number") {
          indices.add(frame);
        } else if (frame && typeof frame.index === "number") {
          indices.add(frame.index);
        }
      });
    }

    // ALSO add any frames with requested_adhoc: true from mlModels
    // This ensures ad-hoc frames show up on initial page load
    Object.values(mlModels).forEach((model) => {
      if (model.frames) {
        model.frames.forEach((f) => {
          if (f.requested_adhoc === true && typeof f.index === "number") {
            indices.add(f.index);
          }
        });
      }
    });

    return Array.from(indices).sort((a, b) => a - b);
  }, [mlFramesRaw, mlModels]);

  useEffect(() => {
    if (!analysisId) {
      navigate('/upload', { replace: true });
    }
  }, [analysisId, navigate]);

  if (!analysisId) {
    return null;
  }

  // Construct the secure video URL
  const videoSrc = `http://localhost:5050/api/analyses/${analysisId}/video`;

  return (
    <div className="p-4">
      <h1 className="text-3xl font-bold mb-4">Frame Analysis</h1>
      <FrameViewer
        videoSrc={videoSrc}
        initialFrameRate={fps}
        deepfakeFrames={flaggedFrameIndices}
        deepfakeMeta={mlModels}
        traditionalResults={traditionalResults}
        analysisId={analysisId}
        onTraditionalResultsUpdate={handleTraditionalResultsUpdate}
        onMLResultsUpdate={handleMLResultsUpdate}
      />
    </div>
  );
}
