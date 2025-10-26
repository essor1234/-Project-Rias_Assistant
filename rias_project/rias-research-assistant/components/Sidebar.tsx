// components/Sidebar.tsx

import React, { useState } from 'react';
import { FileTree } from '../types'; // Import our type
import { SparklesIcon, FolderIcon, ChevronRightIcon, ChevronDownIcon, FileIcon } from './icons/Icons';

// Props for the main Sidebar
interface SidebarProps {
  fileTree: FileTree[] | null; // The tree is an array of root nodes
  onFileClick: (path: string) => void;
}

// Props for the recursive rendering component
interface FileTreeNodeProps {
  node: FileTree;
  onFileClick: (path: string) => void;
  level: number; // For indentation
}

/**
 * A recursive component to render a single node (file or folder) in the tree.
 */
const FileTreeNode: React.FC<FileTreeNodeProps> = ({ node, onFileClick, level }) => {
  const [isOpen, setIsOpen] = useState(false);
  const indentStyle = { paddingLeft: `${level * 16}px` };

  if (node.type === 'folder') {
    return (
      <div className="text-gray-300">
        <div
          className="flex items-center p-1.5 cursor-pointer hover:bg-gray-700 rounded"
          style={indentStyle}
          onClick={() => setIsOpen(!isOpen)}
        >
          {isOpen ? (
            <ChevronDownIcon className="h-4 w-4 mr-1.5 flex-shrink-0" />
          ) : (
            <ChevronRightIcon className="h-4 w-4 mr-1.5 flex-shrink-0" />
          )}
          <FolderIcon className="h-5 w-5 mr-2 text-pink-400 flex-shrink-0" />
          <span className="truncate" title={node.name}>{node.name}</span>
        </div>
        {isOpen && node.children && (
          <div className="border-l border-gray-600 ml-3">
            {node.children.map((child, index) => (
              <FileTreeNode
                key={child.name + index}
                node={child}
                onFileClick={onFileClick}
                level={level + 1}
              />
            ))}
          </div>
        )}
      </div>
    );
  }

  // It's a file
  return (
    <div
      className="flex items-center p-1.5 cursor-pointer hover:bg-gray-700 rounded"
      style={indentStyle}
      onClick={() => onFileClick(node.path!)} // path is guaranteed for files
    >
      <FileIcon className="h-5 w-5 mr-2 text-gray-400 flex-shrink-0 ml-1.5" />
      <span className="truncate" title={node.name}>{node.name}</span>
    </div>
  );
};

/**
 * The main Sidebar component.
 */
export const Sidebar: React.FC<SidebarProps> = ({ fileTree, onFileClick }) => {
  return (
    <div className="w-72 bg-gray-800 p-4 overflow-y-auto h-full flex-shrink-0 border-r border-white/10">
      <h2 className="text-lg font-semibold mb-4 text-white flex items-center">
        <SparklesIcon className="h-6 w-6 mr-2 text-pink-400" />
        Results Explorer
      </h2>
      <div className="border-t border-white/10 pt-4">
        {fileTree && fileTree.length > 0 ? (
          fileTree.map((node, index) => (
            <FileTreeNode
              key={node.name + index}
              node={node}
              onFileClick={onFileClick}
              level={0}
            />
          ))
        ) : (
          <p className="text-gray-500 text-sm">
            No results yet. Upload a file and click 'Generate' to see outputs.
          </p>
        )}
      </div>
    </div>
  );
};