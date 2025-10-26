import React, { useCallback, useState } from 'react';
import { ArrowUpTrayIcon, DocumentTextIcon, XCircleIcon } from './icons/Icons';

interface FileUploaderProps {
  onFilesChange: (files: File[]) => void;
  uploadedFiles: File[];
}

export const FileUploader: React.FC<FileUploaderProps> = ({ onFilesChange, uploadedFiles }) => {
  const [isDragging, setIsDragging] = useState(false);

  const handleDragEnter = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      onFilesChange(Array.from(e.dataTransfer.files));
    }
  }, [onFilesChange]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      onFilesChange(Array.from(e.target.files));
    }
  };
  
  const handleRemoveFile = (index: number) => {
    const newFiles = [...uploadedFiles];
    newFiles.splice(index, 1);
    onFilesChange(newFiles);
  };

  return (
    <div>
      <div
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        className={`relative block w-full border-2 border-dashed rounded-lg p-12 text-center transition-colors duration-300 ${isDragging ? 'border-pink-500 bg-pink-500/10' : 'border-white/20 hover:border-white/40'}`}
      >
        <input
          type="file"
          id="file-upload"
          multiple
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
          onChange={handleFileChange}
          accept=".pdf,.txt,.md,.docx"
        />
        <label htmlFor="file-upload" className="cursor-pointer">
          <ArrowUpTrayIcon className="mx-auto h-12 w-12 text-gray-400" />
          <span className="mt-2 block text-sm font-semibold text-gray-200">
            Drag & drop files or click to upload
          </span>
          <span className="mt-1 block text-xs text-gray-500">Up to 5 files</span>
        </label>
      </div>

      {uploadedFiles.length > 0 && (
        <div className="mt-6">
          <h3 className="text-sm font-medium text-gray-300 text-left">Uploaded Files:</h3>
          <ul className="mt-2 space-y-2">
            {uploadedFiles.map((file, index) => (
              <li key={index} className="flex items-center justify-between bg-white/5 p-2 rounded-md">
                <div className="flex items-center truncate">
                  <DocumentTextIcon className="h-5 w-5 mr-2 text-gray-400 flex-shrink-0" />
                  <span className="text-sm text-gray-200 truncate">{file.name}</span>
                </div>
                 <button onClick={() => handleRemoveFile(index)} className="text-gray-500 hover:text-red-400">
                  <XCircleIcon className="h-5 w-5" />
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};