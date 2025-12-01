"use client";

import { useState, useCallback } from "react";
import { Upload } from "lucide-react";

interface ImportDropzoneProps {
  onFileSelect: (file: File) => void;
  maxSizeMB?: number;
}

export function ImportDropzone({
  onFileSelect,
  maxSizeMB = 500,
}: ImportDropzoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const validateFile = (file: File): string | null => {
    if (!file.name.endsWith(".csv")) {
      return "Please upload a .csv file";
    }

    const maxBytes = maxSizeMB * 1024 * 1024;
    if (file.size > maxBytes) {
      return `File size exceeds ${maxSizeMB}MB limit`;
    }

    return null;
  };

  const handleFile = (file: File) => {
    const validationError = validateFile(file);

    if (validationError) {
      setError(validationError);
      return;
    }

    setError(null);
    onFileSelect(file);
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      handleFile(files[0]);
    }
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleClick = () => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".csv";
    input.onchange = (e) => {
      const files = (e.target as HTMLInputElement).files;
      if (files && files.length > 0) {
        handleFile(files[0]);
      }
    };
    input.click();
  };

  return (
    <div>
      <div
        onClick={handleClick}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        className={`
          border-2 border-dashed rounded-lg p-12 text-center cursor-pointer
          transition-colors
          ${
            isDragging
              ? "border-primary-500 bg-primary-50"
              : "border-gray-300 hover:border-gray-400 bg-gray-50"
          }
        `}
      >
        <div className="flex justify-center mb-4">
          <Upload
            className={`h-12 w-12 ${isDragging ? "text-primary-500" : "text-gray-400"}`}
          />
        </div>
        <p className="text-lg font-medium text-gray-900 mb-2">
          {isDragging ? "Drop file to upload" : "Drag & drop CSV file here"}
        </p>
        <p className="text-sm text-gray-600">or click to browse</p>
        <p className="text-xs text-gray-500 mt-2">Max file size: {maxSizeMB}MB</p>
      </div>

      {error && (
        <div className="mt-3 text-sm text-red-600 flex items-center gap-1">
          <span>Error:</span> {error}
        </div>
      )}
    </div>
  );
}
