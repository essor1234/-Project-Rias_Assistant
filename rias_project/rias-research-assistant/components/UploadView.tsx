import React from 'react';
import { FileUploader } from './FileUploader';
import { SparklesIcon } from './icons/Icons';

interface UploadViewProps {
  uploadedFiles: File[];
  onFilesChange: (files: File[]) => void;
  onGenerate: () => void;
  isLoading: boolean;
  error: string | null;
  // --- ADDED ---
  // Prop to show "Uploading...", "Processing...", etc.
  statusMessage: string | null;
  // Prop to hold the final URL for the download button
  downloadUrl: string | null;
  // --- END ADDED ---
}

const quotes = [
  "The beautiful thing about learning is that nobody can take it away from you.",
  "Research is creating new knowledge.",
  "An investment in knowledge pays the best interest.",
  "The only source of knowledge is experience."
];

const quote = quotes[Math.floor(Math.random() * quotes.length)];

export const UploadView: React.FC<UploadViewProps> = ({
  uploadedFiles,
  onFilesChange,
  onGenerate,
  isLoading,
  error,
  // --- ADDED ---
  statusMessage,
  downloadUrl,
  // --- END ADDED ---
}) => {
  return (
    <div className="flex-1 flex items-center justify-center p-8">
      <div className="w-full max-w-2xl text-center">
        <h1 className="text-5xl font-extrabold mb-3 bg-clip-text text-transparent bg-gradient-to-r from-white to-gray-400">
          Welcome to <span className="text-pink-400">Rias</span>
        </h1>
        <p className="text-lg text-gray-400 mb-6 italic">{`"${quote}"`}</p>
        
        <div className="bg-black/20 p-8 rounded-2xl shadow-lg border border-white/10 backdrop-blur-md">
          <FileUploader onFilesChange={onFilesChange} uploadedFiles={uploadedFiles} />
          
          {/* --- MODIFIED BLOCK --- */}
          {/* This block now handles Error, Loading, Success (Download), and default states */}
          <div className="mt-8">

            {/* 1. Show Error (if any, and not loading) */}
            {error && !isLoading && <p className="text-red-400 mb-4">{error}</p>}
            
            {/* 2. Show Download Button (if complete) */}
            {downloadUrl && !isLoading && (
              <div>
                <p className="text-green-400 mb-2 font-semibold">Processing complete!</p>
                <a
                  href={downloadUrl}
                  download
                  className="w-full px-8 py-4 bg-gradient-to-r from-green-500 to-emerald-600 text-white font-bold rounded-lg hover:from-green-600 hover:to-emerald-700 transition-all duration-300 ease-in-out transform hover:scale-105 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-gray-900 focus:ring-emerald-500 flex items-center justify-center"
                >
                  Download All Results (.zip)
                </a>
              </div>
            )}

            {/* 3. Show Generate Button (if NOT complete) */}
            {!downloadUrl && (
              <button
                onClick={onGenerate}
                disabled={isLoading || uploadedFiles.length === 0}
                className="w-full px-8 py-4 bg-gradient-to-r from-pink-500 to-fuchsia-600 text-white font-bold rounded-lg hover:from-pink-600 hover:to-fuchsia-700 disabled:from-pink-800/50 disabled:to-fuchsia-900/50 disabled:cursor-not-allowed disabled:text-gray-400 transition-all duration-300 ease-in-out transform hover:scale-105 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-gray-900 focus:ring-fuchsia-500 flex items-center justify-center"
              >
                {isLoading ? (
                  <>
                    <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    {/* Show the specific status message, or a fallback */}
                    {statusMessage || 'Generating...'}
                  </>
                ) : (
                  <>
                    <SparklesIcon className="h-6 w-6 mr-2" />
                    Generate Results
                  </>
                )}
              </button>
            )}
          </div>
          {/* --- END MODIFIED BLOCK --- */}

        </div>
      </div>
    </div>
  );
};