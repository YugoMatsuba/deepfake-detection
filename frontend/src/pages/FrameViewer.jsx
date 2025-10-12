import React, { useRef, useState, useEffect } from "react";
import { Button } from "./Button";
import { Card, CardContent } from "./Card";

const FrameViewer = ({ videoSrc, deepfakeFrames = [], deepfakeMeta = {} }) => {
  const videoRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentFrame, setCurrentFrame] = useState(0);
  const [frameRate] = useState(25);
  const [deepfakeIndex, setDeepfakeIndex] = useState(0);
  const [duration, setDuration] = useState(0);

  // Tracks which marker is hovered
  const [hoveredIndex, setHoveredIndex] = useState(null);

  // Timer used to delay hiding the tooltip
  const hideTimerRef = useRef(null);

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

  const handleTimeUpdate = () => {
    const video = videoRef.current;
    if (!video) return;
    setCurrentFrame(Math.floor(video.currentTime * frameRate));
  };

  const handleLoadedMetadata = () => {
    const video = videoRef.current;
    if (video) {
      setDuration(Math.floor(video.duration * frameRate));
    }
  };

  // Helper: compute left % safely (handles duration === 0)
  const pctLeft = (frame) => {
    if (!duration) return 0;
    return (frame / duration) * 100;
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
    <div className="flex justify-center items-center min-h-screen bg-gray-50">
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
              style={{ width: `${duration ? (currentFrame / duration) * 100 : 0}%` }}
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
                      // Wire this to a modal/side panel later
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
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default FrameViewer;
