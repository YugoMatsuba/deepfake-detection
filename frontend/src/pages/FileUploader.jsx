"use client";

import React, { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { Card, CardContent } from "./Card";
import { useNavigate } from "react-router-dom";
import { uploadVideo } from "../api/videos";
import { useAnalysis } from "../app/AnalysisProvider";

export default function FileUploader() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploadStatus, setUploadStatus] = useState(null); // 'uploading' | 'success' | 'error'
  const [fileRejectionError, setFileRejectionError] = useState(null);
  const { setAnalysisId, setSelectedModules } = useAnalysis();

  // checkbox states - map to backend module names
  const [options, setOptions] = useState({
    aiDetection: false,
    ela: false,
    noise: false,
    lbp: false,
  });

  const onDrop = useCallback((droppedFiles) => {
    if (droppedFiles && droppedFiles.length > 0) {
      setSelectedFile(droppedFiles[0]);
      setUploadStatus(null); // Reset status when new file selected
      setFileRejectionError(null); // Clear any previous rejection errors
    }
  }, []);

  const onDropRejected = useCallback((fileRejections) => {
    if (fileRejections && fileRejections.length > 0) {
      const rejection = fileRejections[0];
      if (rejection.errors.some(e => e.code === 'file-invalid-type')) {
        setFileRejectionError('Invalid file type. Please select an image or video file.');
      } else {
        setFileRejectionError('File rejected. Please try again.');
      }
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    onDropRejected,
    accept: { "image/*": [], "video/*": [] },
    multiple: false,
    maxFiles: 1,
  });

  const handleCheckboxChange = (e) => {
    const { name, checked } = e.target;
    setOptions((prev) => ({ ...prev, [name]: checked }));
  };

  let dropzoneClass = "border-2 border-dashed rounded-xl p-10 cursor-pointer text-center transition";
  dropzoneClass += isDragActive ? " border-blue-500 bg-blue-50" : " border-gray-300 bg-white";

  const dropzoneContent = (
    <p className={`font-semibold ${isDragActive ? "text-blue-500" : "text-gray-600"}`}>
      Click or drag image or video to {selectedFile ? 'replace' : 'select'}
    </p>
  );

  const navigate = useNavigate();
  const { analysisId } = useAnalysis();

  const handleGoToAnalysis = async () => {
    if (!selectedFile) {
      alert('Please select a file first');
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

    // Upload file when Start is clicked
    setUploadStatus('uploading');
    try {
      const response = await uploadVideo(selectedFile);
      setAnalysisId(response.analysis_id);
      setUploadStatus('success');

      // Save selected modules to context
      setSelectedModules({ ml: mlModules, traditional: traditionalModules });
      navigate("/analysis");
    } catch (error) {
      setUploadStatus('error');
      alert('Upload failed. Please try again.');
    }
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

            {selectedFile && (
              <div className="mt-4 space-y-2">
                <h2 className="font-semibold text-gray-700">
                  Selected: {selectedFile.name}
                </h2>
                {uploadStatus === 'uploading' && (
                  <p className="text-blue-600 text-sm">Uploading...</p>
                )}
                {uploadStatus === 'error' && (
                  <p className="text-red-600 text-sm">Upload failed</p>
                )}
              </div>
            )}

            {fileRejectionError && (
              <div className="mt-4">
                <p className="text-red-600 text-sm font-semibold">{fileRejectionError}</p>
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
          disabled={uploadStatus === 'uploading'}
          className="absolute bottom-20 right-48 bg-blue-600 text-white font-semibold px-6 py-2 rounded-lg shadow hover:bg-blue-700 transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed"
        >
          {uploadStatus === 'uploading' ? 'Uploading...' : 'Start'}
        </button>
      </div>
    </div>
  );
}
