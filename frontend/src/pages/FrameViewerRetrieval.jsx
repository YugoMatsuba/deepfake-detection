import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import FrameViewer from './FrameViewer';
import { useAnalysis } from '../app/AnalysisProvider';

export default function FrameViewerPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const { setAnalysisResult } = useAnalysis();
  const state = location.state || {};

  const [analysisData, setAnalysisData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const analysisId = state.analysisId;

  // ALWAYS fetch analysis data from backend on load
  useEffect(() => {
    if (!analysisId) {
      navigate('/upload', { replace: true });
      return;
    }

    setIsLoading(true);
    setError(null);

    fetch(`/api/analyses/${analysisId}`, { credentials: 'include' })
      .then(res => {
        if (!res.ok) {
          throw new Error('Failed to fetch analysis');
        }
        return res.json();
      })
      .then(data => {
        setAnalysisData(data);
        setIsLoading(false);
      })
      .catch(err => {
        console.error('Failed to fetch analysis data:', err);
        setError(err.message);
        setIsLoading(false);
      });
  }, [analysisId, navigate]);

  const mlModels = analysisData?.result?.ml || {};
  const traditionalResults = analysisData?.result?.traditional || {};
  const metadata = analysisData?.result?.metadata || null;
  const fps = analysisData?.result?.video?.fps || null;

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

  // Filter frames: show if (average score > 0.5) OR (requested_adhoc === true)
  const flaggedFrameIndices = useMemo(() => {
    const indices = new Set();

    // Collect all unique frame indices
    const allFrameIndices = new Set();
    Object.values(mlModels).forEach((model) => {
      if (model.frames) {
        model.frames.forEach((f) => {
          if (typeof f.index === 'number') {
            allFrameIndices.add(f.index);
          }
        });
      }
    });

    // For each frame, calculate average score across all models
    allFrameIndices.forEach((frameIndex) => {
      const scores = [];
      let isRequestedAdhoc = false;

      // Collect scores from all models for this frame
      Object.values(mlModels).forEach((model) => {
        if (model.frames) {
          const frameData = model.frames.find((f) => f.index === frameIndex);
          if (frameData) {
            if (typeof frameData.score === 'number') {
              scores.push(frameData.score);
            }
            if (frameData.requested_adhoc === true) {
              isRequestedAdhoc = true;
            }
          }
        }
      });

      // Calculate average score
      const avgScore = scores.length > 0
        ? scores.reduce((a, b) => a + b, 0) / scores.length
        : 0;

      // Show frame if average score > 0.5 OR explicitly requested via ad-hoc
      if (avgScore > 0.5 || isRequestedAdhoc) {
        indices.add(frameIndex);
      }
    });

    return Array.from(indices).sort((a, b) => a - b);
  }, [mlModels]);

  if (isLoading) {
    return (
      <div className="p-4">
        <div className="text-center text-gray-600">Loading analysis...</div>
      </div>
    );
  }

  if (error || !analysisData) {
    return (
      <div className="p-4">
        <div className="text-center text-red-600">Failed to load analysis: {error}</div>
      </div>
    );
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
        metadata={metadata}
        analysisId={analysisId}
        onTraditionalResultsUpdate={handleTraditionalResultsUpdate}
        onMLResultsUpdate={handleMLResultsUpdate}
      />
    </div>
  );
}
