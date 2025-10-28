import React, { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Card, CardContent } from "./Card";
import { Button } from "./Button";
import { startImageAnalysis } from "../api/videos";
import { useAnalysis } from "../app/AnalysisProvider";

const ImageAnalysis = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { selectedModules } = useAnalysis();

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [results, setResults] = useState(null);
  const [activeOverlay, setActiveOverlay] = useState(null); // 'ela', 'noise', 'lbp', or null
  const [imageUrl, setImageUrl] = useState(null);
  const [showExifDetails, setShowExifDetails] = useState(false);

  useEffect(() => {
    const runAnalysis = async () => {
      if (!selectedModules || (!selectedModules.ml.length && !selectedModules.traditional.length)) {
        setError("No analysis methods selected");
        setIsLoading(false);
        return;
      }

      try {
        setIsLoading(true);
        const response = await startImageAnalysis(
          id,
          selectedModules.ml,
          selectedModules.traditional
        );
        setResults(response);
        setImageUrl(`http://localhost:5050/analyses/${id}/image`);
      } catch (err) {
        console.error("Image analysis failed:", err);
        setError(err.message || "Analysis failed");
      } finally {
        setIsLoading(false);
      }
    };

    runAnalysis();
  }, [id, selectedModules]);

  const handleFinish = () => {
    navigate("/upload");
  };

  const toggleOverlay = (method) => {
    setActiveOverlay(activeOverlay === method ? null : method);
  };

  // Extract EXIF anomalies
  const exifAnomalies = results?.exif?.metadata?.anomalies || {};
  const hasAnomalies = Object.values(exifAnomalies).some(arr => arr && arr.length > 0);

  // Extract ML results
  const mlResults = results?.ml || {};
  const hasMlResults = Object.keys(mlResults).length > 0;

  // Extract traditional forensics results
  const traditionalResults = results?.traditional || {};
  const hasTraditionalResults = Object.keys(traditionalResults).length > 0;

  // Calculate overall ML score (average across models)
  const calculateOverallMLScore = () => {
    const scores = Object.values(mlResults).map(model => {
      const frameData = model.frames?.find(f => f.index === 0);
      return frameData?.score;
    }).filter(score => typeof score === 'number');

    if (scores.length === 0) return null;
    const avg = scores.reduce((sum, score) => sum + score, 0) / scores.length;
    return Math.round(avg * 100);
  };

  const overallMLScore = calculateOverallMLScore();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="text-center">
          <div className="text-xl font-semibold text-gray-700 mb-2">Analyzing image...</div>
          <div className="text-sm text-gray-500">This may take a moment</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <Card className="max-w-md p-6">
          <CardContent>
            <h2 className="text-xl font-bold text-red-600 mb-2">Analysis Error</h2>
            <p className="text-gray-700">{error}</p>
            <Button onClick={() => navigate("/upload")} className="mt-4">
              Back to Upload
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      {/* Finish Button - Top Right */}
      <button
        onClick={handleFinish}
        className="fixed top-4 right-4 z-50 px-4 py-2 rounded-lg bg-blue-600 text-white font-semibold hover:bg-blue-700 transition shadow-lg"
      >
        Finish
      </button>

      <div className="max-w-7xl mx-auto">
        <h1 className="text-3xl font-bold text-gray-900 mb-6 text-center">Image Analysis</h1>

        <div className="flex gap-6">
          {/* Left Panel - Image Display (60%) */}
          <div className="flex-[6]">
            <Card className="p-4">
              <CardContent>
                <div className="relative">
                  {imageUrl && (
                    <>
                      <img
                        src={imageUrl}
                        alt="Analyzed image"
                        className="w-full rounded-lg"
                      />
                      {activeOverlay && (
                        <img
                          src={`http://localhost:5050/analyses/${id}/forensics/${activeOverlay}/frames/0/overlay`}
                          alt={`${activeOverlay.toUpperCase()} overlay`}
                          className="absolute top-0 left-0 w-full h-full object-cover opacity-100 rounded-lg pointer-events-none"
                        />
                      )}
                    </>
                  )}
                </div>

                {/* Overlay Toggle Buttons */}
                {hasTraditionalResults && (
                  <div className="mt-4 flex gap-2 justify-center">
                    {Object.keys(traditionalResults).map((method) => (
                      <Button
                        key={method}
                        size="sm"
                        variant={activeOverlay === method ? "default" : "secondary"}
                        onClick={() => toggleOverlay(method)}
                      >
                        {method.toUpperCase()}
                      </Button>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Right Panel - Results (40%) */}
          <div className="flex-[4]">
            <Card className="p-4">
              <CardContent className="space-y-6">
                <h2 className="text-xl font-bold text-gray-900">Analysis Results</h2>

                {/* EXIF Anomalies - Top Priority */}
                {hasAnomalies && (
                  <section className="border-l-4 border-red-500 pl-4 bg-red-50 p-3 rounded">
                    <h3 className="text-lg font-semibold text-red-700 mb-2">
                      EXIF Anomalies Detected
                    </h3>
                    {Object.entries(exifAnomalies).map(([category, anomalies]) => {
                      if (!anomalies || anomalies.length === 0) return null;
                      return (
                        <div key={category} className="mb-2">
                          <h4 className="font-semibold text-red-600 text-sm uppercase">{category}</h4>
                          <ul className="list-disc list-inside text-sm text-gray-700">
                            {anomalies.map((anomaly, idx) => (
                              <li key={idx}>{anomaly}</li>
                            ))}
                          </ul>
                        </div>
                      );
                    })}
                  </section>
                )}

                {/* ML Detection */}
                {hasMlResults && (
                  <section>
                    <h3 className="text-lg font-semibold text-gray-900 mb-2">ML Detection</h3>
                    {overallMLScore !== null && (
                      <div className="mb-3 p-3 bg-blue-50 rounded">
                        <div className="text-sm text-gray-600">Overall Score</div>
                        <div className="text-2xl font-bold text-blue-700">{overallMLScore}%</div>
                      </div>
                    )}
                    <div className="space-y-2">
                      {Object.entries(mlResults).map(([modelName, modelData]) => {
                        const frameData = modelData.frames?.find(f => f.index === 0);
                        if (!frameData || typeof frameData.score !== 'number') return null;
                        return (
                          <div key={modelName} className="flex items-center justify-between text-sm border-b pb-2">
                            <span className="font-medium">{modelName.toUpperCase()}</span>
                            <span className="font-bold text-blue-600">
                              {Math.round(frameData.score * 100)}%
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </section>
                )}

                {/* Traditional Forensics */}
                {hasTraditionalResults && (
                  <section>
                    <h3 className="text-lg font-semibold text-gray-900 mb-2">Traditional Forensics</h3>
                    <div className="space-y-3">
                      {Object.entries(traditionalResults).map(([method, methodData]) => {
                        const frameData = methodData.frames?.find(f => f.frame_number === 0);
                        if (!frameData || typeof frameData.score !== 'number') return null;

                        const score = frameData.score;
                        const barWidth = Math.min(100, Math.max(0, ((score + 3) / 6) * 100));

                        return (
                          <div
                            key={method}
                            className={`p-3 rounded cursor-pointer transition ${
                              activeOverlay === method ? 'bg-blue-100 border-2 border-blue-500' : 'bg-gray-50 hover:bg-gray-100'
                            }`}
                            onClick={() => toggleOverlay(method)}
                          >
                            <div className="flex items-center justify-between mb-2">
                              <h4 className="font-semibold text-gray-900">{method.toUpperCase()}</h4>
                              <span className="text-sm text-gray-600">z: {score.toFixed(2)}</span>
                            </div>
                            <div className="h-2 w-full bg-gray-200 rounded-full overflow-hidden">
                              <div className="h-full bg-gray-700" style={{ width: `${barWidth}%` }} />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </section>
                )}

                {/* EXIF Metadata Details */}
                {results?.exif?.metadata?.raw && (
                  <section>
                    <button
                      onClick={() => setShowExifDetails(!showExifDetails)}
                      className="flex items-center justify-between w-full text-left"
                    >
                      <h3 className="text-lg font-semibold text-gray-900">EXIF Metadata</h3>
                      <span className="text-gray-500">{showExifDetails ? '▼' : '▶'}</span>
                    </button>

                    {showExifDetails && (
                      <div className="mt-2 max-h-96 overflow-y-auto bg-gray-50 p-3 rounded text-xs font-mono">
                        {Object.entries(results.exif.metadata.raw).map(([key, value]) => (
                          <div key={key} className="mb-1">
                            <span className="text-gray-600">{key}:</span>{' '}
                            <span className="text-gray-900">{JSON.stringify(value)}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </section>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ImageAnalysis;
