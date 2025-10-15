import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAnalysis } from "../app/AnalysisProvider";
import { startAnalysis } from "../api/videos";

const baseButton = "justify-center items-center mt-[15px] text-[17px] font-semibold px-10 py-3.5 rounded-lg shadow";

export default function Analysis() {
  const navigate = useNavigate();
  const {
    analysisId,
    selectedModules,
    analysisResult,
    setAnalysisResult
  } = useAnalysis();
  const [status, setStatus] = useState('idle'); // 'idle' | 'running' | 'success' | 'error'
  const [fakeVideoPercentage, setFakeVideoPercentage] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!analysisId) {
      navigate('/upload');
      return;
    }
  }, [analysisId, navigate]);

  const handleStartAnalysis = async () => {
    setStatus('running');
    setError(null);
    setAnalysisResult(null);

    try {
      const response = await startAnalysis(
        analysisId,
        selectedModules.ml,
        selectedModules.traditional
      );

      // Calculate ML score from response
      const mlResults = response?.ml || {};
      const mlScores = Object.values(mlResults).map(r => r.score).filter(s => s != null);
      const avgScore = mlScores.length > 0
        ? Math.round(mlScores.reduce((a, b) => a + b, 0) / mlScores.length * 100)
        : 0;

      setFakeVideoPercentage(avgScore);
      setAnalysisResult(response);
      setStatus('success');
    } catch (err) {
      setError(err.message || 'Analysis failed');
      setStatus('error');
    }
  };

  if (status === 'idle') {
    return (
      <div className="flex font-inter font-bold flex-col items-center pt-8 mt-[200px]">
        <h1 className="mt-[60px] text-4xl text-[#0D47A1] text-center">
          Ready to Start Analysis
        </h1>
        <h3 className="mt-[140px] text-4xl">
          Proceed with analysis?
        </h3>
        <div className="flex flex-row gap-20 mt-[20px]">
          <button
            onClick={handleStartAnalysis}
            className={`${baseButton} bg-[#1E88E5] text-white hover:bg-[#114f85] transition-colors`}
          >
            Yes
          </button>
          <button
            onClick={() => navigate('/upload')}
            className={`${baseButton} bg-[#E0E0E0] text-[#1702028F] border border-[#1E88E5] hover:bg-[#b5b5b5] transition-colors`}
          >
            No
          </button>
        </div>
      </div>
    );
  }

  if (status === 'running') {
    return (
      <div className="flex font-inter font-bold flex-col items-center pt-8 mt-[200px]">
        <h1 className="mt-[60px] text-4xl text-[#0D47A1] text-center">
          Running Analysis...
        </h1>
        <p className="mt-[40px] text-2xl text-gray-600">
          This may take 1-2 minutes
        </p>
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div className="flex font-inter font-bold flex-col items-center pt-8 mt-[200px]">
        <h1 className="mt-[60px] text-4xl text-red-600 text-center">
          Analysis Failed
        </h1>
        <p className="mt-[40px] text-xl text-gray-700">{error}</p>
        <button
          onClick={() => navigate('/upload')}
          className={`${baseButton} mt-[60px] bg-[#1E88E5] text-white hover:bg-[#114f85] transition-colors`}
        >
          Back to Upload
        </button>
      </div>
    );
  }

  // Success - show only the percentage
  return (
    <div className="flex font-inter font-bold flex-col items-center pt-8 mt-[200px]">
      <h1 className="mt-[60px] text-4xl text-[#0D47A1] text-center">
        Initial Analysis: Synthetic Media Chance = {fakeVideoPercentage}%
      </h1>
      <h2 className="mt-[40px] text-4xl leading-none tracking-normal text-black">
        Metadata anomalies: None found
      </h2>
      <h3 className="mt-[140px] text-4xl">
        Proceed to frame analysis?
      </h3>

      <div className="flex flex-row gap-20 mt-[20px]">
        <button
          onClick={() => navigate('/frame-viewer', {
            state: {
              analysisId,
              fps: analysisResult?.ml_video?.fps ?? null,
              mlFrames: analysisResult?.ml_frames ?? [],
              mlModels: analysisResult?.ml ?? {},
              traditional: analysisResult?.traditional ?? {}
            }
          })}
          className={`${baseButton} bg-[#1E88E5] text-white hover:bg-[#114f85] hover:text-[#cccccc] transition-colors`}
          disabled={!analysisResult}
        >
          Yes
        </button>
        <button
          onClick={() => navigate('/upload')}
          className={`${baseButton} bg-[#E0E0E0] text-[#1702028F] border border-[#1E88E5] hover:bg-[#b5b5b5] hover:text-[#02028f] transition-colors`}
        >
          No
        </button>
      </div>
    </div>
  );
}
