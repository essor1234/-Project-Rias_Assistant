// src/services/generationService.ts

// Define the base URL of your FastAPI backend
const API_BASE_URL = "http://localhost:8000";

/**
 * Represents the status response from the /status/{session_id} endpoint.
 */
export interface JobStatus {
  tree_url: any;
  status: "processing" | "complete";
  session_id: string;
  result_url?: string; // This will be present when status is 'complete'
}

/**
 * Represents the initial upload response from the /upload-and-process/ endpoint.
 */
export interface UploadResponse {
  message: string;
  session_id: string;
  filename: string;
}

/**
 * Uploads a file to the backend and starts the processing pipeline.
 * Returns a session ID to poll for results.
 */
export async function uploadAndProcessFile(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  try {
    const response = await fetch(`${API_BASE_URL}/upload-and-process/`, {
      method: "POST",
      body: formData,
      // No 'Content-Type' header needed; 'fetch' sets it for FormData
    });

    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.detail || `HTTP error! status: ${response.status}`);
    }

    const result = await response.json();
    return result as UploadResponse;

  } catch (error) {
    console.error("Error uploading file:", error);
    throw error;
  }
}

/**
 * Polls the backend for the status of a processing job.
 */
export async function checkJobStatus(sessionId: string): Promise<JobStatus> {
  try {
    const response = await fetch(`${API_BASE_URL}/status/${sessionId}`, {
      method: "GET",
    });

    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.detail || `HTTP error! status: ${response.status}`);
    }

    const result = await response.json();
    return result as JobStatus;

  } catch (error) {
    console.error("Error checking status:", error);
    throw error;
  }
}

/**
 * Helper function to get the full download URL for a completed job.
 */
export function getDownloadUrl(sessionId: string): string {
  return `${API_BASE_URL}/download-result/${sessionId}`;
}