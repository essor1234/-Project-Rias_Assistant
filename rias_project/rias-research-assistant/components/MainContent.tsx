// components/MainContent.tsx

import React from 'react';
import { UploadView } from './UploadView';
import { FileViewer } from './FileViewer'; // --- NEW IMPORT ---

// --- UPDATE PROPS INTERFACE ---
interface MainContentProps {
  uploadedFiles: File[];
  onFilesChange: (files: File[]) => void;
  onGenerate: () => void;
  isLoading: boolean;
  error: string | null;
  statusMessage: string | null;
  downloadUrl: string | null;
  selectedFile: string | null; // --- NEW PROP ---
  onCloseViewer: () => void; // --- NEW PROP ---
}

export const MainContent: React.FC<MainContentProps> = ({
  uploadedFiles,
  onFilesChange,
  onGenerate,
  isLoading,
  error,
  statusMessage,
  downloadUrl,
  selectedFile, // --- NEW PROP ---
  onCloseViewer, // --- NEW PROP ---
}) => {
  return (
    <main className="flex-1 overflow-y-auto">
      {/* --- NEW LOGIC --- */}
      {/* If a file is selected, show the viewer. Otherwise, show the upload view. */}
      {selectedFile ? (
        <FileViewer 
          filePath={selectedFile} 
          onClose={onCloseViewer} 
        />
      ) : (
        <UploadView
          uploadedFiles={uploadedFiles}
          onFilesChange={onFilesChange}
          onGenerate={onGenerate}
          isLoading={isLoading}
          error={error}
          statusMessage={statusMessage}
          downloadUrl={downloadUrl}
        />
      )}
    </main>
  );
};