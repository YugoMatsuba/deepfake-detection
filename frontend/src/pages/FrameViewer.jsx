import React, { useRef, useState } from "react";
import { Button } from "./Button";
import { Card, CardContent } from "./Card";

const FrameViewer = ({ videoSrc, deepfakeFrames = [] }) => {
  const videoRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentFrame, setCurrentFrame] = useState(0);
  const [frameRate] = useState(25);
  const [deepfakeIndex, setDeepfakeIndex] = useState(0);
  const [duration, setDuration] = useState(0);

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
    if(!video) return;
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

    for(let i = 0; i < deepfakeFrames.length; i++) {
        if(deepfakeFrames[i] < currentFrame) {
            prevDeepfakeIndex = i;
        }
    }

    if(prevDeepfakeIndex !== -1) {
        const video = videoRef.current;
        video.currentTime = deepfakeFrames[prevDeepfakeIndex] / frameRate;
        setCurrentFrame(deepfakeFrames[prevDeepfakeIndex]);
        setDeepfakeIndex(prevDeepfakeIndex);

    }

  }


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
            style={{ width: `${(currentFrame / duration) * 100}%` }}
          />
          {/* Deepfake markers */}
          {deepfakeFrames.map((frame, index) => (
            <div
              key={index}
              className="absolute top-0 h-4 w-1 bg-red-500"
              style={{ left: `${(frame / duration) * 100}%` }}
              title={`Deepfake at frame ${frame}`}
            />
          ))}
          </div>

         <div className="flex justify-center gap-12">
          <Button variant = "secondary" className="bg-white" onClick={prevDeepfake}>
            <span className="text-2xl">&lt;&lt;</span>
          </Button>
          <Button size = "lg" variant="secondary" className="bg-white" onClick={prevFrame}>
            <span className="text-2xl">&lt;</span>
          </Button>
          <Button variant="default"  onClick={togglePlay}>
            {isPlaying ? "Pause" : "Play"}
          </Button>
          <Button variant="secondary" size = "lg" className="bg-white" onClick={nextFrame}>
           <span className="text-2xl">&gt;</span>
          </Button>
          <Button variant = "secondary" className="bg-white"onClick={nextDeepfake}>
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