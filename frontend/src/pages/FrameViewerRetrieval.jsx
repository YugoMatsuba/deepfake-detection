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

  const flaggedFrameIndices = useMemo(() => {
    if (!Array.isArray(mlFramesRaw)) {
      return [];
    }
    return mlFramesRaw
      .map((frame) => {
        if (typeof frame === "number") {
          return frame;
        }
        if (frame && typeof frame.index === "number") {
          return frame.index;
        }
        return null;
      })
      .filter((idx) => typeof idx === "number");
  }, [mlFramesRaw]);

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
      />
    </div>
  );
}
