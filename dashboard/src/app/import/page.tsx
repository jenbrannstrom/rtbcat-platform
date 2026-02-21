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
  RequiredColumnsTable,
  TroubleshootingSection,
  ImportResultCard,
  ImportHistorySection,
  ImportTrackingMatrixSection,
} from "@/components/import";
import {
  type ExtendedValidationResult,
} from "@/lib/csv-validator";
import {
  importPerformanceData,
  getImportHistory,
  getImportTrackingMatrix,
  type ImportHistoryItem,
  type ImportTrackingMatrixResponse,
} from "@/lib/api";
import {
  uploadChunkedCSV,
  previewCSV,
  type UploadProgress,
} from "@/lib/chunked-uploader";
import { extractSeatFromPreview, formatSeatInfo, type SeatInfo } from "@/lib/seat-extractor";
import type { ImportResponse } from "@/lib/types/import";
import { GmailReportsTab } from "@/app/settings/accounts/components/GmailReportsTab";
import {
  detectReportType,
  getMissingRequiredColumns,
} from "@/lib/report-metadata";
import { useAccount } from "@/contexts/account-context";
import { toBuyerScopedPath } from "@/lib/buyer-routes";

type ImportStep = "upload" | "preview" | "importing" | "success" | "error";

// Threshold for using chunked upload (5MB)
const CHUNKED_UPLOAD_THRESHOLD = 5 * 1024 * 1024;

export default function ImportPage() {
  const router = useRouter();
  const { selectedBuyerId } = useAccount();
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
  const [importMatrix, setImportMatrix] = useState<ImportTrackingMatrixResponse | null>(null);
  const [matrixLoading, setMatrixLoading] = useState(true);

  // Load import history on mount and after successful imports
  const loadImportData = useCallback(async () => {
    setHistoryLoading(true);
    setMatrixLoading(true);
    try {
      const [history, matrix] = await Promise.all([
        getImportHistory(10, 0, selectedBuyerId || undefined),
        getImportTrackingMatrix(30, selectedBuyerId || undefined),
      ]);
      setImportHistory(history);
      setImportMatrix(matrix);
    } catch (error) {
      console.error("Failed to load import data:", error);
    } finally {
      setHistoryLoading(false);
      setMatrixLoading(false);
    }
  }, [selectedBuyerId]);

  useEffect(() => {
    loadImportData();
  }, [loadImportData]);

  useEffect(() => {
    const isImportInFlight =
      step === "importing" &&
      (chunkedProgress?.status === "uploading" || chunkedProgress?.status === "processing");
    if (!isImportInFlight) return;

    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };

    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
    };
  }, [step, chunkedProgress?.status]);

  // Handle file selection
  const handleFileSelect = async (selectedFile: File) => {
    setFile(selectedFile);
    setStep("preview");
    setIsLargeFile(selectedFile.size > CHUNKED_UPLOAD_THRESHOLD);

    try {
      const preview = await previewCSV(selectedFile, 10);
      setPreviewData(preview);

      // Extract seat info from preview rows
      const seat = extractSeatFromPreview(preview.rows);
      setSeatInfo(seat);

      const reportType = detectReportType(preview.headers, selectedFile.name);
      const missingRequired = getMissingRequiredColumns(
        preview.headers,
        reportType,
        selectedFile.name
      );

      const errors =
        reportType === "unknown"
          ? [{
              row: 0,
              field: "columns",
              error: `Could not identify report type. Found columns: ${preview.headers.join(", ") || "none"}`,
              value: null,
            }]
          : missingRequired.length > 0
            ? [{
                row: 0,
                field: "columns",
                error: `Missing required columns: ${missingRequired.join(", ")}. Found columns: ${preview.headers.join(", ") || "none"}`,
                value: null,
              }]
            : [];

      setValidationResult({
        valid: reportType !== "unknown" && missingRequired.length === 0,
        errors,
        warnings: [],
        anomalies: [],
        rowCount: preview.estimatedRowCount,
        data: [],
        detectedColumns: undefined,
        hasHourlyData: preview.headers.some((h) => h.toLowerCase().includes("hour")),
        aggregatedFromRows: undefined,
      });
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
        const imported = result.imported ?? 0;
        const duplicates = result.duplicates ?? 0;
        setStep(result.success || imported > 0 || duplicates > 0 ? "success" : "error");
        if (result.success || imported > 0 || duplicates > 0) {
          loadImportData(); // Reload import tracking after successful import
        }
      } else {
        // Use standard upload for small files
        const result = await importPerformanceData(file, (progress) => {
          setUploadProgress(progress);
        });

        setImportResult(result);
        setStep("success");
        loadImportData(); // Reload import tracking after successful import
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
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <GmailReportsTab />
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">
          Import Reports
        </h1>
      </div>

      {/* Upload Step */}
      {step === "upload" && (
        <div className="space-y-6">
          {/* Main Upload Area */}
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <ImportDropzone onFileSelect={handleFileSelect} maxSizeMB={500} />
          </div>

          {/* Collapsible Required Columns */}
          <details className="bg-white rounded-lg border border-gray-200">
            <summary className="p-4 cursor-pointer hover:bg-gray-50 font-medium text-gray-900 flex items-center justify-between">
              <span>Reference: Required columns by report type</span>
              <ChevronDown className="h-5 w-5 text-gray-500" />
            </summary>
            <div className="p-4 pt-0 border-t border-gray-200">
              <RequiredColumnsTable />
            </div>
          </details>

          {/* Collapsible Troubleshooting */}
          <details className="bg-white rounded-lg border border-gray-200">
            <summary className="p-4 cursor-pointer hover:bg-gray-50 font-medium text-gray-900 flex items-center justify-between">
              <span>Help: Large files and download links</span>
              <ChevronDown className="h-5 w-5 text-gray-500" />
            </summary>
            <div className="p-4 pt-0 border-t border-gray-200">
              <TroubleshootingSection />
            </div>
          </details>

          <ImportTrackingMatrixSection
            matrix={importMatrix}
            loading={matrixLoading}
            onRefresh={loadImportData}
          />

          {/* Recent Import History */}
          <ImportHistorySection
            history={importHistory}
            loading={historyLoading}
            onRefresh={loadImportData}
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

          {/* Fatal Errors */}
          {!validationResult.valid && validationResult.errors.length > 0 && (
            <ValidationErrors errors={validationResult.errors} />
          )}

          {/* Preview */}
          {validationResult.valid && previewData && (
            <div className="mt-4">
              <ImportPreview
                headers={previewData.headers}
                rows={previewData.rows.slice(0, 10)}
              />
              {previewData.rows.length > 10 && (
                <p className="text-sm text-gray-600 text-center">
                  Showing first 10 of {previewData.rows.length} rows
                </p>
              )}
            </div>
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
              Import {validationResult.rowCount.toLocaleString()} Rows
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
        <ImportResultCard
          result={importResult}
          onReset={resetForm}
          onViewCreatives={() => router.push(toBuyerScopedPath("/clusters", selectedBuyerId))}
        />
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
