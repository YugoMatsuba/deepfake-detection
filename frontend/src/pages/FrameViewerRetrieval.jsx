import React, { useEffect, useState } from 'react';
import FrameViewer from './FrameViewer';

export default function FrameViewerPage() {
  const [latestVideo, setLatestVideo] = useState(null);

  useEffect(() => {
    const fetchVideos = async () => {
      try {
        const response = await fetch('http://localhost:5050/api/videos/all'); 
        const data = await response.json();

        if (data.length > 0) {
          // Pick the last video (most recent)
          const lastVideo = data[data.length - 1];
          setLatestVideo(lastVideo);
        }
      } catch (err) {
        console.error('Error fetching videos:', err);
      }
    };

    fetchVideos();
  }, []);

  if (!latestVideo) return <p>Loading latest video...</p>;

  // Construct the src URL
  const videoSrc = `http://localhost:5050/api/videos/${latestVideo.id}`;

  return (
    <div className="p-4">
      <h1 className="text-3xl font-bold mb-4">Frame Analysis</h1>
      <FrameViewer videoSrc={videoSrc} />
    </div>
  );
}
