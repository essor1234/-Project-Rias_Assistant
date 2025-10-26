import { GeneratedFile, FileType, TreeNode } from '../types';
import JSZip from 'jszip';
import saveAs from 'file-saver';

const convertXlsxToCsv = (data: string[][]): string => {
  return data.map(row => 
    row.map(cell => `"${(cell ?? '').toString().replace(/"/g, '""')}"`).join(',')
  ).join('\n');
};

const convertPptxToText = (slides: { title: string; content: string }[]): string => {
  return slides.map((slide, index) => 
    `Slide ${index + 1}: ${slide.title}\n${slide.content}\n\n`
  ).join('----------------------------------------\n');
};

const addNodeToZip = (zip: JSZip, node: TreeNode) => {
  if (node.type === 'folder') {
    const folder = zip.folder(node.name);
    if (folder && node.children) {
      node.children.forEach(child => addNodeToZip(folder, child));
    }
  } else if (node.type === 'file' && node.fileData) {
    const file = node.fileData;
    let content: string | Blob = '';
    let fileName = file.name;

    switch (file.type) {
      case FileType.DOCX:
        // Saving HTML content directly
        fileName = fileName.replace('.docx', '.html');
        content = file.content as string;
        break;
      case FileType.PPTX:
        // Convert presentation to a simple text file
        fileName = fileName.replace('.pptx', '.txt');
        content = convertPptxToText(file.content as { title: string; content: string }[]);
        break;
      case FileType.XLSX:
        // Convert spreadsheet data to a CSV file
        fileName = fileName.replace('.xlsx', '.csv');
        content = convertXlsxToCsv(file.content as string[][]);
        break;
    }
    zip.file(fileName, content);
  }
};

export const downloadResultsAsZip = async (tree: TreeNode[]) => {
  const zip = new JSZip();
  
  tree.forEach(node => {
    addNodeToZip(zip, node);
  });

  const content = await zip.generateAsync({ type: 'blob' });
  saveAs(content, 'Rias_Research_Results.zip');
};
