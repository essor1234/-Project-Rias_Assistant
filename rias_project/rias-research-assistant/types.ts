export enum FileType {
  DOCX = 'docx',
  PPTX = 'pptx',
  XLSX = 'xlsx',
}

export interface GeneratedFile {
  id: string; // Unique ID for selection tracking
  name: string;
  type: FileType;
  content: any; // Can be string (HTML for docx), object[] (for pptx), or string[][] (for xlsx)
}

export interface TreeNode {
  id: string;
  name: string;
  type: 'folder' | 'file';
  children?: TreeNode[];
  fileData?: GeneratedFile; // Only for 'file' type nodes
}

// types.ts

export interface FileTree {
  name: string;
  type: 'file' | 'folder';
  path?: string; // path is optional (only for files)
  children?: FileTree[]; // children is optional (only for folders)
}