import React, { useRef, useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "./Button";
import { Card, CardContent } from "./Card";
import {
  MetadataAnomaliesSummary,
  IntegrityStatus,
  FrameHashesSummary
} from "./MetadataResults";
import Toast from "../components/Toast";
import InfoButton from "../components/InfoButton";
import { forensicsInfo } from "../utils/ForensicsInfo";

const FrameViewer = ({
  videoSrc,
  initialFrameRate = null,
  deepfakeFrames = [],
  deepfakeMeta = {},
  traditionalResults = {},
  metadata = null,
  analysisId,
  onTraditionalResultsUpdate = () => {},
  onMLResultsUpdate = () => {},
}) => {

  const videoRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentFrame, setCurrentFrame] = useState(0);
  const [frameRate, setFrameRate] = useState(initialFrameRate);
  const [deepfakeIndex, setDeepfakeIndex] = useState(0);
  const [duration, setDuration] = useState(0);
  const [durationFrames, setDurationFrames] = useState(0);
  const [analysisResult, setAnalysisResult] = useState(null);
  const[isAnalysing, setIsAnalysing] = useState(false);
  const [currentAnalysisType, setCurrentAnalysisType] = useState(null);
  const [overlayResult, setOverlayResult] = useState(null);
  const [selectedAnalysis, setSelectedAnalysis] = useState(null); 
  const [analysisPopupOpen, setAnalysisPopupOpen] = useState(false);
  const [videoUrl, setVideoUrl] = useState(null);
  const [isVideoLoading, setIsVideoLoading] = useState(true);
  const [videoError, setVideoError] = useState(null);
  const [traditionalData, setTraditionalData] = useState(traditionalResults || {});
  const [mlData, setMLData] = useState(deepfakeMeta || {});
  const [mlFrames, setMLFrames] = useState(deepfakeFrames || []);
  const [markerType, setMarkerType] = useState("ml");
  const [isTooltipHovered, setIsTooltipHovered] = useState(false);
  const [toastMessage, setToastMessage] = useState(null);
  const [toastType, setToastType] = useState('error'); 
  const [selectedMarkerType, setSelectedMarkerType] = useState(null);
  const [showAllMarkers, setShowAllMarkers] = useState(false);

  // Finish Analysis state
  const [showFinishPopup, setShowFinishPopup] = useState(false);
  const [downloadingPDF, setDownloadingPDF] = useState(false);
  const [cleaning, setCleaning] = useState(false);

  // Stats info popup state
  const [showStatsPopup, setShowStatsPopup] = useState(false);

  const navigate = useNavigate();




  // Tracks which marker is hovered
  const [hoveredIndex, setHoveredIndex] = useState(null);

  // Timer used to delay hiding the tooltip
  const hideTimerRef = useRef(null);

  // Side panel state
  const [isDetailsOpen, setIsDetailsOpen] = useState(false);
  const [detailsFrame, setDetailsFrame] = useState(null);

  // ============================================
  // ========== FRAME ANALYSIS DETAILS ==========

  // Get meta for a frame (safe)
  const getMeta = (frame) => (frame != null ? mlData?.[frame] || null : null);

useEffect(() => {
  if (initialFrameRate) {
    setFrameRate(initialFrameRate);
  }
}, [initialFrameRate]);

  // Sync props to state when they change (important for page reloads)
  useEffect(() => {
    setTraditionalData(traditionalResults || {});
  }, [traditionalResults]);

  useEffect(() => {
    setMLData(deepfakeMeta || {});
  }, [deepfakeMeta]);

  useEffect(() => {
    setMLFrames(deepfakeFrames || []);
  }, [deepfakeFrames]);

  useEffect(() => {
    let abort = false;
    let objectUrl = null;
    let hasRetried = false;

    async function loadVideo() {
      if (!videoSrc) {
        setVideoUrl(null);
        setIsVideoLoading(false);
        return;
      }

      setIsVideoLoading(true);
      setVideoError(null);
      setVideoUrl(null);

      try {
        const response = await fetch(videoSrc, { credentials: 'include' });
        if (!response.ok) {
          throw new Error(`Failed to load video (status ${response.status})`);
        }
        const blob = await response.blob();
        if (abort) {
          return;
        }
        objectUrl = URL.createObjectURL(blob);
        setVideoUrl(objectUrl);
        setIsVideoLoading(false);
      } catch (err) {
        if (!abort) {
          console.error("Error fetching video:", err);

          // Retry once if this is the first failure
          if (!hasRetried) {
            console.log("Retrying video load once...");
            hasRetried = true;
            // Wait a bit before retrying
            setTimeout(() => {
              if (!abort) {
                loadVideo();
              }
            }, 500);
            return;
          }

          // If retry also failed, show error
          setVideoError(err.message || "Failed to load video");
          setVideoUrl(null);
          setIsVideoLoading(false);
        }
      }
    }

    loadVideo();

    return () => {
      abort = true;
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [videoSrc]);


  // Average anomaly score across frames that have a score
  const getAverageAnomaly = () => {
    const entries = Object.values(mlData || {}).filter(
      (m) => typeof m?.anomalyScore === "number"
    );
    if (!entries.length) return null;
    const sum = entries.reduce((acc, m) => acc + m.anomalyScore, 0);
    return sum / entries.length; // 0..1
  };

  // Extract “details” for the currently selected frame
 const details = (() => {
  const meta = getMeta(detailsFrame); // ML meta
  const methods = ["ela", "noise", "lbp"].reduce((acc, type) => {
    const frames = traditionalData?.[type]?.frames || [];
    const frameData = frames.find(f => (f.frame_number ?? f.frame) === detailsFrame);
    acc[type] = frameData?.score ?? frameData?.confidence ?? null;
    return acc;
  }, {});

  return {
    anomalyScore: typeof meta?.anomalyScore === "number" ? meta.anomalyScore : null,
    methods,
    temporalLabels: Array.isArray(meta?.temporalLabels) ? meta.temporalLabels : [],
  };
})();



  // ============================================


  const clearHideTimer = () => {
    if (hideTimerRef.current) {
      clearTimeout(hideTimerRef.current);
      hideTimerRef.current = null;
    }
  };

  const hideTooltip = () => {
  clearHideTimer();
  setHoveredIndex(null);

};


  useEffect(() => {
    return () => clearHideTimer();
  }, []);

  useEffect(() => {
    if (!videoUrl) {
      setIsPlaying(false);
      setCurrentFrame(0);
      setCurrentTime(0);
    }
  }, [videoUrl]);

  const togglePlay = () => {
    const video = videoRef.current;
    if (!video) return;
    if (isPlaying) {
      video.pause();
    } else {
      video.play();
    }
    setIsPlaying(!isPlaying);
  };

  const nextFrame = () => {
     if (!frameRate) return;
    const video = videoRef.current;
    if (!video) return;
    video.currentTime = Math.min(video.currentTime + 1 / frameRate, video.duration);
    setCurrentFrame(Math.round(video.currentTime * frameRate));
    setOverlayResult(null); // Clear overlay when navigating frames
  };

  const prevFrame = () => {
    const video = videoRef.current;
    if (!video) return;
    video.currentTime = Math.max(video.currentTime - 1 / frameRate, 0);
    setCurrentFrame(Math.round(video.currentTime * frameRate));
    setOverlayResult(null); // Clear overlay when navigating frames
  };

  const jumpToNextMarker = (type) => {
  if (!frameRate || !videoRef.current) return;

  let frames = [];

  // If showing all markers, combine frames from all types
  if (showAllMarkers) {
    // Add ML frames
    frames = [...mlFrames];

    // Add traditional forensics frames (only flagged)
    ["ela", "noise", "lbp"].forEach(t => {
      const tFrames = (traditionalData?.[t]?.frames || [])
        .filter(f => f.flagged)  // Only show flagged frames
        .map(f => f.frame_number ?? f.frame)
        .filter(n => typeof n === "number");
      frames.push(...tFrames);
    });
  } else {
    // Single type
    if (type === "ml") {
      frames = mlFrames;
    } else {
      frames = (traditionalData?.[type]?.frames || [])
        .filter(f => f.flagged)  // Only show flagged frames
        .map(f => f.frame_number ?? f.frame)
        .filter(n => typeof n === "number");
    }
  }

  if (frames.length === 0) return;

  frames.sort((a, b) => a - b);
  const next = frames.find(f => f > currentFrame);
  if (typeof next === "number") {
    const video = videoRef.current;
    video.currentTime = next / frameRate;
    setCurrentFrame(next);
    setOverlayResult(null); // Clear overlay when jumping to marker
  }
};

const jumpToPreviousMarker = (type) => {
  if (!frameRate || !videoRef.current) return;

  let frames = [];

  // If showing all markers, combine frames from all types
  if (showAllMarkers) {
    // Add ML frames
    frames = [...mlFrames];

    // Add traditional forensics frames (only flagged)
    ["ela", "noise", "lbp"].forEach(t => {
      const tFrames = (traditionalData?.[t]?.frames || [])
        .filter(f => f.flagged)  // Only show flagged frames
        .map(f => f.frame_number ?? f.frame)
        .filter(n => typeof n === "number");
      frames.push(...tFrames);
    });
  } else {
    // Single type
    if (type === "ml") {
      frames = mlFrames;
    } else {
      frames = (traditionalData?.[type]?.frames || [])
        .filter(f => f.flagged)  // Only show flagged frames
        .map(f => f.frame_number ?? f.frame)
        .filter(n => typeof n === "number");
    }
  }

  if (frames.length === 0) return;

  frames.sort((a, b) => a - b);
  const prev = [...frames].reverse().find(f => f < currentFrame);
  if (typeof prev === "number") {
    const video = videoRef.current;
    video.currentTime = prev / frameRate;
    setCurrentFrame(prev);
    setOverlayResult(null); // Clear overlay when jumping to marker
  }
};

  

  const restartVideo = () => {
    const video = videoRef.current;
    if (!video) return;

    video.currentTime = 0;
    setCurrentFrame(0);
    video.pause();
    setIsPlaying(false);
  };

  const [currentTime, setCurrentTime] = useState(0);

const handleTimeUpdate = () => {
  const video = videoRef.current;
  if (!video) return;
  setCurrentTime(video.currentTime);
  if (frameRate) setCurrentFrame(Math.round(video.currentTime * frameRate));
};
  const handleLoadedMetadata = () => {
  const video = videoRef.current;
  if (!video) return;
  setDuration(video.duration);
};

useEffect(() => {
  if (frameRate && duration) {
    setDurationFrames(Math.floor(duration * frameRate));
  }
}, [frameRate, duration]);

  // Helper: compute left % safely (handles duration === 0)
  const pctLeft = (frame) => {
  if (!durationFrames) return 0;
  return (frame / durationFrames) * 100;
};

  // Tooltip anchor frame
  const hoveredFrame = (() => {
  if (hoveredIndex === null) return null;

  // Use selectedMarkerType (set on hover) instead of markerType (filter button)
  const typeToCheck = selectedMarkerType || markerType;

  if (typeToCheck === "ml") {
    return mlFrames[hoveredIndex] ?? null;
  }

  // For other types (filter to flagged frames to match timeline markers)
  const frames = traditionalData?.[typeToCheck]?.frames?.filter(f => f.flagged) || [];
  if (!frames || hoveredIndex < 0 || hoveredIndex >= frames.length) return null;

  return frames[hoveredIndex].frame_number ?? frames[hoveredIndex].frame;
})();


  // Tooltip text: from deepfakeMeta if available, else a fallback
  const hoveredSummary =
    hoveredFrame != null && mlData && mlData[hoveredFrame]?.summary
      ? mlData[hoveredFrame].summary
      : hoveredFrame != null
      ? `Flagged at frame ${hoveredFrame}`
      : "";

  const mergeFrames = (existing = [], additions = []) => {
    const byKey = new Map();
    [...existing, ...additions].forEach((frame) => {
      if (!frame) {
        return;
      }
      const key =
        typeof frame.frame_number === "number"
          ? `idx_${frame.frame_number}`
          : frame.frame ?? JSON.stringify(frame);
      const existingEntry = byKey.get(key) || {};
      byKey.set(key, { ...existingEntry, ...frame });
    });
    return Array.from(byKey.values()).sort((a, b) => {
      const aNum = typeof a.frame_number === "number" ? a.frame_number : Number.POSITIVE_INFINITY;
      const bNum = typeof b.frame_number === "number" ? b.frame_number : Number.POSITIVE_INFINITY;
      if (aNum !== bNum) {
        return aNum - bNum;
      }
      const aFrame = a.frame ?? "";
      const bFrame = b.frame ?? "";
      return aFrame.localeCompare(bFrame);
    });
  };

  const analyzeFrame = async (analysisType) => {
    if (!analysisId) {
      alert("Analysis ID not found. Please restart the analysis flow.");
      return;
    }

    const video = videoRef.current;
    if (video && !video.paused) {
      video.pause();
      setIsPlaying(false);
    }

    const targetFrame = Number.isFinite(currentFrame) ? currentFrame : 0;

    setIsAnalysing(true);
    setCurrentAnalysisType(analysisType);
    setAnalysisResult(null);

    try {
      // Handle ML analysis differently
      if (analysisType === "ml") {
        const response = await fetch(
          `http://localhost:5050/api/analyses/${analysisId}/frames/${targetFrame}/ml`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({ models: ["xception", "spsl", "ucf"] }),
          }
        );

        const result = await response.json();

        if (!response.ok) {
          throw new Error(result.error || "ML analysis failed");
        }

        // Process ML results: {xception: {score, index, time}, spsl: {...}, ucf: {...}}
        const results = result.results || {};
        const frameNumber = result.frame_number;
        const frameTime = result.time;

        // Update each model's data
        const updatedMLData = { ...mlData };

        for (const [modelName, modelResult] of Object.entries(results)) {
          const existingModel = updatedMLData[modelName] || { frames: [], score: null };

          // Create new frame entry
          const newFrameEntry = {
            index: frameNumber,
            time: frameTime,
            score: modelResult.score
          };

          // Merge with existing frames (avoid duplicates)
          const existingFrames = existingModel.frames || [];
          const frameIndex = existingFrames.findIndex(f => f.index === frameNumber);

          let updatedFrames;
          if (frameIndex >= 0) {
            // Update existing frame
            updatedFrames = [...existingFrames];
            updatedFrames[frameIndex] = { ...updatedFrames[frameIndex], ...newFrameEntry };
          } else {
            // Add new frame
            updatedFrames = [...existingFrames, newFrameEntry];
          }

          updatedMLData[modelName] = {
            ...existingModel,
            frames: updatedFrames
          };
        }

        setMLData(updatedMLData);
        onMLResultsUpdate(updatedMLData, frameNumber);

        // Fetch fresh data from DB to ensure consistency and persistence
        try {
          const freshResponse = await fetch(`http://localhost:5050/api/analyses/${analysisId}`, {
            credentials: "include"
          });
          if (freshResponse.ok) {
            const freshData = await freshResponse.json();
            const freshML = freshData.result?.ml || {};
            const freshMLFrames = [];

            // Extract frame indices that should be displayed:
            // Calculate average score across all models for each frame (like backend does)
            // Show if: (average score > 0.5) OR (requested_adhoc === true)

            // First, collect all unique frame indices
            const allFrameIndices = new Set();
            Object.values(freshML).forEach(modelData => {
              if (modelData.frames) {
                modelData.frames.forEach(f => {
                  if (typeof f.index === 'number') {
                    allFrameIndices.add(f.index);
                  }
                });
              }
            });

            // For each frame, calculate average score across all models
            allFrameIndices.forEach(frameIndex => {
              const scores = [];
              let isRequestedAdhoc = false;

              // Collect scores from all models for this frame
              Object.values(freshML).forEach(modelData => {
                if (modelData.frames) {
                  const frameData = modelData.frames.find(f => f.index === frameIndex);
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
                freshMLFrames.push(frameIndex);
              }
            });

            setMLData(freshML);
            setMLFrames(freshMLFrames.sort((a, b) => a - b));
            console.log("Synced ML data from DB:", freshML);
          }
        } catch (dbError) {
          console.error("Failed to fetch fresh ML data from DB:", dbError);
          // Continue with local state if DB fetch fails
          // Add frame to mlFrames array if not already present
          if (!mlFrames.includes(frameNumber)) {
            const updatedFrames = [...mlFrames, frameNumber].sort((a, b) => a - b);
            setMLFrames(updatedFrames);
          }
        }

        // Calculate average score from all models for popup
        const modelScores = Object.values(results)
          .map(r => r.score)
          .filter(s => typeof s === 'number');

        const avgScore = modelScores.length > 0
          ? modelScores.reduce((a, b) => a + b, 0) / modelScores.length
          : null;

        // Show popup with average ML score
        setAnalysisResult({
          analysis_type: "ml",
          frame_number: frameNumber,
          score: avgScore
        });

        setIsAnalysing(false);
        setCurrentAnalysisType(null);
        return;
      }

      // Traditional forensics analysis (existing code)
      console.log("1. Starting traditional forensics request for", analysisType, "frame", targetFrame);

      const response = await fetch(
        `http://localhost:5050/api/analyses/${analysisId}/frames/${targetFrame}/forensics`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ methods: [analysisType] }),
        }
      );

      console.log("2. Got forensics response, status:", response.status);
      const result = await response.json();
      console.log("3. Forensics result:", result);

      if (!response.ok) {
        throw new Error(result.error || "Analysis failed");
      }

      const methodResult = result?.results?.[analysisType];
      console.log("4. Method result:", methodResult);

      if (!methodResult) {
        throw new Error("Backend returned no data for the requested analysis.");
      }

      // Fetch fresh data from DB to ensure consistency and persistence
      console.log("5. Fetching fresh data from DB...");
      const freshResponse = await fetch(`http://localhost:5050/api/analyses/${analysisId}`, {
        credentials: "include"
      });

      console.log("6. Got DB response, status:", freshResponse.status);

      if (!freshResponse.ok) {
        throw new Error("Failed to fetch updated analysis from DB");
      }

      const freshData = await freshResponse.json();
      console.log("7. Fresh DB data:", freshData);

      const freshTraditional = freshData.result?.traditional || {};
      console.log("8. Fresh traditional data:", freshTraditional);

      const freshMethodResult = freshTraditional[analysisType];
      console.log("9. Fresh method result:", freshMethodResult);

      if (!freshMethodResult) {
        throw new Error("Analysis method data missing from DB after update");
      }

      console.log("10. Setting state with fresh traditional data");
      setTraditionalData(freshTraditional);
      onTraditionalResultsUpdate(freshTraditional);
      console.log("11. ✓ Synced traditional data from DB:", freshTraditional);

      // Find the frame we just analyzed (from fresh DB data)
      const analyzedFrame = freshMethodResult.frames?.find(
        (frame) => frame.frame_number === result.frame_number
      );

      // Use overlay_url from disk persistence
      const overlayData = analyzedFrame?.overlay_url ?? null;
      const primaryScore =
        analyzedFrame?.score ??
        analyzedFrame?.confidence ??
        methodResult.score ??
        methodResult.confidence ??
        null;

      setAnalysisResult({
        analysis_type: analysisType,
        frame_number: result.frame_number,
        score: primaryScore,
        confidence: analyzedFrame?.confidence ?? methodResult.confidence ?? null,
        overlay: overlayData,
      });

      setOverlayResult(
        overlayData
          ? { analysis_type: analysisType, overlay: overlayData }
          : null
      );
    } catch (error) {
      console.error("Error analyzing frame:", error);
      setToastMessage(`Error during ${analysisType.toUpperCase()} analysis: ${error.message}`);
      setToastType('error');
    } finally {
      setIsAnalysing(false);
      setCurrentAnalysisType(null);
    }
  };

// Determine color class based on analysis type and value
const getColor = (type, value) => {
  if (type === 'ela') {
    // For ELA: z-score interpretation (higher = more suspicious)
    if (value >= 3.0) return 'text-red-600';
    if (value >= 2.0) return 'text-orange-500';
    if (value >= 1.0) return 'text-yellow-500';
    return 'text-gray-600';
  } else if (type === 'noise') {
    // For Noise: z-score interpretation (higher = more suspicious)
    if (value >= 3.0) return 'text-red-600';
    if (value >= 2.0) return 'text-orange-500';
    if (value >= 1.0) return 'text-yellow-500';
    return 'text-gray-600';
  } else {
    // For LBP: z-score interpretation (higher = more suspicious)
    if (value >= 3.0) return 'text-red-600';
    if (value >= 2.0) return 'text-orange-500';
    if (value >= 1.0) return 'text-yellow-500';
    return 'text-gray-600';
  }
};

// Finish Analysis handlers
const handleDownloadPDF = async () => {
  setDownloadingPDF(true);
  try {
    const response = await fetch(`/api/reports/${analysisId}/pdf`, {
      credentials: "include",
    });

    if (!response.ok) throw new Error("Failed to download PDF");

    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `analysis_report.pdf`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  } catch (err) {
    alert("Failed to download PDF: " + err.message);
  } finally {
    setDownloadingPDF(false);
  }
};

const handleFinishAnalysis = () => {
  setShowFinishPopup(true);
};

const handleRunFullAnalysis = async (method) => {
  if (!analysisId) return;

  // Set loading state
  setIsAnalysing(true);
  setCurrentAnalysisType(method);

  try {
    console.log(`Starting full ${method} analysis...`);

    const response = await fetch(
      `http://localhost:5050/api/analyses/${analysisId}/run-full/${method}`,
      {
        method: "POST",
        credentials: "include"
      }
    );

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || "Full analysis failed");
    }

    const result = await response.json();
    console.log(`Full ${method} analysis completed:`, result);

    // Update state with fresh data
    const freshData = result.result;

    if (method === "ml") {
      setMLData(freshData.ml || {});

      // Extract ML frames - only show if avgScore > 0.5 OR requested_adhoc === true
      const freshMLFrames = [];

      // First, collect all unique frame indices
      const allFrameIndices = new Set();
      Object.values(freshData.ml || {}).forEach(modelData => {
        if (modelData.frames) {
          modelData.frames.forEach(f => {
            if (typeof f.index === 'number') {
              allFrameIndices.add(f.index);
            }
          });
        }
      });

      // For each frame, calculate average score across all models
      allFrameIndices.forEach(frameIndex => {
        const scores = [];
        let isRequestedAdhoc = false;

        // Collect scores from all models for this frame
        Object.values(freshData.ml || {}).forEach(modelData => {
          if (modelData.frames) {
            const frameData = modelData.frames.find(f => f.index === frameIndex);
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
          freshMLFrames.push(frameIndex);
        }
      });

      setMLFrames(freshMLFrames.sort((a, b) => a - b));
    } else {
      setTraditionalData(freshData.traditional || {});
      onTraditionalResultsUpdate(freshData.traditional || {});
    }

    alert(`Full ${method.toUpperCase()} analysis completed successfully!`);

  } catch (error) {
    console.error(`Full ${method} analysis failed:`, error);
    alert(`Failed to run full ${method} analysis: ${error.message}`);
  } finally {
    setIsAnalysing(false);
    setCurrentAnalysisType(null);
  }
};

  // Calculate overall statistics
  const overallStats = useMemo(() => {
    // ML: Calculate average score across all models (use state, not prop)
    const mlScores = Object.values(mlData || {}).map(r => r.score).filter(s => s != null);
    const mlAverage = mlScores.length > 0
      ? Math.round(mlScores.reduce((a, b) => a + b, 0) / mlScores.length * 100)
      : null;

    // ML frame counts (min across all models)
    const mlFrameCounts = Object.values(mlData || {})
      .map(m => m.frames?.length ?? 0)
      .filter(c => c > 0);
    const mlFrameCount = mlFrameCounts.length > 0 ? Math.min(...mlFrameCounts) : 0;

    // Traditional: Get scores (use state, not prop)
    const elaScore = traditionalData?.ela?.score ?? null;
    const noiseConfidence = traditionalData?.noise?.confidence ?? null;
    const lbpScore = traditionalData?.lbp?.score ?? null;

    // Traditional frame counts
    const elaFrameCount = traditionalData?.ela?.frames?.length ?? 0;
    const noiseFrameCount = traditionalData?.noise?.frames?.length ?? 0;
    const lbpFrameCount = traditionalData?.lbp?.frames?.length ?? 0;

    return {
      syntheticMediaChance: mlAverage,
      mlFrameCount,
      showMLButton: mlFrameCount === 0 || mlFrameCount < 10,

      elaScore: elaScore !== null ? elaScore.toFixed(2) : null,
      elaFrameCount,
      showElaButton: elaFrameCount === 0 || elaFrameCount < 10,

      noiseScore: noiseConfidence !== null ? noiseConfidence.toFixed(2) : null,
      noiseFrameCount,
      showNoiseButton: noiseFrameCount === 0 || noiseFrameCount < 10,

      lbpScore: lbpScore !== null ? lbpScore.toFixed(2) : null,
      lbpFrameCount,
      showLBPButton: lbpFrameCount === 0 || lbpFrameCount < 10
    };
  }, [mlData, traditionalData]);


  return (
    <>
    <div className="flex justify-center items-center min-h-screen bg-gray-50 space-x-10">

      {/* Info Button - Bottom Left */}
      <button
        onClick={() => setShowStatsPopup(true)}
        className="fixed bottom-8 left-8 z-50 w-10 h-10 rounded-full bg-blue-600 text-white font-semibold hover:bg-blue-700 transition shadow-lg flex items-center justify-center"
        title="View Overall Statistics"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      </button>

      {/* Finish Analysis Button - Top Right */}
      <button
        onClick={handleFinishAnalysis}
        className="fixed top-4 right-4 z-50 px-4 py-2 rounded-lg bg-blue-600 text-white font-semibold hover:bg-blue-700 transition shadow-lg"
      >
        Finish Analysis
      </button>

      <div className="flex flex-col items-center flex-1 space-y-1 p-3">

      <Card className="w-full max-w-3xl shadow-lg rounded-2xl">
        <CardContent className="flex flex-col items-center space-y-4 p-3">
          <div className="relative w-full max-w-3xl min-h-[360px] flex items-center justify-center">
            <video
              ref={videoRef}
              src={videoUrl || undefined}
              controls={Boolean(videoUrl)}
              width="640"
              height="360"
              preload="metadata"
              onTimeUpdate={handleTimeUpdate}
              onLoadedMetadata={handleLoadedMetadata}
              className="rounded-lg border border-gray-300 bg-black"
            />

            {isVideoLoading && (
              <div className="absolute inset-0 flex items-center justify-center rounded-lg bg-black/40">
                <span className="text-white font-semibold">Loading video…</span>
              </div>
            )}

            {videoError && !isVideoLoading && (
              <div className="absolute inset-0 flex items-center justify-center rounded-lg bg-black/50">
                <span className="text-red-200 font-semibold">{videoError}</span>
              </div>
            )}

            {/* Overlay image for ELA, LBP, or Noise */}
            {(() => {
              let overlaySrc = overlayResult?.overlay;

              // If overlay starts with /, it's a URL path - prepend API base
              if (overlaySrc && overlaySrc.startsWith('/')) {
                overlaySrc = `http://localhost:5050${overlaySrc}`;
              }

              if (!overlaySrc) {
                return null;
              }

              return (
                <img
                  src={overlaySrc}
                  alt={`${overlayResult.analysis_type?.toUpperCase() || "Analysis"} overlay`}
                  className="absolute top-0 left-0 w-full h-full object-cover opacity-100 pointer-events-none rounded-lg"
                />
              );
            })()}
          </div>

          <div className="flex justify-center gap-2 mb-2 flex-wrap">
  <Button
    size="sm"
    variant={showAllMarkers ? "default" : "secondary"}
    onClick={() => setShowAllMarkers(!showAllMarkers)}
  >
    ALL
  </Button>

  {["ml", "ela", "noise", "lbp"].map((type) => (
    <Button
      key={type}
      size="sm"
      variant={!showAllMarkers && markerType === type ? "default" : "secondary"}
      onClick={() => {
        setMarkerType(type);
        setShowAllMarkers(false); // disable show all when a single marker is selected
      }}
    >
      {type.toUpperCase()}
    </Button>
  ))}
</div>


          {/* === TIMELINE BAR === */}
          <div className="relative w-full h-4 bg-gray-200 rounded-lg">
            {/* Current progress */}
            <div
              className="absolute top-0 left-0 h-4 bg-blue-500 rounded-lg"
              style={{ width: `${durationFrames ? (currentFrame / durationFrames) * 100 : 0}%` }}
            />

            
  <div className="flex flex-col items-center mt-4 space-y-2">



  

</div>

{/* Timeline markers */}
{(showAllMarkers ? ["ml", "ela", "noise", "lbp"] : [markerType]).map((type) => {
  if (type === "ml") {
    return mlFrames.map((frame, index) => (
      <div
        key={`df-${index}`}
        className="absolute top-0 h-4 w-1 bg-red-500"
        style={{ left: `${pctLeft(frame)}%` }}
        onMouseEnter={() => {
          setHoveredIndex(index);
          setSelectedMarkerType("ml");
          setDetailsFrame(frame);
        }}
        onMouseLeave={() => { if (!isTooltipHovered) setHoveredIndex(null); }}
        onClick={() => {
          setIsDetailsOpen(true);
          setDetailsFrame(frame);
          setSelectedMarkerType("ml");
        }}
        onDoubleClick={() => {
          if (frameRate && videoRef.current) {
            videoRef.current.currentTime = frame / frameRate;
            setCurrentFrame(frame);
            setOverlayResult(null);
          }
        }}
      />
    ));
  } else {
    return traditionalData?.[type]?.frames?.filter(f => f.flagged).map((frame, idx) => {
      const frameNum = frame.frame_number ?? frame.frame;
      if (frameNum == null) return null;

      return (
        <div
          key={`${type}-${idx}`}
          className="absolute top-0 h-4 w-1 rounded-sm"
          style={{
            left: `${pctLeft(frameNum)}%`,
            backgroundColor:
              type === "ela" ? "#4B0082" :
              type === "noise" ? "#facc15" : "#10b981",
          }}
          onMouseEnter={() => {
            clearHideTimer();
            setHoveredIndex(idx);
            setDetailsFrame(frameNum);
            setSelectedMarkerType(type);
          }}
          onMouseLeave={hideTooltip}
          onClick={() => {
            setIsDetailsOpen(true);
            setDetailsFrame(frameNum);
            setSelectedMarkerType(type);
          }}
          onDoubleClick={() => {
            if (frameRate && videoRef.current) {
              videoRef.current.currentTime = frameNum / frameRate;
              setCurrentFrame(frameNum);
              // Show overlay for traditional forensics (ML has no overlay)
              const overlayData = frame.overlay || frame.overlay_url || null;
              setOverlayResult(
                overlayData
                  ? { analysis_type: type, overlay: overlayData }
                  : null
              );
            }
          }}
        />
      );
    });
  }
})}



  

  
{/* Hover tooltip */}
{hoveredFrame != null && (
  <div
    className="absolute -top-20 z-30"
    style={{
      left: `${pctLeft(hoveredFrame)}%`,
      transform: "translateX(-50%)",
    }}
    onMouseEnter={() => setIsTooltipHovered(true)}
    onMouseLeave={() => {
      setIsTooltipHovered(false);
      setHoveredIndex(null); // hide when mouse leaves the tooltip
    }}
    onClick={() => {
      setIsDetailsOpen(true);
      setDetailsFrame(hoveredFrame);
    }}
    onDoubleClick={() => {
      if (frameRate && videoRef.current) {
        videoRef.current.currentTime = hoveredFrame / frameRate;
        setCurrentFrame(hoveredFrame);
        setOverlayResult(null);
      }
    }}
  >
    <div className="flex flex-col items-center justify-center relative w-64 rounded-xl border border-gray-300 bg-white p-3 shadow-lg cursor-pointer">

      {/* Title: ML, ELA, Noise, or LBP */}
      <h4 className="text-center text-sm font-semibold mb-1">
        {(selectedMarkerType || markerType).toUpperCase()}
      </h4>

      {/* Summary */}
      <p className="text-sm text-gray-800 leading-snug">
        {mlData?.[hoveredFrame]?.summary || `Flagged at frame ${hoveredFrame}`}
      </p>

      {/* Tooltip arrow */}
      <div className="absolute left-1/2 top-full -translate-x-1/2 -mt-2 w-3 h-3 rotate-45 bg-white border-r border-b border-gray-300" />
    </div>
  </div>
)}

</div>

          <div className="flex justify-center gap-12">

            <Button 
  variant="secondary" 
  className="bg-white"
  onClick={() => jumpToPreviousMarker(markerType)}
>
  <span className="text-2xl">&lt;&lt;</span>
</Button>

<Button variant="secondary" size="lg" className="bg-white" onClick={prevFrame}>
              <span className="text-2xl">&lt;</span>
            </Button>
            

            <div className="flex flex-col items-center gap-2">
              <Button variant="default" onClick={() => {
      togglePlay();            // play/pause video
      // optionally clear overlay popup only if you want:
      setOverlayResult(null);
    }}>
                {isPlaying ? "Pause" : "Play"}
              </Button>
              <Button variant="destructive" onClick={restartVideo}>
                Restart
              </Button>
            </div>

            <Button variant="secondary" size="lg" className="bg-white" onClick={nextFrame}>
              <span className="text-2xl">&gt;</span>
            </Button>
            <Button 
  variant="secondary" 
  className="bg-white"
  onClick={() => jumpToNextMarker(markerType)}
>
  <span className="text-2xl">&gt;&gt;</span>
</Button>
            
          </div>

          <div className="text-sm text-gray-700">
            <p>
              <span className="font-medium">Current Frame:</span> {currentFrame}
            </p>
            <p>
                <span className="font-medium">Frame Rate:</span>{" "}
                {frameRate ? frameRate.toFixed(2) : "Loading..."} fps
              </p>
          </div>
        </CardContent>
      </Card>

<Card className="w-full max-w-3xl shadow-lg rounded-2xl">
    <CardContent className="flex justify-center gap-4 p-0">
      {["ml", "ela", "noise", "lbp"].map((method) => (
        <Button
          key={method}
          variant="default"
          size="sm"
          disabled={isAnalysing}
          onClick={() => analyzeFrame(method)}
        >
          {isAnalysing && currentAnalysisType === method ? `Analyzing...` : `${method.toUpperCase()}`}
        </Button>
      ))}
    </CardContent>
  </Card>

</div>
        {/* RIGHT: Details panel */}
        {isDetailsOpen && detailsFrame != null && (
  <Card className="w-[360px] shrink-0 shadow-lg rounded-2xl">
    <CardContent className="p-5 space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-lg font-semibold">Frame Details</h3>
          <p className="text-xs text-gray-500">
            Frame {detailsFrame != null ? detailsFrame : "—"}
          </p>
        </div>
        <Button
          variant="secondary"
          className="bg-white"
          onClick={() => setIsDetailsOpen(false)}
        >
          Close
        </Button>
      </div>

      {/* ML Detection - Always show if data exists */}
{(() => {
  const flaggedFrames = Object.entries(mlData || {}).map(([modelName, modelData]) => {
    const frame = modelData.frames?.find(f => f.index === detailsFrame);
    if (!frame || typeof frame.score !== "number") return null;
    return {
      model: modelName,
      index: frame.index,
      score: frame.score,
      time: frame.time
    };
  }).filter(Boolean);

  if (flaggedFrames.length === 0) return null;  // Hide section if no data

  return (
    <section>
      <h4 className="text-sm font-medium text-gray-700 mb-2">ML Detection Score</h4>
      {flaggedFrames.map(f => (
        <div key={`${f.model}-${f.index}`} className="flex items-center justify-between text-sm mb-1">
          <span>{f.model.toUpperCase()} — {f.time.toFixed(2)}s</span>
          <span className="font-bold text-blue-600">{Math.round(f.score * 100)}%</span>
        </div>
      ))}
    </section>
  );
})()}

{/* Traditional Forensics - Always show all available methods */}
{["ela", "noise", "lbp"].map((type) => {
  const value = details.methods[type];
  if (typeof value !== "number") return null;  // Skip if no data for this method

  // All methods now display z-scores (not percentages)
  const displayValue = `z: ${value.toFixed(2)}`;
  const barWidth = Math.min(100, Math.max(0, ((value + 3) / 6) * 100)); // Map z-score [-3, 3] to [0, 100]

  return (
    <section key={type} className="mt-4">
      <div className="flex items-center mb-2">
        <h4 className="text-sm font-medium text-gray-700">{type.toUpperCase()} Analysis</h4>
        <InfoButton
          title={forensicsInfo.video[type]?.title}
          content={forensicsInfo.video[type]?.content}
        />
      </div>
      <div className="flex items-center justify-between text-sm mb-1">
        <span>Z-score</span>
        <span className="text-gray-600 font-semibold">{displayValue}</span>
      </div>
      <div className="h-2 w-full bg-gray-200 rounded-full overflow-hidden">
        <div className="h-full bg-gray-700" style={{ width: `${barWidth}%` }} />
      </div>
    </section>
  );
})}


    </CardContent>
  </Card>
)}

      </div>

      {/* Ad-hoc Analysis Result Popup - rendered outside main container */}
      {analysisResult && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="relative w-[400px] max-w-[90%] bg-white rounded-2xl shadow-lg p-5">
            {/* Close button */}
            <button
              className="absolute top-3 right-3 text-gray-500 hover:text-gray-800 text-lg font-bold"
              onClick={() => setAnalysisResult(null)}
            >
              ✕
            </button>

            {/* Analysis content */}
            <h4 className="font-semibold mb-2 text-gray-800">
              {analysisResult.analysis_type?.toUpperCase() || "Analysis"} Result
            </h4>

            <p className="text-sm text-gray-600 mb-1">
              Frame {analysisResult.frame_number ?? "N/A"}
            </p>

            <p
              className={`text-2xl font-bold mb-4 ${
                getColor(analysisResult.analysis_type, analysisResult.score)
              }`}
            >
              {analysisResult.score !== undefined ? (
                analysisResult.analysis_type === "noise"
                  ? `Noise (z): ${analysisResult.score.toFixed(2)}`
                  : analysisResult.analysis_type === "ela"
                  ? `ELA (z): ${analysisResult.score.toFixed(2)}`
                  : analysisResult.analysis_type === "lbp"
                  ? `LBP (z): ${analysisResult.score.toFixed(2)}`
                  : analysisResult.analysis_type === "ml"
                  ? `ML Score: ${(analysisResult.score * 100).toFixed(1)}%`
                  : `Score: ${analysisResult.score.toFixed(2)}`
              ) : (
                "No score available"
              )}
            </p>

            {(() => {
              let overlaySrc = analysisResult.overlay;

              if (overlaySrc && overlaySrc.startsWith('/')) {
                overlaySrc = `http://localhost:5050${overlaySrc}`;
              }

              if (!overlaySrc) {
                return null;
              }

              return (
                <img
                  src={overlaySrc}
                  alt={`${analysisResult.analysis_type?.toUpperCase() || "Analysis"} overlay`}
                  className="w-full rounded-lg mb-4"
                />
              );
            })()}

            <Button
              className="w-full bg-[#1E88E5] text-white hover:bg-[#114f85]"
              onClick={() => {
                setDetailsFrame(currentFrame);
                setIsDetailsOpen(true);
                setAnalysisResult(null);
              }}
            >
              More Details
            </Button>
          </div>
        </div>
      )}

      {/* Finish Analysis Popup */}
      {showFinishPopup && (
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-[100]"
          onClick={() => setShowFinishPopup(false)}
        >
          <div
            className="bg-white rounded-lg shadow-xl max-w-md p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-2xl font-bold text-gray-900 mb-4">Finish Analysis</h2>
            <p className="text-gray-700 mb-6">
              This analysis has been saved and will be available in Past Analyses.
            </p>
            <p className="text-gray-700 mb-6">
              Would you like to download a PDF report?
            </p>

            <div className="flex gap-3">
              <button
                onClick={async () => {
                  await handleDownloadPDF();
                  setShowFinishPopup(false);
                  navigate("/upload");
                }}
                disabled={downloadingPDF}
                className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition disabled:bg-gray-400"
              >
                {downloadingPDF ? "Downloading..." : "Yes, Download PDF"}
              </button>
              <button
                onClick={() => {
                  setShowFinishPopup(false);
                  navigate("/upload");
                }}
                className="flex-1 px-4 py-2 bg-gray-300 text-gray-700 rounded-lg hover:bg-gray-400 transition"
              >
                No, Just Finish
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Overall Statistics Popup - rendered outside main container */}
      {showStatsPopup && (
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-[100]"
          onClick={() => setShowStatsPopup(false)}
        >
          <div
            className="bg-white rounded-lg shadow-xl max-w-4xl max-h-[90vh] overflow-y-auto p-6"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold text-gray-900">Overall Analysis Statistics</h2>
              <button
                onClick={() => setShowStatsPopup(false)}
                className="text-gray-400 hover:text-gray-600 transition"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* ML Results */}
            {overallStats.syntheticMediaChance !== null ? (
              <div className="mb-6">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-semibold text-blue-700">
                    Synthetic Media Chance = {overallStats.syntheticMediaChance}%
                  </h3>
                  {overallStats.showMLButton && (
                    <button
                      onClick={() => handleRunFullAnalysis('ml')}
                      disabled={isAnalysing}
                      className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition whitespace-nowrap ml-4"
                    >
                      {overallStats.mlFrameCount === 0 ? 'Run Full Analysis' : 'Complete Analysis'}
                    </button>
                  )}
                </div>
                {overallStats.mlFrameCount > 0 && overallStats.mlFrameCount < 10 && (
                  <p className="text-sm text-gray-500 mt-1">({overallStats.mlFrameCount} frames analyzed)</p>
                )}
              </div>
            ) : (
              overallStats.showMLButton && (
                <div className="mb-6">
                  <div className="flex items-center justify-between">
                    <h3 className="text-lg font-semibold text-gray-700">
                      Synthetic Media Chance = N/A
                    </h3>
                    <button
                      onClick={() => handleRunFullAnalysis('ml')}
                      disabled={isAnalysing}
                      className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition whitespace-nowrap ml-4"
                    >
                      Run Full Analysis
                    </button>
                  </div>
                </div>
              )
            )}

            {/* Traditional Forensics */}
            <div className="space-y-3 mb-6">
              {(overallStats.elaScore !== null || overallStats.showElaButton) && (
                <div className="text-lg text-gray-700">
                  <div className="flex items-center justify-between">
                    <span>
                      <span className="font-medium">ELA Top Z-score:</span> {overallStats.elaScore !== null ? overallStats.elaScore : 'N/A'}
                      {overallStats.elaFrameCount > 0 && overallStats.elaFrameCount < 10 && (
                        <span className="text-sm text-gray-500 ml-2">({overallStats.elaFrameCount} frames)</span>
                      )}
                    </span>
                    {overallStats.showElaButton && (
                      <button
                        onClick={() => handleRunFullAnalysis('ela')}
                        disabled={isAnalysing}
                        className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition whitespace-nowrap ml-4"
                      >
                        {overallStats.elaFrameCount === 0 ? 'Run Full Analysis' : 'Complete Analysis'}
                      </button>
                    )}
                  </div>
                </div>
              )}
              {(overallStats.noiseScore !== null || overallStats.showNoiseButton) && (
                <div className="text-lg text-gray-700">
                  <div className="flex items-center justify-between">
                    <span>
                      <span className="font-medium">Noise Top Z-score:</span> {overallStats.noiseScore !== null ? overallStats.noiseScore : 'N/A'}
                      {overallStats.noiseFrameCount > 0 && overallStats.noiseFrameCount < 10 && (
                        <span className="text-sm text-gray-500 ml-2">({overallStats.noiseFrameCount} frames)</span>
                      )}
                    </span>
                    {overallStats.showNoiseButton && (
                      <button
                        onClick={() => handleRunFullAnalysis('noise')}
                        disabled={isAnalysing}
                        className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition whitespace-nowrap ml-4"
                      >
                        {overallStats.noiseFrameCount === 0 ? 'Run Full Analysis' : 'Complete Analysis'}
                      </button>
                    )}
                  </div>
                </div>
              )}
              {(overallStats.lbpScore !== null || overallStats.showLBPButton) && (
                <div className="text-lg text-gray-700">
                  <div className="flex items-center justify-between">
                    <span>
                      <span className="font-medium">LBP Top Z-score:</span> {overallStats.lbpScore !== null ? overallStats.lbpScore : 'N/A'}
                      {overallStats.lbpFrameCount > 0 && overallStats.lbpFrameCount < 10 && (
                        <span className="text-sm text-gray-500 ml-2">({overallStats.lbpFrameCount} frames)</span>
                      )}
                    </span>
                    {overallStats.showLBPButton && (
                      <button
                        onClick={() => handleRunFullAnalysis('lbp')}
                        disabled={isAnalysing}
                        className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition whitespace-nowrap ml-4"
                      >
                        {overallStats.lbpFrameCount === 0 ? 'Run Full Analysis' : 'Complete Analysis'}
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Metadata Forensics */}
            {metadata && (
              <div className="border-t pt-6">
                <h3 className="text-xl font-semibold text-gray-900 mb-4">Metadata Forensics</h3>
                <MetadataAnomaliesSummary metadata={metadata} />
                <IntegrityStatus metadata={metadata} />
                <FrameHashesSummary metadata={metadata} />
              </div>
            )}
          </div>
        </div>
      )}
      {toastMessage && (
        <Toast
          message={toastMessage}
          type={toastType}
          onClose={() => setToastMessage(null)}
        />
      )}
    </>
  );
};

export default FrameViewer;
