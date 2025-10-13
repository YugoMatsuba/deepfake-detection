import React, { useRef, useState, useEffect } from "react";
import { Button } from "./Button";
import { Card, CardContent } from "./Card";

const FrameViewer = ({ videoSrc, deepfakeFrames = [], deepfakeMeta = {}}) => {
  const videoRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentFrame, setCurrentFrame] = useState(0);
const [frameRate, setFrameRate] = useState(null);
  const [deepfakeIndex, setDeepfakeIndex] = useState(0);
  const [duration, setDuration] = useState(0);
  const [durationFrames, setDurationFrames] = useState(0);

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
  const getMeta = (frame) => (frame != null ? deepfakeMeta?.[frame] || null : null);

  useEffect(() => {
  const fetchFrameRate = async () => {
    try {
      const response = await fetch("http://localhost:5000/frame_rate");
      const data = await response.json();
      if (data.frame_rate) {
        setFrameRate(data.frame_rate);
        console.log("Fetched frame rate:", data.frame_rate);
      }
    } catch (error) {
      console.error("Error fetching frame rate:", error);
    }
  };

  fetchFrameRate();
}, []);


  // Average anomaly score across frames that have a score
  const getAverageAnomaly = () => {
    const entries = Object.values(deepfakeMeta || {}).filter(
      (m) => typeof m?.anomalyScore === "number"
    );
    if (!entries.length) return null;
    const sum = entries.reduce((acc, m) => acc + m.anomalyScore, 0);
    return sum / entries.length; // 0..1
  };

  // Extract “details” for the currently selected frame
  const details = (() => {
    const meta = getMeta(detailsFrame);
    return {
      anomalyScore: typeof meta?.anomalyScore === "number" ? meta.anomalyScore : null, // 0..1
      methods: {
        ela: typeof meta?.methods?.ela === "number" ? meta.methods.ela : null,
        noise: typeof meta?.methods?.noise === "number" ? meta.methods.noise : null,
        lbp: typeof meta?.methods?.lbp === "number" ? meta.methods.lbp : null,
      },
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

  const scheduleHideTooltip = () => {
    clearHideTimer();
    hideTimerRef.current = setTimeout(() => {
      setHoveredIndex(null);
      hideTimerRef.current = null;
    }, 500); // 0.5s in miliseconds
  };

  useEffect(() => {
    return () => clearHideTimer();
  }, []);

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
    setCurrentFrame(Math.floor(video.currentTime * frameRate));
  };

  const prevFrame = () => {
    const video = videoRef.current;
    if (!video) return;
    video.currentTime = Math.max(video.currentTime - 1 / frameRate, 0);
    setCurrentFrame(Math.floor(video.currentTime * frameRate));
  };

  const nextDeepfake = () => {
    if (deepfakeFrames.length === 0) return;
    const nextIndex = deepfakeFrames.findIndex((f) => f > currentFrame);
    if (nextIndex !== -1) {
      const video = videoRef.current;
      video.currentTime = deepfakeFrames[nextIndex] / frameRate;
      setCurrentFrame(deepfakeFrames[nextIndex]);
      setDeepfakeIndex(nextIndex);
    }
  };

  const prevDeepfake = () => {
    if (deepfakeFrames.length === 0) return;

    let prevDeepfakeIndex = -1;
    for (let i = 0; i < deepfakeFrames.length; i++) {
      if (deepfakeFrames[i] < currentFrame) {
        prevDeepfakeIndex = i;
      }
    }

    if (prevDeepfakeIndex !== -1) {
      const video = videoRef.current;
      video.currentTime = deepfakeFrames[prevDeepfakeIndex] / frameRate;

     
      setCurrentFrame(deepfakeFrames[prevDeepfakeIndex]);
      setDeepfakeIndex(prevDeepfakeIndex);
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
  if (frameRate) setCurrentFrame(Math.floor(video.currentTime * frameRate));
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
  const hoveredFrame =
    hoveredIndex !== null &&
    hoveredIndex >= 0 &&
    hoveredIndex < deepfakeFrames.length
      ? deepfakeFrames[hoveredIndex]
      : null;

  // Tooltip text: from deepfakeMeta if available, else a fallback
  const hoveredSummary =
    hoveredFrame != null && deepfakeMeta && deepfakeMeta[hoveredFrame]?.summary
      ? deepfakeMeta[hoveredFrame].summary
      : hoveredFrame != null
      ? `Flagged at frame ${hoveredFrame}.`
      : "";

  return (
    <div className="flex justify-center items-center min-h-screen bg-gray-50 space-x-10">
      <Card className="w-full max-w-3xl shadow-lg rounded-2xl">
        <CardContent className="flex flex-col items-center space-y-4 p-6">
          <video
            ref={videoRef}
            src={videoSrc}
            width="640"
            height="360"
            onTimeUpdate={handleTimeUpdate}
            onLoadedMetadata={handleLoadedMetadata}
            className="rounded-lg border border-gray-300"
          />

          {/* === TIMELINE BAR === */}
          <div className="relative w-full h-4 bg-gray-200 rounded-lg">
            {/* Current progress */}
            <div
              className="absolute top-0 left-0 h-4 bg-blue-500 rounded-lg"
              style={{ width: `${durationFrames ? (currentFrame / durationFrames) * 100 : 0}%` }}
            />

            {/* Deepfake markers */}
            {deepfakeFrames.map((frame, index) => (
              <div
                key={index}
                className="absolute top-0 h-4 w-1 bg-red-500"
                style={{ left: `${pctLeft(frame)}%` }}
                onMouseEnter={() => {
                  clearHideTimer();
                  setHoveredIndex(index); // immediate switch
                }}
                onMouseLeave={scheduleHideTooltip} // 1s grace
              />
            ))}

            {/* Hover tooltip */}
            {hoveredFrame != null && (
              <div
                className="absolute -top-28 z-30"
                style={{ left: `${pctLeft(hoveredFrame)}%`, transform: "translateX(-50%)" }}
                onMouseEnter={clearHideTimer}      // keep open while hovered
                onMouseLeave={scheduleHideTooltip} // close after 1s when leaving
              >
                {/* Tooltip card */}
                <div className="flex flex-col items-center justify-center relative w-64 rounded-xl border border-gray-300 bg-white p-3 shadow-lg">
                  <p className="text-sm text-gray-800 leading-snug">{hoveredSummary}</p>
                  <Button
                    size="sm"
                    className="mt-2 bg-[#1E88E5] text-white hover:bg-[#114f85] hover:text-[#cccccc] transition-colors"
                    onClick={() => {
                      setDetailsFrame(hoveredFrame);
                      setIsDetailsOpen(true);
                    }}
                  >
                    More Details
                  </Button>

                  {/* Arrow */}
                  <div className="absolute left-1/2 top-full -translate-x-1/2 -mt-2 w-3 h-3 rotate-45 bg-white border-r border-b border-gray-300" />
                </div>
              </div>
            )}
          </div>

          <div className="flex justify-center gap-12">
            <Button variant="secondary" className="bg-white" onClick={prevDeepfake}>
              <span className="text-2xl">&lt;&lt;</span>
            </Button>
            <Button size="lg" variant="secondary" className="bg-white" onClick={prevFrame}>
              <span className="text-2xl">&lt;</span>
            </Button>

            <div className="flex flex-col items-center gap-2">
              <Button variant="default" onClick={togglePlay}>
                {isPlaying ? "Pause" : "Play"}
              </Button>
              <Button variant="destructive" onClick={restartVideo}>
                Restart
              </Button>
            </div>

            <Button variant="secondary" size="lg" className="bg-white" onClick={nextFrame}>
              <span className="text-2xl">&gt;</span>
            </Button>
            <Button variant="secondary" className="bg-white" onClick={nextDeepfake}>
              <span className="text-2xl">&gt;&gt;</span>
            </Button>
          </div>

          <div className="text-sm text-gray-700">
            <p>
              <span className="font-medium">Current Frame:</span> {currentFrame}
            </p>
            {deepfakeFrames.length > 0 && (
              <p>
                <span className="font-medium">Next Deepfake Frame:</span>{" "}
                {deepfakeFrames[deepfakeIndex] || "None"}
              </p>
            )}
            <p>
                <span className="font-medium">Frame Rate:</span>{" "}
                {frameRate ? frameRate.toFixed(2) : "Loading..."} fps
              </p>
          </div>
        </CardContent>
      </Card>

        {/* RIGHT: Details panel */}
        {isDetailsOpen && (
          <Card className="w-[360px] shrink-0 shadow-lg rounded-2xl gap-">
            <CardContent className="p-5 space-y-5">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="text-lg font-semibold">Frame Details</h3>
                  <p className="text-xs text-gray-500">
                    Frame {detailsFrame != null ? detailsFrame : "—"}
                  </p>
                </div>
                <Button variant="secondary" className="bg-white" onClick={() => setIsDetailsOpen(false)}>
                  Close
                </Button>
              </div>

              {/* Anomaly vs Average */}
              <section>
                <h4 className="text-sm font-medium text-gray-700 mb-2">Anomaly Score</h4>
                {(() => {
                  const avg = getAverageAnomaly();
                  const cur = details.anomalyScore;
                  if (cur == null) {
                    return <p className="text-sm text-gray-500">No anomaly score available.</p>;
                  }
                  const pct = Math.round(cur * 100);
                  const avgPct = avg != null ? Math.round(avg * 100) : null;
                  const delta = avg != null ? pct - avgPct : null;
                  return (
                    <div className="space-y-1">
                      <div className="flex items-center justify-between text-sm">
                        <span className="font-medium">{pct}%</span>
                        {avgPct != null && (
                          <span className="text-gray-500">
                            avg {avgPct}%{" "}
                            {delta != null && (
                              <span className={delta >= 0 ? "text-red-600" : "text-green-600"}>
                                ({delta >= 0 ? "+" : ""}{delta}%)
                              </span>
                            )}
                          </span>
                        )}
                      </div>
                      <div className="h-2 w-full bg-gray-200 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-blue-500"
                          style={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
                        />
                      </div>
                    </div>
                  );
                })()}
              </section>

              {/* Forensic methods */}
              <section>
                <h4 className="text-sm font-medium text-gray-700 mb-2">Forensic Methods</h4>
                <div className="space-y-3">
                  {[
                    { key: "ela", label: "ELA Analysis", value: details.methods.ela },
                    { key: "noise", label: "Noise Analysis", value: details.methods.noise },
                    { key: "lbp", label: "LBP Analysis", value: details.methods.lbp },
                  ].map(({ key, label, value }) => (
                    <div key={key}>
                      <div className="flex items-center justify-between text-sm">
                        <span>{label}</span>
                        <span className="text-gray-600">
                          {typeof value === "number" ? `${Math.round(value * 100)}%` : "N/A"}
                        </span>
                      </div>
                      <div className="h-2 w-full bg-gray-200 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-gray-700"
                          style={{
                            width: `${
                              typeof value === "number"
                                ? Math.min(100, Math.max(0, Math.round(value * 100)))
                                : 0
                            }%`,
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </section>

              {/* Temporal labels */}
              <section>
                <h4 className="text-sm font-medium text-gray-700 mb-2">Temporal Consistency</h4>
                {details.temporalLabels.length ? (
                  <ul className="list-disc pl-5 space-y-1 text-sm text-gray-800">
                    {details.temporalLabels.map((t, i) => (
                      <li key={i}>{t}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-gray-500">No temporal anomalies reported.</p>
                )}
              </section>
            </CardContent>
          </Card>
        )}
      </div>
  );
};

export default FrameViewer;
