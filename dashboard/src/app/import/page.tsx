"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  CheckCircle,
  XCircle,
  ArrowRight,
  AlertTriangle,
  ChevronDown,
} from "lucide-react";
import { ImportDropzone } from "@/components/import-dropzone";
import { ImportPreview } from "@/components/import-preview";
import { ImportProgress } from "@/components/import-progress";
import { ValidationErrors } from "@/components/validation-errors";
import {
  ExportInstructions,
  RequiredColumnsTable,
  TroubleshootingSection,
  ColumnMappingCard,
  ImportResultCard,
  ImportHistorySection,
} from "@/components/import";
import {
  validatePerformanceCSV,
  type ExtendedValidationResult,
  groupAnomaliesByType,
  getTopAnomalyApps,
  formatAnomalyType,
} from "@/lib/csv-validator";
import type { AnomalyType } from "@/lib/types/import";
import { parseCSV } from "@/lib/csv-parser";
import { importPerformanceData, getImportHistory, type ImportHistoryItem } from "@/lib/api";
import {
  uploadChunkedCSV,
  previewCSV,
  type UploadProgress,
} from "@/lib/chunked-uploader";
import { extractSeatFromPreview, formatSeatInfo, type SeatInfo } from "@/lib/seat-extractor";
import type { ImportResponse } from "@/lib/types/import";

type ImportStep = "upload" | "preview" | "importing" | "success" | "error";

// Threshold for using chunked upload (5MB)
const CHUNKED_UPLOAD_THRESHOLD = 5 * 1024 * 1024;

export default function ImportPage() {
  const router = useRouter();
  const abortControllerRef = useRef<AbortController | null>(null);

  const [step, setStep] = useState<ImportStep>("upload");
  const [file, setFile] = useState<File | null>(null);
  const [validationResult, setValidationResult] =
    useState<ExtendedValidationResult | null>(null);
  const [importResult, setImportResult] = useState<ImportResponse | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isLargeFile, setIsLargeFile] = useState(false);
  const [chunkedProgress, setChunkedProgress] = useState<UploadProgress | null>(null);
  const [seatInfo, setSeatInfo] = useState<SeatInfo | null>(null);
  const [previewData, setPreviewData] = useState<{
    headers: string[];
    rows: Record<string, string>[];
    columnMappings: Record<string, string>;
    estimatedRowCount: number;
  } | null>(null);

  // Import history state
  const [importHistory, setImportHistory] = useState<ImportHistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);

  // Load import history on mount and after successful imports
  const loadHistory = useCallback(async () => {
    try {
      const history = await getImportHistory(10);
      setImportHistory(history);
    } catch (error) {
      console.error("Failed to load import history:", error);
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  // Handle file selection
  const handleFileSelect = async (selectedFile: File) => {
    setFile(selectedFile);
    setStep("preview");
    setIsLargeFile(selectedFile.size > CHUNKED_UPLOAD_THRESHOLD);

    try {
      if (selectedFile.size > CHUNKED_UPLOAD_THRESHOLD) {
        // Large file: use quick preview instead of full parse
        const preview = await previewCSV(selectedFile, 10);
        setPreviewData(preview);

        // Extract seat info from preview rows
        const seat = extractSeatFromPreview(preview.rows);
        setSeatInfo(seat);

        // Create a mock validation result for preview
        const hasRequiredCols = !!(preview.columnMappings.creative_id && preview.columnMappings.date);
        setValidationResult({
          valid: hasRequiredCols,
          errors: hasRequiredCols ? [] : [{
            row: 0,
            field: "columns",
            error: `Missing required columns. Detected: ${Object.entries(preview.columnMappings)
              .filter(([, v]) => v)
              .map(([k, v]) => `${v} → ${k}`)
              .join(", ") || "none"}`,
            value: null,
          }],
          warnings: [],
          anomalies: [],
          rowCount: preview.estimatedRowCount,
          data: [],
          detectedColumns: preview.columnMappings,
          hasHourlyData: preview.headers.some(h => h.toLowerCase().includes("hour")),
        });
      } else {
        // Small file: full parse and validate
        const parseResult = await parseCSV(selectedFile);
        const validation = validatePerformanceCSV(parseResult);
        setValidationResult(validation);
      }
    } catch (error) {
      console.error("CSV parsing error:", error);
      setValidationResult({
        valid: false,
        errors: [
          {
            row: 0,
            field: "file",
            error: "Failed to parse CSV file. Please check the file format.",
            value: null,
          },
        ],
        warnings: [],
        anomalies: [],
        rowCount: 0,
        data: [],
      });
    }
  };

  // Handle chunked upload progress
  const handleChunkedProgress = useCallback((progress: UploadProgress) => {
    setChunkedProgress(progress);
    setUploadProgress(progress.progress);
  }, []);

  // Handle import
  const handleImport = async () => {
    if (!file) return;

    setStep("importing");
    setUploadProgress(0);
    setChunkedProgress(null);

    // Create abort controller for cancellation
    abortControllerRef.current = new AbortController();

    try {
      if (isLargeFile) {
        // Use chunked upload for large files
        const result = await uploadChunkedCSV(file, {
          onProgress: handleChunkedProgress,
          signal: abortControllerRef.current.signal,
        });

        setImportResult(result);
        const imported = result.imported ?? result.rows_imported ?? 0;
        const duplicates = result.duplicates ?? result.rows_duplicate ?? 0;
        setStep(result.success || imported > 0 || duplicates > 0 ? "success" : "error");
        if (result.success || imported > 0 || duplicates > 0) {
          loadHistory(); // Reload history after successful import
        }
      } else {
        // Use standard upload for small files
        const result = await importPerformanceData(file, (progress) => {
          setUploadProgress(progress);
        });

        setImportResult(result);
        setStep("success");
        loadHistory(); // Reload history after successful import
      }
    } catch (error) {
      console.error("Import error:", error);
      const errorMessage = error instanceof Error ? error.message : "Import failed";

      if (errorMessage === "Upload cancelled") {
        setStep("upload");
        return;
      }

      setImportResult({
        success: false,
        imported: 0,
        error: errorMessage,
      });
      setStep("error");
    } finally {
      abortControllerRef.current = null;
    }
  };

  // Handle cancel
  const handleCancel = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    resetForm();
  };

  const resetForm = () => {
    setFile(null);
    setValidationResult(null);
    setImportResult(null);
    setUploadProgress(0);
    setIsLargeFile(false);
    setChunkedProgress(null);
    setPreviewData(null);
    setSeatInfo(null);
    setStep("upload");
  };

  // Format file size
  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">
          Import Performance Data
        </h1>
        <p className="text-gray-600 mt-1">
          Upload CSV exports from Google Authorized Buyers
        </p>
      </div>

      {/* Upload Step */}
      {step === "upload" && (
        <div className="space-y-6">
          {/* Main Upload Area */}
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <ImportDropzone onFileSelect={handleFileSelect} maxSizeMB={500} />
          </div>

          {/* Collapsible Instructions */}
          <details className="bg-white rounded-lg border border-gray-200">
            <summary className="p-4 cursor-pointer hover:bg-gray-50 font-medium text-gray-900 flex items-center justify-between">
              <span>How to export from Google Authorized Buyers</span>
              <ChevronDown className="h-5 w-5 text-gray-500" />
            </summary>
            <div className="p-4 pt-0 border-t border-gray-200">
              <ExportInstructions />
            </div>
          </details>

          {/* Collapsible Required Columns */}
          <details className="bg-white rounded-lg border border-gray-200">
            <summary className="p-4 cursor-pointer hover:bg-gray-50 font-medium text-gray-900 flex items-center justify-between">
              <span>Required columns</span>
              <ChevronDown className="h-5 w-5 text-gray-500" />
            </summary>
            <div className="p-4 pt-0 border-t border-gray-200">
              <RequiredColumnsTable />
            </div>
          </details>

          {/* Collapsible Troubleshooting */}
          <details className="bg-white rounded-lg border border-gray-200">
            <summary className="p-4 cursor-pointer hover:bg-gray-50 font-medium text-gray-900 flex items-center justify-between">
              <span>Troubleshooting large files</span>
              <ChevronDown className="h-5 w-5 text-gray-500" />
            </summary>
            <div className="p-4 pt-0 border-t border-gray-200">
              <TroubleshootingSection />
            </div>
          </details>

          {/* Recent Import History */}
          <ImportHistorySection
            history={importHistory}
            loading={historyLoading}
            onRefresh={loadHistory}
          />
        </div>
      )}

      {/* Preview Step */}
      {step === "preview" && validationResult && (
        <div className="space-y-6">
          {/* File Info */}
          <div className="bg-gray-50 rounded-lg p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium text-gray-900">{file?.name}</p>
                <p className="text-sm text-gray-600">
                  {formatFileSize(file?.size || 0)} ·{" "}
                  {isLargeFile ? (
                    <span>~{validationResult.rowCount.toLocaleString()} rows (estimated)</span>
                  ) : (
                    <span>{validationResult.rowCount.toLocaleString()} rows</span>
                  )}
                  {validationResult.aggregatedFromRows && (
                    <span className="text-blue-600">
                      {" "}(aggregated from {validationResult.aggregatedFromRows} hourly rows)
                    </span>
                  )}
                </p>
              </div>
              <button
                onClick={resetForm}
                className="text-sm text-gray-600 hover:text-gray-800"
              >
                Remove
              </button>
            </div>
          </div>

          {/* Seat Info */}
          {seatInfo && (
            <div className="bg-green-50 border border-green-200 rounded-lg p-4">
              <div className="flex items-start gap-2">
                <CheckCircle className="h-5 w-5 text-green-600 mt-0.5" />
                <div>
                  <p className="font-medium text-green-900">Seat detected</p>
                  <p className="text-sm text-green-800 mt-1">
                    {formatSeatInfo(seatInfo)}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Large File Warning */}
          {isLargeFile && (
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
              <div className="flex items-start gap-2">
                <AlertTriangle className="h-5 w-5 text-yellow-600 mt-0.5" />
                <div>
                  <p className="font-medium text-yellow-900">Large file detected</p>
                  <p className="text-sm text-yellow-800 mt-1">
                    This file will be uploaded using streaming mode to avoid browser memory issues.
                    Progress will be shown during upload.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Column Detection Info */}
          {validationResult.detectedColumns && validationResult.valid && (
            <ColumnMappingCard columns={validationResult.detectedColumns} />
          )}

          {/* Fatal Errors (only shown if file is unparseable) */}
          {!validationResult.valid && validationResult.errors.length > 0 && (
            <ValidationErrors errors={validationResult.errors} />
          )}

          {/* Anomalies - Interesting fraud signals, not blocking */}
          {validationResult.valid && validationResult.anomalies && validationResult.anomalies.length > 0 && (
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
              <h3 className="font-semibold text-yellow-800 mb-2 flex items-center gap-2">
                <AlertTriangle className="h-5 w-5" />
                {validationResult.anomalies.length} Anomalies Detected
              </h3>
              <p className="text-sm text-yellow-700 mb-3">
                These patterns may indicate fraud or tracking issues.
                Data will be imported and flagged for analysis.
              </p>

              {/* Group anomalies by type */}
              <div className="space-y-1 text-sm">
                {Object.entries(groupAnomaliesByType(validationResult.anomalies)).map(([type, items]) => (
                  <div key={type} className="flex justify-between py-1 border-b border-yellow-200 last:border-0">
                    <span className="text-yellow-800">{formatAnomalyType(type as AnomalyType)}</span>
                    <span className="font-medium text-yellow-900">{items.length} rows</span>
                  </div>
                ))}
              </div>

              {/* Expand to see affected apps */}
              {getTopAnomalyApps(validationResult.anomalies, 5).length > 0 && (
                <details className="mt-3">
                  <summary className="text-sm text-yellow-600 cursor-pointer hover:text-yellow-800">
                    View affected apps
                  </summary>
                  <ul className="mt-2 text-xs space-y-1 text-yellow-700">
                    {getTopAnomalyApps(validationResult.anomalies, 5).map((app, i) => (
                      <li key={i} className="flex justify-between">
                        <span>{app.app_name || "Unknown app"}</span>
                        <span className="font-medium">{app.count} anomalies</span>
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </div>
          )}

          {/* Warnings - Informational (collapsible) */}
          {validationResult.valid && validationResult.warnings && validationResult.warnings.length > 0 && (
            <details className="bg-gray-50 border rounded-lg p-4">
              <summary className="text-sm text-gray-600 cursor-pointer hover:text-gray-800">
                {validationResult.warnings.length} warnings (click to expand)
              </summary>
              <ul className="mt-3 text-xs text-gray-600 max-h-40 overflow-y-auto space-y-1">
                {validationResult.warnings.slice(0, 50).map((w, i) => (
                  <li key={i} className={w.severity === "warning" ? "text-yellow-700" : "text-gray-500"}>
                    Row {w.row}: {w.message}
                  </li>
                ))}
                {validationResult.warnings.length > 50 && (
                  <li className="text-gray-500 italic">
                    ... and {validationResult.warnings.length - 50} more
                  </li>
                )}
              </ul>
            </details>
          )}

          {/* Preview */}
          {validationResult.valid && (
            <>
              {isLargeFile && previewData ? (
                // Large file preview from quick scan
                <div className="border rounded-lg overflow-hidden">
                  <div className="bg-gray-50 px-4 py-2 border-b">
                    <p className="text-sm font-medium text-gray-700">
                      Preview (first 10 rows)
                    </p>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                      <thead className="bg-gray-50">
                        <tr>
                          {previewData.headers.slice(0, 6).map((header) => (
                            <th
                              key={header}
                              className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase"
                            >
                              {header}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-gray-200">
                        {previewData.rows.map((row, i) => (
                          <tr key={i}>
                            {previewData.headers.slice(0, 6).map((header) => (
                              <td
                                key={header}
                                className="px-4 py-2 text-sm text-gray-900 whitespace-nowrap"
                              >
                                {row[header]}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : (
                // Small file preview from full parse
                <>
                  <ImportPreview data={validationResult.data.slice(0, 10)} />
                  {validationResult.data.length > 10 && (
                    <p className="text-sm text-gray-600 text-center">
                      Showing first 10 of {validationResult.data.length} rows
                    </p>
                  )}
                </>
              )}
            </>
          )}

          {/* Actions */}
          <div className="flex gap-3 justify-end">
            <button onClick={resetForm} className="btn-secondary">
              Cancel
            </button>
            <button
              onClick={handleImport}
              disabled={!validationResult.valid}
              className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Import {isLargeFile ? `~${validationResult.rowCount.toLocaleString()}` : validationResult.data.length.toLocaleString()} Rows
              {validationResult.anomalies && validationResult.anomalies.length > 0 && (
                <span className="ml-1 text-yellow-200">
                  ({validationResult.anomalies.length} flagged)
                </span>
              )}
              <ArrowRight className="ml-1 h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {/* Importing Step */}
      {step === "importing" && (
        <div className="space-y-6">
          <ImportProgress progress={uploadProgress} />

          {/* Chunked upload progress details */}
          {isLargeFile && chunkedProgress && (
            <div className="bg-gray-50 rounded-lg p-4">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
                <div>
                  <p className="text-2xl font-bold text-gray-900">
                    {formatFileSize(chunkedProgress.bytesSent)}
                  </p>
                  <p className="text-sm text-gray-600">Uploaded</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-green-600">
                    {formatFileSize(chunkedProgress.totalBytes)}
                  </p>
                  <p className="text-sm text-gray-600">Total Size</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-gray-500">
                    {chunkedProgress.chunksSent}/{chunkedProgress.totalChunks}
                  </p>
                  <p className="text-sm text-gray-600">Chunks Sent</p>
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-700">
                    {chunkedProgress.currentPhase}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">Current Phase</p>
                </div>
              </div>
            </div>
          )}

          {/* Cancel button */}
          {isLargeFile && (
            <div className="flex justify-center">
              <button
                onClick={handleCancel}
                className="btn-secondary text-red-600 hover:text-red-700"
              >
                Cancel Import
              </button>
            </div>
          )}
        </div>
      )}

      {/* Success Step */}
      {step === "success" && importResult && (
        <ImportResultCard result={importResult} onReset={resetForm} onViewCreatives={() => router.push("/creatives")} />
      )}

      {/* Error Step */}
      {step === "error" && importResult && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-6">
          <div className="flex items-start gap-3">
            <XCircle className="h-6 w-6 text-red-600 mt-0.5" />
            <div className="flex-1">
              <h3 className="font-semibold text-red-900 text-lg mb-2">
                Import {importResult.imported && importResult.imported > 0 ? "Partially " : ""}Failed
              </h3>
              {importResult.error && (
                <p className="text-red-800">{importResult.error}</p>
              )}

              {importResult.imported && importResult.imported > 0 && (
                <p className="text-red-700 mt-2">
                  Partially imported: {importResult.imported.toLocaleString()} rows before error
                </p>
              )}

              {importResult.error_details &&
                importResult.error_details.length > 0 && (
                  <div className="mt-4">
                    <ValidationErrors errors={importResult.error_details} />
                  </div>
                )}

              <div className="mt-4">
                <button onClick={resetForm} className="btn-primary">
                  Try Again
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
