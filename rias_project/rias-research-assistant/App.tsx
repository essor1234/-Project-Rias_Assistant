// App.tsx

import React, { useState } from 'react';
import { Sidebar } from './components/Sidebar';
import { MainContent } from './components/MainContent';
import {
  uploadAndProcessFile,
  checkJobStatus,
  getDownloadUrl
} from './services/generationService';
import { FileTree } from './types'; // This import is now correct

let pollInterval: NodeJS.Timeout | null = null;
const API_BASE_URL = "http://localhost:8000";

function App() {
  // --- STATE MANAGEMENT ---
  const [uploadedFiles, setUploadedFiles] = useState<File[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // --- NEW STATES ---
  const [fileTree, setFileTree] = useState<FileTree[] | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<string | null>(null); // For the file viewer

  /**
   * Handles when a user selects files from the FileUploader.
   */
  const handleFilesChange = (files: File[]) => {
    setUploadedFiles(files);
    // Reset everything
    setDownloadUrl(null);
    setError(null);
    setStatusMessage(null);
    setFileTree(null); // Clear the file tree
    setSelectedFile(null); // Close the file viewer
    if (pollInterval) clearInterval(pollInterval);
  };
  
  /**
   * Handles when a user clicks a file in the sidebar.
   */
  const handleFileClick = (path: string) => {
    console.log("Selected file:", path);
    setSelectedFile(path);
  };
  
  /**
   * Handles closing the file viewer.
   */
  const handleCloseViewer = () => {
    setSelectedFile(null);
  };

  /**
   * Handles when the user clicks the "Generate" button.
   */
  const handleGenerate = async () => {
    const file = uploadedFiles[0];
    if (!file) return;

    // 1. Reset UI
    setIsLoading(true);
    setStatusMessage('Uploading file...');
    setDownloadUrl(null);
    setError(null);
    setFileTree(null); // Clear previous results
    setSelectedFile(null); // Close file viewer
    if (pollInterval) clearInterval(pollInterval);

    try {
      // 2. Upload
      const { session_id } = await uploadAndProcessFile(file);
      setStatusMessage(`Processing... (Job ID: ${session_id})`);

      // 3. Start polling
      pollInterval = setInterval(async () => {
        try {
          const statusResult = await checkJobStatus(session_id);

          if (statusResult.status === 'complete') {
            // 4. Job is done!
            if (pollInterval) clearInterval(pollInterval);
            setIsLoading(false);
            setStatusMessage(`Processing complete!`);
            setDownloadUrl(getDownloadUrl(session_id));
            
            // --- NEW: Fetch the file tree ---
            if (statusResult.tree_url) {
              try {
                const treeResponse = await fetch(`${API_BASE_URL}${statusResult.tree_url}`);
                const treeData = await treeResponse.json();
                setFileTree(treeData); // <-- SET THE FILE TREE STATE
              } catch (treeError) {
                console.error("Failed to fetch file tree:", treeError);
                setError("Processing complete, but failed to load results tree.");
              }
            }
            
          } else {
            setStatusMessage(`Processing... (Job ID: ${session_id})`);
          }
        } catch (pollError) {
          if (pollInterval) clearInterval(pollInterval);
          setIsLoading(false);
          setError('Error checking job status. Please try again.');
          console.error(pollError);
        }
      }, 5000); // Poll every 5 seconds

    } catch (uploadError: any) {
      console.error(uploadError);
      setIsLoading(false);
      setError(`Upload failed: ${uploadError.message}`);
    }
  };

  return (
    <div className="flex h-screen bg-gray-900 text-white">
      <Sidebar 
        fileTree={fileTree} 
        onFileClick={handleFileClick} 
      />
      <MainContent
        uploadedFiles={uploadedFiles}
        onFilesChange={handleFilesChange}
        onGenerate={handleGenerate}
        isLoading={isLoading}
        error={error}
        statusMessage={statusMessage}
        downloadUrl={downloadUrl}
        // --- PASS NEW PROPS ---
        selectedFile={selectedFile}
        onCloseViewer={handleCloseViewer}
      />
    </div>
  );
}

export default App;