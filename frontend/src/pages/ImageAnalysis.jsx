import React, { useState, useEffect, useRef } from "react";
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

  const hasRun = useRef(false);

  useEffect(() => {
    // Prevent double execution in React StrictMode
    if (hasRun.current) return;
    hasRun.current = true;

    const loadOrRunAnalysis = async () => {
      try {
        setIsLoading(true);
        setImageUrl(`http://localhost:5050/api/analyses/${id}/image`);

        // Always fetch existing analysis first (like FrameViewer)
        const existingResponse = await fetch(`http://localhost:5050/api/analyses/${id}`, {
          credentials: 'include'
        });

        if (existingResponse.ok) {
          const analysisData = await existingResponse.json();

          // If analysis is complete and has results, display them
          if (analysisData.status === 'succeeded' && analysisData.result) {
            setResults(analysisData.result);
            setIsLoading(false);
            return;
          }

          // If analysis exists but not complete, show error (shouldn't run from here)
          if (analysisData.status === 'created' || analysisData.status === 'running') {
            setError("This analysis is not yet complete. Please start it from the upload page.");
            setIsLoading(false);
            return;
          }

          // If failed
          if (analysisData.status === 'failed') {
            setError(`Analysis failed: ${analysisData.error || 'Unknown error'}`);
            setIsLoading(false);
            return;
          }
        } else {
          // Log the actual error for debugging
          console.error(`GET /api/analyses/${id} returned ${existingResponse.status}`);
          const errorText = await existingResponse.text();
          console.error('Error response:', errorText);
        }

        // If we get here, analysis doesn't exist or fetch failed
        setError(`Analysis not found (status: ${existingResponse.status})`);
        setIsLoading(false);
      } catch (err) {
        console.error("Failed to load analysis:", err);
        setError(err.message || "Failed to load analysis");
        setIsLoading(false);
      }
    };

    loadOrRunAnalysis();
  }, [id]); // Remove selectedModules dependency

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
  const mlError = mlResults.error;

  // Extract traditional forensics results
  const traditionalResults = results?.traditional || {};
  const hasTraditionalResults = Object.keys(traditionalResults).length > 0;

  // Calculate overall ML score (average across models)
  const calculateOverallMLScore = () => {
    if (!mlResults || typeof mlResults !== 'object') return null;

    // Image analysis returns flat structure: {xception: {score: 0.87}, ...}
    const scores = Object.values(mlResults)
      .map(model => model?.score)
      .filter(score => typeof score === 'number');

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
                      {activeOverlay && traditionalResults[activeOverlay]?.overlay_url && (
                        <img
                          src={`http://localhost:5050${traditionalResults[activeOverlay].overlay_url}`}
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
                          <h4 className="font-semibold text-red-600 text-sm uppercase">
                            {category.replace(/_/g, ' ')}
                          </h4>
                          <ul className="list-disc list-inside text-sm text-gray-700">
                            {anomalies.map((anomaly, idx) => {
                              // Anomalies are objects: {type, fields, note}
                              if (typeof anomaly === 'string') {
                                return <li key={idx}>{anomaly}</li>;
                              }
                              return (
                                <li key={idx}>
                                  {anomaly.note}
                                  {anomaly.fields && ` (${anomaly.fields.join(', ')})`}
                                </li>
                              );
                            })}
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
                    {mlError ? (
                      <div className="p-3 bg-yellow-50 border-l-4 border-yellow-500 rounded">
                        <p className="text-sm text-yellow-800">{mlError}</p>
                      </div>
                    ) : (
                      <>
                        {overallMLScore !== null && (
                          <div className="mb-3 p-3 bg-blue-50 rounded">
                            <div className="text-sm text-gray-600">Overall Score</div>
                            <div className="text-2xl font-bold text-blue-700">{overallMLScore}%</div>
                          </div>
                        )}
                        <div className="space-y-2">
                          {Object.entries(mlResults).map(([modelName, modelData]) => {
                            // Image analysis returns flat structure: {score: 0.87}
                            if (!modelData || typeof modelData.score !== 'number') return null;
                            return (
                              <div key={modelName} className="flex items-center justify-between text-sm border-b pb-2">
                                <span className="font-medium">{modelName.toUpperCase()}</span>
                                <span className="font-bold text-blue-600">
                                  {Math.round(modelData.score * 100)}%
                                </span>
                              </div>
                            );
                          })}
                        </div>
                      </>
                    )}
                  </section>
                )}

                {/* Traditional Forensics */}
                {hasTraditionalResults && (
                  <section>
                    <h3 className="text-lg font-semibold text-gray-900 mb-2">Traditional Forensics</h3>
                    <div className="space-y-3">
                      {Object.entries(traditionalResults).map(([method, methodData]) => {
                        // Image analysis returns flat structure with score directly on methodData
                        if (!methodData || typeof methodData.score !== 'number') return null;

                        const score = methodData.score;
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
