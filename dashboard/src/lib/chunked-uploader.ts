/**
 * Chunked Uploader for Large CSV Files
 *
 * Streams large CSV files in chunks to avoid browser memory issues.
 * Uses the browser's ReadableStream API to process files without
 * loading the entire file into memory.
 *
 * Features:
 * - Streams file in 1MB chunks
 * - Parses CSV on-the-fly
 * - Sends batches of 10,000 rows to server
 * - Supports cancellation via AbortController
 * - Reports progress during upload
 */

import Papa from "papaparse";

// Constants
const CHUNK_SIZE = 1024 * 1024; // 1MB chunks
const BATCH_SIZE = 10000; // Rows per API call
const API_BASE = "/api";

// Types
export interface UploadProgress {
  status: "parsing" | "uploading" | "completed" | "error" | "cancelled";
  rowsProcessed: number;
  rowsImported: number;
  rowsSkipped: number;
  batchesSent: number;
  totalEstimatedRows: number;
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

export interface UploadResult {
  success: boolean;
  imported: number;
  skipped: number;
  batches: number;
  errors: UploadError[];
  dateRange?: { start: string; end: string };
  totalSpend?: number;
}

export interface ChunkedUploaderOptions {
  onProgress?: (progress: UploadProgress) => void;
  signal?: AbortSignal;
  columnMappings?: Record<string, string>;
  filename?: string;  // Original filename for tracking
}

// Column name variations for auto-detection
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

/**
 * Parse date from various formats to YYYY-MM-DD
 */
function parseDate(dateStr: string): string {
  if (!dateStr) return "";

  // Already YYYY-MM-DD
  if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
    return dateStr;
  }

  // MM/DD/YY or MM/DD/YYYY
  if (dateStr.includes("/")) {
    const parts = dateStr.split("/");
    if (parts.length === 3) {
      const [month, day, year] = parts;
      const fullYear = year.length === 2 ? `20${year}` : year;
      return `${fullYear}-${month.padStart(2, "0")}-${day.padStart(2, "0")}`;
    }
  }

  return dateStr;
}

/**
 * Parse spend value (remove $, commas)
 */
function parseSpend(value: string | number | undefined): number {
  if (value === undefined || value === null || value === "") return 0;
  const str = String(value).replace(/[$,]/g, "").trim();
  const num = parseFloat(str);
  return isNaN(num) ? 0 : num;
}

/**
 * Parse integer value
 */
function parseInt2(value: string | number | undefined): number {
  if (value === undefined || value === null || value === "") return 0;
  const str = String(value).replace(/,/g, "").trim();
  const num = parseInt(str, 10);
  return isNaN(num) ? 0 : num;
}

/**
 * Detect column mappings from header row
 */
function detectColumnMappings(headers: string[]): Record<string, string> {
  const mappings: Record<string, string> = {};
  const normalizedHeaders: Record<string, string> = {};

  // Normalize all headers
  headers.forEach((header) => {
    normalizedHeaders[normalizeColumnName(header)] = header;
  });

  // Find mappings for each target column
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
 * Transform raw CSV row to normalized format
 */
function transformRow(
  row: Record<string, string>,
  mappings: Record<string, string>
): Record<string, unknown> | null {
  // Get mapped values
  const creativeId = row[mappings.creative_id];
  const date = row[mappings.date];

  // Skip rows without required fields
  if (!creativeId || !date) {
    return null;
  }

  return {
    creative_id: creativeId,
    date: parseDate(date),
    impressions: parseInt2(row[mappings.impressions]),
    clicks: parseInt2(row[mappings.clicks]),
    spend: parseSpend(row[mappings.spend]),
    geography: row[mappings.geography]?.toUpperCase() || undefined,
    device_type: row[mappings.device_type]?.toUpperCase() || undefined,
    campaign_id: row[mappings.campaign_id] || undefined,
    app_id: row[mappings.app_id] || undefined,
    billing_id: row[mappings.billing_id] || undefined,
  };
}

/**
 * Send batch to server
 */
async function sendBatch(
  rows: Record<string, unknown>[],
  signal?: AbortSignal
): Promise<{ imported: number; errors: UploadError[] }> {
  const response = await fetch(`${API_BASE}/performance/import/batch`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ rows }),
    signal,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `Import failed: ${response.status}`);
  }

  const result = await response.json();
  return {
    imported: result.imported || 0,
    errors: result.errors || [],
  };
}

/**
 * Estimate total rows from file size
 */
function estimateRowCount(fileSize: number): number {
  // Average row size is ~100 bytes
  const avgRowSize = 100;
  return Math.ceil(fileSize / avgRowSize);
}

/**
 * Generate a unique batch ID
 */
function generateBatchId(): string {
  return `batch-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
}

/**
 * Finalize import and record in history
 */
async function finalizeImport(params: {
  batchId: string;
  filename: string;
  fileSize: number;
  rowsRead: number;
  rowsImported: number;
  rowsSkipped: number;
  dateRangeStart?: string;
  dateRangeEnd?: string;
  totalSpend: number;
}): Promise<void> {
  try {
    await fetch(`${API_BASE}/performance/import/finalize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        batch_id: params.batchId,
        filename: params.filename,
        file_size_bytes: params.fileSize,
        rows_read: params.rowsRead,
        rows_imported: params.rowsImported,
        rows_skipped: params.rowsSkipped,
        rows_duplicate: 0,
        date_range_start: params.dateRangeStart,
        date_range_end: params.dateRangeEnd,
        total_spend_usd: params.totalSpend,
        total_impressions: 0,
        total_reached: 0,
      }),
    });
  } catch (err) {
    console.warn("Failed to finalize import:", err);
  }
}

/**
 * Upload large CSV file using chunked streaming
 */
export async function uploadChunkedCSV(
  file: File,
  options: ChunkedUploaderOptions = {}
): Promise<UploadResult> {
  const { onProgress, signal, filename } = options;
  const batchId = generateBatchId();

  let rowsProcessed = 0;
  let rowsImported = 0;
  let rowsSkipped = 0;
  let batchesSent = 0;
  const errors: UploadError[] = [];
  let minDate: string | undefined;
  let maxDate: string | undefined;
  let totalSpend = 0;

  const totalEstimatedRows = estimateRowCount(file.size);
  let currentBatch: Record<string, unknown>[] = [];
  let columnMappings: Record<string, string> | null = null;
  let headersParsed = false;

  const reportProgress = (
    status: UploadProgress["status"],
    phase: string
  ) => {
    if (onProgress) {
      const progress = Math.min(
        99,
        Math.round((rowsProcessed / totalEstimatedRows) * 100)
      );
      onProgress({
        status,
        rowsProcessed,
        rowsImported,
        rowsSkipped,
        batchesSent,
        totalEstimatedRows,
        progress,
        currentPhase: phase,
        errors: errors.slice(0, 50),
      });
    }
  };

  return new Promise((resolve, reject) => {
    // Check for cancellation
    if (signal?.aborted) {
      reject(new Error("Upload cancelled"));
      return;
    }

    // Setup abort handler
    const abortHandler = () => {
      reject(new Error("Upload cancelled"));
    };
    signal?.addEventListener("abort", abortHandler);

    Papa.parse<Record<string, string>>(file, {
      header: true,
      skipEmptyLines: true,
      chunk: async (results, parser) => {
        // Pause parser while processing
        parser.pause();

        try {
          // Check for cancellation
          if (signal?.aborted) {
            parser.abort();
            return;
          }

          // Detect column mappings from first chunk
          if (!headersParsed && results.meta.fields) {
            columnMappings = detectColumnMappings(results.meta.fields);
            headersParsed = true;

            // Validate required columns detected
            if (!columnMappings.creative_id || !columnMappings.date) {
              throw new Error(
                `Missing required columns. Found: ${results.meta.fields.join(", ")}`
              );
            }
          }

          if (!columnMappings) {
            throw new Error("Failed to parse CSV headers");
          }

          // Transform rows
          for (const row of results.data) {
            const transformed = transformRow(row, columnMappings);

            if (transformed) {
              currentBatch.push(transformed);
              rowsProcessed++;

              // Track stats
              const date = transformed.date as string;
              if (date) {
                if (!minDate || date < minDate) minDate = date;
                if (!maxDate || date > maxDate) maxDate = date;
              }
              totalSpend += (transformed.spend as number) || 0;

              // Send batch when full
              if (currentBatch.length >= BATCH_SIZE) {
                reportProgress("uploading", `Sending batch ${batchesSent + 1}`);

                try {
                  const result = await sendBatch(currentBatch, signal);
                  rowsImported += result.imported;
                  errors.push(...result.errors);
                  batchesSent++;
                } catch (err) {
                  // On batch failure, count as skipped but continue
                  rowsSkipped += currentBatch.length;
                  errors.push({
                    batch: batchesSent + 1,
                    error: err instanceof Error ? err.message : "Batch failed",
                  });
                  batchesSent++;
                }

                currentBatch = [];
              }
            } else {
              rowsSkipped++;
            }
          }

          reportProgress("parsing", `Processed ${rowsProcessed} rows`);

          // Resume parser
          parser.resume();
        } catch (err) {
          parser.abort();
          reject(err);
        }
      },
      complete: async () => {
        try {
          // Send remaining batch
          if (currentBatch.length > 0) {
            reportProgress("uploading", `Sending final batch`);

            try {
              const result = await sendBatch(currentBatch, signal);
              rowsImported += result.imported;
              errors.push(...result.errors);
              batchesSent++;
            } catch (err) {
              rowsSkipped += currentBatch.length;
              errors.push({
                batch: batchesSent + 1,
                error: err instanceof Error ? err.message : "Final batch failed",
              });
            }
          }

          // Finalize import and record in history
          await finalizeImport({
            batchId,
            filename: filename || file.name,
            fileSize: file.size,
            rowsRead: rowsProcessed,
            rowsImported,
            rowsSkipped,
            dateRangeStart: minDate,
            dateRangeEnd: maxDate,
            totalSpend,
          });

          // Report completion
          if (onProgress) {
            onProgress({
              status: "completed",
              rowsProcessed,
              rowsImported,
              rowsSkipped,
              batchesSent,
              totalEstimatedRows: rowsProcessed,
              progress: 100,
              currentPhase: "Complete",
              errors: errors.slice(0, 50),
            });
          }

          signal?.removeEventListener("abort", abortHandler);

          resolve({
            success: errors.length === 0,
            imported: rowsImported,
            skipped: rowsSkipped,
            batches: batchesSent,
            errors: errors.slice(0, 50),
            dateRange: minDate && maxDate ? { start: minDate, end: maxDate } : undefined,
            totalSpend: totalSpend > 0 ? Math.round(totalSpend * 100) / 100 : undefined,
          });
        } catch (err) {
          reject(err);
        }
      },
      error: (err) => {
        signal?.removeEventListener("abort", abortHandler);
        reject(new Error(`CSV parsing error: ${err.message}`));
      },
    });
  });
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
