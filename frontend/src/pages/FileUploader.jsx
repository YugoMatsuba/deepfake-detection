"use client";

import React, { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { Card, CardContent } from "./Card";
import { useNavigate } from "react-router-dom";
import { uploadVideo } from "../api/videos"; // POST /api/videos

export default function FileUploader() {
  // store selected files for the list UI
  const [files, setFiles] = useState([]);
  const [uploadedVideos, setUploadedVideos] = useState([]);
  // checkbox states
  const [options, setOptions] = useState({
    option1: false,
    option2: false,
    option3: false,
    option4: false,
  });

  // silently stage upload in the background after selection
  const onDrop = useCallback(async (droppedFiles) => {
  setFiles(droppedFiles);

  if (droppedFiles && droppedFiles.length > 0) {
    try {
      const meta = await uploadVideo(droppedFiles[0]);
      setUploadedVideos((prev) => [...prev, meta]); // store metadata
    } catch (err) {
      console.error("Upload failed", err);
    }
  }
}, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "image/*": [], "video/*": [] },
  });

  const handleCheckboxChange = (e) => {
    const { name, checked } = e.target;
    setOptions((prev) => ({ ...prev, [name]: checked }));
  };

  // styles unchanged
  let dropzoneClass = "border-2 border-dashed rounded-xl p-10 cursor-pointer text-center transition";
  dropzoneClass += isDragActive ? " border-blue-500 bg-blue-50" : " border-gray-300 bg-white";

  const dropzoneContent = isDragActive
    ? <p className="text-blue-500 font-semibold">Drop files here...</p>
    : <p className="text-gray-600 font-semibold">Drag images or videos here, or click to select</p>;

  const navigate = useNavigate();
  const handleGoToAnalysis = () => {
  const videoIds = uploadedVideos.map((v) => v.id);
  navigate("/analysis", { state: { videoIds, options } });
};

  return (
    <div className="px-3">
      <h1 className="text-5xl font-bold mt-2 mb-2 text-center py-10">Deepfake Analysis</h1>
      <div className="flex gap-x-32 mt-10 px-4 items-center">
        <Card className="w-full max-w-md p-6 bg-gray-100">
          <CardContent>
            <div {...getRootProps()} className={dropzoneClass}>
              <input {...getInputProps()} />
              {dropzoneContent}
            </div>

            {files.length > 0 && (
              <div className="mt-4 space-y-2">
                <h2 className="font-semibold">Uploaded Files:</h2>
                <ul className="list-disc pl-5 text-gray-700">
                  {files.map((file) => (
                    <li key={file.name}>{file.name}</li>
                  ))}
                </ul>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="max-w-md p-6 bg-black-100">
          <div className="flex flex-col justify-start space-y-4">
            <label className="flex items-center space-x-3">
              <input
                type="checkbox"
                name="option1"
                checked={options.option1}
                onChange={handleCheckboxChange}
                className="w-4 h-4"
              />
              <span className="font-semibold">AI Detection</span>
            </label>
            <label className="flex items-center space-x-3">
              <input
                type="checkbox"
                name="option2"
                checked={options.option2}
                onChange={handleCheckboxChange}
                className="w-4 h-4"
              />
              <span className="font-semibold">ELA Analysis</span>
            </label>
            <label className="flex items-center space-x-3">
              <input
                type="checkbox"
                name="option3"
                checked={options.option3}
                onChange={handleCheckboxChange}
                className="w-4 h-4"
              />
              <span className="font-semibold">Noise Analysis</span>
            </label>
            <label className="flex items-center space-x-3">
              <input
                type="checkbox"
                name="option4"
                checked={options.option4}
                onChange={handleCheckboxChange}
                className="w-4 h-4"
              />
              <span className="font-semibold">LBP Analysis</span>
            </label>
          </div>
        </Card>

        <button
          onClick={handleGoToAnalysis}
          className="absolute bottom-20 right-48 bg-blue-600 text-white font-semibold px-6 py-2 rounded-lg shadow hover:bg-blue-700 transition-colors"
        >
          Start
        </button>
      </div>
    </div>
  );
}
