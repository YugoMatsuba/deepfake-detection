"use client";

import React, { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { Card, CardContent } from "./Card";
import { useNavigate } from "react-router-dom";
import { uploadVideo } from "../api/videos";
import { useAnalysis } from "../app/AnalysisProvider";

export default function FileUploader() {
  const [files, setFiles] = useState([]);
  const [uploadStatus, setUploadStatus] = useState(null); // 'uploading' | 'success' | 'error'
  const { setAnalysisId, setSelectedModules } = useAnalysis();

  // checkbox states - map to backend module names
  const [options, setOptions] = useState({
    aiDetection: false,
    ela: false,
    noise: false,
    lbp: false,
  });

  const onDrop = useCallback(async (droppedFiles) => {
    setFiles(droppedFiles);
    if (droppedFiles && droppedFiles.length > 0) {
      setUploadStatus('uploading');
      try {
        const response = await uploadVideo(droppedFiles[0]);
        setAnalysisId(response.analysis_id); // Save analysis_id to context
        setUploadStatus('success');
      } catch {
        setUploadStatus('error');
      }
    }
  }, [setAnalysisId]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "image/*": [], "video/*": [] },
  });

  const handleCheckboxChange = (e) => {
    const { name, checked } = e.target;
    setOptions((prev) => ({ ...prev, [name]: checked }));
  };

  let dropzoneClass = "border-2 border-dashed rounded-xl p-10 cursor-pointer text-center transition";
  dropzoneClass += isDragActive ? " border-blue-500 bg-blue-50" : " border-gray-300 bg-white";

  const dropzoneContent = (
    <p className={`font-semibold ${isDragActive ? "text-blue-500" : "text-gray-600"}`}>
      Drag images or videos here, or click to select
    </p>
  );

  const navigate = useNavigate();
  const { analysisId } = useAnalysis();

  const handleGoToAnalysis = () => {
    if (!analysisId) {
      alert('Please upload a video first');
      return;
    }

    // Build module arrays from checkboxes
    const mlModules = options.aiDetection ? ['xception', 'spsl', 'ucf'] : [];
    const traditionalModules = [];
    if (options.ela) traditionalModules.push('ela');
    if (options.noise) traditionalModules.push('noise');
    if (options.lbp) traditionalModules.push('lbp');

    if (mlModules.length === 0 && traditionalModules.length === 0) {
      alert('Please select at least one analysis method');
      return;
    }

    // Save selected modules to context
    setSelectedModules({ ml: mlModules, traditional: traditionalModules });
    navigate("/analysis");
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
                <h2 className="font-semibold">
                  {uploadStatus === 'uploading' && 'Uploading...'}
                  {uploadStatus === 'success' && 'Upload successful!'}
                  {uploadStatus === 'error' && 'Upload failed'}
                </h2>
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
                name="aiDetection"
                checked={options.aiDetection}
                onChange={handleCheckboxChange}
                className="w-4 h-4"
              />
              <span className="font-semibold">AI Detection</span>
            </label>
            <label className="flex items-center space-x-3">
              <input
                type="checkbox"
                name="ela"
                checked={options.ela}
                onChange={handleCheckboxChange}
                className="w-4 h-4"
              />
              <span className="font-semibold">ELA Analysis</span>
            </label>
            <label className="flex items-center space-x-3">
              <input
                type="checkbox"
                name="noise"
                checked={options.noise}
                onChange={handleCheckboxChange}
                className="w-4 h-4"
              />
              <span className="font-semibold">Noise Analysis</span>
            </label>
            <label className="flex items-center space-x-3">
              <input
                type="checkbox"
                name="lbp"
                checked={options.lbp}
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
