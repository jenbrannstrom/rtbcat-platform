/**
 * Chunked Uploader for Large CSV Files
 *
 * Streams large CSV files in chunks to avoid browser memory issues.
 * Uploads file bytes to the server, which handles parsing and import.
 *
 * Features:
 * - Streams file in 4MB chunks
 * - Server-side CSV parsing for consistent schema handling
 * - Supports cancellation via AbortController
 * - Reports progress during upload
 */

import Papa from "papaparse";
import type { ImportResponse } from "@/lib/types/import";

// Constants
const CHUNK_SIZE = 1 * 1024 * 1024; // 1MB chunks (safer for proxy limits)
const API_BASE = "/api";

// Types
export interface UploadProgress {
  status: "uploading" | "processing" | "completed" | "error" | "cancelled";
  bytesSent: number;
  totalBytes: number;
  chunksSent: number;
  totalChunks: number;
  progress: number; // 0-100
  currentPhase: string;
  errors: UploadError[];
}

export interface UploadError {
  row?: number;
  batch?: number;
  field?: string;
  error: string;
  value?: unknown;
}

export interface ChunkedUploaderOptions {
  onProgress?: (progress: UploadProgress) => void;
  signal?: AbortSignal;
  filename?: string;  // Original filename for tracking
}

/**
 * Normalize column name for matching
 */
function normalizeColumnName(name: string): string {
  return name
    .replace(/^#/, "")
    .replace(/\s+/g, "_")
    .replace(/[()]/g, "")
    .toLowerCase()
    .trim();
}

const COLUMN_VARIATIONS: Record<string, string[]> = {
  creative_id: ["creative_id", "creativeid", "creative"],
  date: ["date", "day", "metric_date"],
  impressions: ["impressions"],
  clicks: ["clicks"],
  spend: ["spend", "spend_buyer_currency"],
  geography: ["geography", "country"],
  device_type: ["device_type", "devicetype", "device"],
  campaign_id: ["campaign_id", "campaignid"],
  app_id: ["app_id", "appid"],
  billing_id: ["billing_id", "billingid", "buyer_account_id"],
};

function detectColumnMappings(headers: string[]): Record<string, string> {
  const mappings: Record<string, string> = {};
  const normalizedHeaders: Record<string, string> = {};

  headers.forEach((header) => {
    normalizedHeaders[normalizeColumnName(header)] = header;
  });

  for (const [targetCol, variations] of Object.entries(COLUMN_VARIATIONS)) {
    for (const variation of variations) {
      if (normalizedHeaders[variation]) {
        mappings[targetCol] = normalizedHeaders[variation];
        break;
      }
    }
  }

  return mappings;
}

/**
 * Estimate total rows from file size
 */
function estimateRowCount(fileSize: number): number {
  // Average row size is ~100 bytes
  const avgRowSize = 100;
  return Math.ceil(fileSize / avgRowSize);
}

async function startUpload(file: File): Promise<{ upload_id: string }> {
  const response = await fetch(`${API_BASE}/performance/import/stream/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      filename: file.name,
      file_size_bytes: file.size,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    const errorDetail = error.detail || error.error || error.message;
    throw new Error(errorDetail || `Failed to start upload (HTTP ${response.status})`);
  }

  return response.json();
}

async function uploadChunk(params: {
  uploadId: string;
  chunk: Blob;
  chunkIndex: number;
  totalChunks: number;
  signal?: AbortSignal;
}): Promise<{ bytes_received: number }> {
  const formData = new FormData();
  formData.append("upload_id", params.uploadId);
  formData.append("chunk_index", String(params.chunkIndex));
  formData.append("total_chunks", String(params.totalChunks));
  formData.append("chunk", params.chunk, `chunk-${params.chunkIndex}`);

  const response = await fetch(`${API_BASE}/performance/import/stream/chunk`, {
    method: "POST",
    body: formData,
    signal: params.signal,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    const errorDetail = error.detail || error.error || error.message;
    throw new Error(errorDetail || `Chunk upload failed (HTTP ${response.status})`);
  }

  return response.json();
}

async function completeUpload(uploadId: string): Promise<ImportResponse> {
  const response = await fetch(`${API_BASE}/performance/import/stream/complete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ upload_id: uploadId }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    const errorDetail = error.detail || error.error || error.message;
    throw new Error(errorDetail || `Failed to finalize upload (HTTP ${response.status})`);
  }

  const apiResult = await response.json();
  return {
    ...apiResult,
    imported: apiResult.rows_imported ?? apiResult.imported,
    duplicates: apiResult.rows_duplicate ?? apiResult.duplicates,
    total_spend: apiResult.total_spend_usd ?? apiResult.total_spend,
  };
}

/**
 * Upload large CSV file using chunked streaming
 */
export async function uploadChunkedCSV(
  file: File,
  options: ChunkedUploaderOptions = {}
): Promise<ImportResponse> {
  const { onProgress, signal } = options;
  const totalChunks = Math.ceil(file.size / CHUNK_SIZE);
  const start = await startUpload(file);
  let bytesSent = 0;
  let chunksSent = 0;

  for (let chunkIndex = 0; chunkIndex < totalChunks; chunkIndex += 1) {
    if (signal?.aborted) {
      throw new Error("Upload cancelled");
    }

    const startByte = chunkIndex * CHUNK_SIZE;
    const endByte = Math.min(startByte + CHUNK_SIZE, file.size);
    const chunk = file.slice(startByte, endByte);

    await uploadChunk({
      uploadId: start.upload_id,
      chunk,
      chunkIndex,
      totalChunks,
      signal,
    });

    bytesSent += chunk.size;
    chunksSent += 1;

    if (onProgress) {
      const progress = Math.min(99, Math.round((bytesSent / file.size) * 100));
      onProgress({
        status: "uploading",
        bytesSent,
        totalBytes: file.size,
        chunksSent,
        totalChunks,
        progress,
        currentPhase: `Uploading chunk ${chunksSent}/${totalChunks}`,
        errors: [],
      });
    }
  }

  if (onProgress) {
    onProgress({
      status: "processing",
      bytesSent,
      totalBytes: file.size,
      chunksSent,
      totalChunks,
      progress: 99,
      currentPhase: "Processing on server",
      errors: [],
    });
  }

  const result = await completeUpload(start.upload_id);

  if (onProgress) {
    onProgress({
      status: "completed",
      bytesSent,
      totalBytes: file.size,
      chunksSent,
      totalChunks,
      progress: 100,
      currentPhase: "Complete",
      errors: [],
    });
  }

  return result;
}

/**
 * Quick preview of CSV file (first 10 rows)
 */
export async function previewCSV(
  file: File,
  maxRows = 10
): Promise<{
  headers: string[];
  rows: Record<string, string>[];
  columnMappings: Record<string, string>;
  estimatedRowCount: number;
}> {
  return new Promise((resolve, reject) => {
    const rows: Record<string, string>[] = [];
    let headers: string[] = [];
    let columnMappings: Record<string, string> = {};

    Papa.parse<Record<string, string>>(file, {
      header: true,
      skipEmptyLines: true,
      preview: maxRows + 1, // +1 for header
      complete: (results) => {
        headers = results.meta.fields || [];
        columnMappings = detectColumnMappings(headers);
        rows.push(...results.data);

        resolve({
          headers,
          rows,
          columnMappings,
          estimatedRowCount: estimateRowCount(file.size),
        });
      },
      error: (err) => {
        reject(new Error(`CSV preview error: ${err.message}`));
      },
    });
  });
}
