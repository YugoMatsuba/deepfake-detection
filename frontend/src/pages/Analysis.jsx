import React, { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useAnalysis } from "../app/AnalysisProvider";
import { startAnalysis } from "../api/videos";
import {
  MetadataAnomaliesSummary,
  IntegrityStatus,
  FrameHashesSummary
} from "./MetadataResults";

const baseButton = "justify-center items-center mt-[15px] text-[17px] font-semibold px-10 py-3.5 rounded-lg shadow";

export default function Analysis() {
  const navigate = useNavigate();
  const {
    analysisId,
    selectedModules,
    analysisResult,
    setAnalysisResult
  } = useAnalysis();
  const [status, setStatus] = useState('running'); // Start directly in running state
  const [fakeVideoPercentage, setFakeVideoPercentage] = useState(null);
  const [ela, setEla] = useState(null);
  const [noise, setNoise] = useState(null);
  const [lbp, setLbp] = useState(null);
  const [error, setError] = useState(null);
  const hasRun = useRef(false);

  useEffect(() => {
    if (!analysisId) {
      navigate('/upload');
      return;
    }

    // Auto-start analysis once
    if (!hasRun.current) {
      hasRun.current = true;
      handleStartAnalysis();
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

      // Calculates traditional forensics scores
      const tradResults = response?.traditional || {};

      const elaScore = tradResults?.ela?.score ?? null;
      const lbpScore = tradResults?.lbp?.score ?? null;
      const noiseConfidence = tradResults?.noise?.confidence ?? null;

      // Only update states if the module was actually selected
      if (selectedModules.traditional.includes("ela") && typeof elaScore === "number") {
        setEla(elaScore.toFixed(2));
      } else {
        setEla(null);
      }

      if (selectedModules.traditional.includes("noise") && typeof noiseConfidence === "number") {
        setNoise(noiseConfidence.toFixed(2));
      } else {
        setNoise(null);
      }

      if (selectedModules.traditional.includes("lbp") && typeof lbpScore === "number") {
        setLbp(lbpScore.toFixed(2));
      } else {
        setLbp(null);
      }

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

  // Success - show results
  return (
    <div className="flex font-inter font-bold flex-col items-center pt-8 mt-[100px]">
      <h1 className="mt-[40px] text-4xl text-[#0D47A1] text-center">
        Initial Analysis: Synthetic Media Chance = {fakeVideoPercentage}%
      </h1>
      {ela !== null && (
        <h1 className="mt-[40px] text-4xl text-[#0D47A1] text-center">
          ELA Analysis Score = {ela}
        </h1>
      )}

      {noise !== null && (
        <h1 className="mt-[40px] text-4xl text-[#0D47A1] text-center">
          Noise Analysis Confidence = {noise}
        </h1>
      )}

      {lbp !== null && (
        <h1 className="mt-[40px] text-4xl text-[#0D47A1] text-center">
          LBP Analysis Score = {lbp}
        </h1>
      )}

      {/* Metadata Forensics Results */}
      {analysisResult?.metadata && (
        <div className="mt-[40px] w-full max-w-4xl px-4">
          <h2 className="text-3xl font-bold text-[#0D47A1] mb-4 text-center">
            Metadata Forensics
          </h2>

          {/* Anomalies Summary */}
          <MetadataAnomaliesSummary metadata={analysisResult.metadata} />

          {/* Integrity Status */}
          <IntegrityStatus metadata={analysisResult.metadata} />

          {/* Frame Hashes Summary */}
          <FrameHashesSummary metadata={analysisResult.metadata} />
        </div>
      )}

      <h3 className="mt-[100px] text-4xl">
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
