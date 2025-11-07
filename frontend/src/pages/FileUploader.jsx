"use client";

import React, { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { Card, CardContent } from "./Card";
import { useNavigate } from "react-router-dom";
import { uploadVideo } from "../api/videos";
import { useAnalysis } from "../app/AnalysisProvider";

export default function FileUploader() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploadStatus, setUploadStatus] = useState(null); // 'uploading' | 'analyzing' | 'success' | 'error'
  const [fileRejectionError, setFileRejectionError] = useState(null);
  const { setAnalysisId, setSelectedModules } = useAnalysis();

  // checkbox states - map to backend module names
  const [options, setOptions] = useState({
    aiDetection: false,
    ela: false,
    noise: false,
    lbp: false,
  });

  const MAX_FILE_SIZE = 500 * 1024 * 1024; // 500MB in bytes

  const onDrop = useCallback((droppedFiles) => {
    if (droppedFiles && droppedFiles.length > 0) {
      const file = droppedFiles[0];

      // Check file size
      if (file.size > MAX_FILE_SIZE) {
        setFileRejectionError(`File too large. Maximum size is 500MB (your file: ${(file.size / 1024 / 1024).toFixed(1)}MB)`);
        setSelectedFile(null);
        return;
      }

      setSelectedFile(file);
      setUploadStatus(null); // Reset status when new file selected
      setFileRejectionError(null); // Clear any previous rejection errors
    }
  }, []);

  const onDropRejected = useCallback((fileRejections) => {
    if (fileRejections && fileRejections.length > 0) {
      const rejection = fileRejections[0];
      if (rejection.errors.some(e => e.code === 'file-invalid-type')) {
        setFileRejectionError('Invalid file type. Please select an image or video file.');
      } else if (rejection.errors.some(e => e.code === 'file-too-large')) {
        setFileRejectionError('File too large. Maximum size is 500MB.');
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
    maxSize: MAX_FILE_SIZE,
  });

  const handleCheckboxChange = (e) => {
    const { name, checked } = e.target;
    setOptions((prev) => ({ ...prev, [name]: checked }));
  };

  let dropzoneClass = "border-2 border-dashed rounded-xl p-10 cursor-pointer text-center transition";
  dropzoneClass += isDragActive ? " border-blue-500 bg-blue-50" : " border-gray-300 bg-white";

  const dropzoneContent = (
    <div>
      <p className={`font-semibold ${isDragActive ? "text-blue-500" : "text-gray-600"}`}>
        Click or drag image or video to {selectedFile ? 'replace' : 'select'}
      </p>
      <p className="text-xs text-gray-500 mt-2">Max file size: 500MB</p>
    </div>
  );

  const navigate = useNavigate();

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

      // Route based on media type
      if (response.media_type === "image") {
        // For images, run analysis immediately then navigate
        setUploadStatus('analyzing');
        try {
          const { startImageAnalysis } = await import('../api/videos');
          await startImageAnalysis(response.analysis_id, mlModules, traditionalModules);
          navigate(`/image-analysis/${response.analysis_id}`);
        } catch (analysisError) {
          console.error('Image analysis failed:', analysisError);
          alert('Image analysis failed. Please try again.');
          setUploadStatus('error');
        }
      } else {
        // For videos, go to intermediate Analysis page
        navigate("/analysis");
      }
    } catch (error) {
      setUploadStatus('error');
      // Check for 413 error (file too large)
      if (error.status === 413) {
        alert('File too large. Maximum upload size is 500MB.');
      } else {
        alert('Upload failed. Please try again.');
      }
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
                {uploadStatus === 'analyzing' && (
                  <p className="text-blue-600 text-sm">Analyzing...</p>
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
          disabled={uploadStatus === 'uploading' || uploadStatus === 'analyzing'}
          className="absolute bottom-20 right-48 bg-blue-600 text-white font-semibold px-6 py-2 rounded-lg shadow hover:bg-blue-700 transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed"
        >
          {uploadStatus === 'uploading' ? 'Uploading...' : uploadStatus === 'analyzing' ? 'Analyzing...' : 'Start'}
        </button>
      </div>
    </div>
  );
}
