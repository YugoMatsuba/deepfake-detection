import React, { useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import FrameViewer from './FrameViewer';

export default function FrameViewerPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const { analysisId, fps } = location.state || {};

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
      />
    </div>
  );
}
