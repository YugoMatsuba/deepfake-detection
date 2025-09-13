"use client";

import React, { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { Card, CardContent } from "./Card";
import { useNavigate } from "react-router-dom";

export default function FileUploader() {
    /*Storing files in an array*/
  const [files, setFiles] = useState([]);
  /*Array storing the checked state of each checkbox*/
  const [options, setOptions] = useState({
    option1: false,
    option2: false,
    option3: false,
  });

  const onDrop = useCallback((droppedFiles) => {
    setFiles(droppedFiles);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "image/*": [],
      "video/*": [],
    },
  });

  const handleCheckboxChange = (checkbox) => {
    const { name, checked } = checkbox.target;
    setOptions((prev) => ({ ...prev, [name]: checked }));
  };

  /* border width 2 px, dashed, extra large border radius, 40px padding between dropzone and border, change cursor to pointer to indicate clickable and center text*/

  let dropzoneClass = "border-2 border-dashed rounded-xl p-10 cursor-pointer text-center transition";

  if (isDragActive) {
    dropzoneClass += " border-blue-500 bg-blue-50";
  } else {
    dropzoneClass += " border-gray-300 bg-white";
  }

  let dropzoneContent;

  if (isDragActive){
    dropzoneContent = <p className="text-blue-500 font-semibold">Drop files here...</p>;
  } else {
    dropzoneContent = <p className="text-gray-600 font-semibold">Drag images or videos here, or click to select</p>;
  }

  const navigate = useNavigate();

  const handleGoToAnalysis = () => {
    navigate("/analysis");
  }

  return (
    <div className="px-3">
      <h1 className="text-5xl font-bold mt-2 mb-2 text-center py-10">Deepfake Analysis</h1>
    <div className="flex gap-x-32 mt-10 px-4 items-center">
      <Card className="w-full max-w-md p-6 bg-gray-100">
        <CardContent>
          <div
            {...getRootProps()}
            className={dropzoneClass}>
           
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
