// components/FileViewer.tsx

import React from 'react';

interface FileViewerProps {
  filePath: string; // This will be the relative path, e.g., "sZ9ipF7G/test3/..."
  onClose: () => void;
}

// This is the base URL of our backend's static file server
const STATIC_BASE_URL = "http://localhost:8000" + '/static-results';

export const FileViewer: React.FC<FileViewerProps> = ({ filePath, onClose }) => {
  
  // Construct the full, direct URL to the file
  const fullFileUrl = `${STATIC_BASE_URL}/${filePath}`;

  let viewerUrl = '';
  const fileExtension = filePath.split('.').pop()?.toLowerCase();

  if (['docx', 'pptx', 'xlsx'].includes(fileExtension || '')) {
    // Use Microsoft Office Online viewer
    // We must URL-encode the fullFileUrl for it to work
    viewerUrl = `https://view.officeapps.live.com/op/embed.aspx?src=${encodeURIComponent(fullFileUrl)}`;
  } else if (fileExtension === 'pdf' || ['png', 'jpg', 'txt', 'json'].includes(fileExtension || '')) {
    // Most browsers can render these directly
    viewerUrl = fullFileUrl;
  } else {
    // For unsupported files, just show a download link
    return (
      <div className="p-4 h-full flex flex-col text-center justify-center items-center">
        <p className="mb-4 text-lg">
          This file type ({fileExtension}) cannot be previewed directly.
        </p>
        <a 
          href={fullFileUrl} 
          download 
          className="px-4 py-2 bg-pink-500 text-white font-bold rounded-lg hover:bg-pink-600"
        >
          Download {filePath.split('/').pop()}
        </a>
        <button onClick={onClose} className="mt-6 text-gray-400 hover:text-white">
          &larr; Back to Upload
        </button>
      </div>
    );
  }

  // Render the iframe for Office docs, PDFs, images, etc.
  return (
    <div className="h-full flex flex-col bg-gray-800">
      <div className="flex-shrink-0 p-2 flex justify-between items-center bg-gray-900 border-b border-white/10">
        <button onClick={onClose} className="px-3 py-1 bg-gray-700 rounded hover:bg-gray-600">
          &larr; Back
        </button>
        <span className="text-sm text-gray-400 truncate mx-4" title={filePath}>
          {filePath.split('/').pop()}
        </span>
        <a 
          href={fullFileUrl} 
          download 
          className="px-3 py-1 bg-pink-500 text-white font-bold rounded-lg hover:bg-pink-600"
        >
          Download
        </a>
      </div>
      <iframe
        src={viewerUrl}
        width="100%"
        height="100%"
        frameBorder="0"
        title="File Viewer"
        className="flex-grow bg-white"
      >
        This browser does not support iframes.
      </iframe>
    </div>
  );
};