"use client";

import { useState, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  CheckCircle,
  XCircle,
  ArrowRight,
  AlertTriangle,
  ChevronDown,
  ExternalLink,
} from "lucide-react";
import { ImportDropzone } from "@/components/import-dropzone";
import { ImportPreview } from "@/components/import-preview";
import { ImportProgress } from "@/components/import-progress";
import { ValidationErrors } from "@/components/validation-errors";
import {
  validatePerformanceCSV,
  type ExtendedValidationResult,
  groupAnomaliesByType,
  getTopAnomalyApps,
  formatAnomalyType,
} from "@/lib/csv-validator";
import type { AnomalyType } from "@/lib/types/import";
import { parseCSV } from "@/lib/csv-parser";
import { importPerformanceData } from "@/lib/api";
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

        setImportResult({
          success: result.success,
          imported: result.imported,
          duplicates: result.skipped,
          error_details: result.errors.map(e => ({
            row: e.row || 0,
            field: e.field || "unknown",
            error: e.error,
            value: e.value,
          })),
          date_range: result.dateRange,
          total_spend: result.totalSpend,
        });
        setStep(result.success || result.imported > 0 ? "success" : "error");
      } else {
        // Use standard upload for small files
        const result = await importPerformanceData(file, (progress) => {
          setUploadProgress(progress);
        });

        setImportResult(result);
        setStep("success");
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
        imported: chunkedProgress?.rowsImported || 0,
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
                    {chunkedProgress.rowsProcessed.toLocaleString()}
                  </p>
                  <p className="text-sm text-gray-600">Rows Processed</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-green-600">
                    {chunkedProgress.rowsImported.toLocaleString()}
                  </p>
                  <p className="text-sm text-gray-600">Imported</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-gray-500">
                    {chunkedProgress.batchesSent}
                  </p>
                  <p className="text-sm text-gray-600">Batches Sent</p>
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

// ============================================================================
// Sub-components
// ============================================================================

function ExportInstructions() {
  return (
    <div className="space-y-6 text-sm">
      <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
        <h4 className="font-semibold text-amber-900 mb-2">Why Multiple Reports?</h4>
        <p className="text-amber-800">
          Google Authorized Buyers doesn{"'"}t allow <strong>Billing ID</strong> and <strong>Bids</strong> in the same export.
          To analyze waste by pretargeting config, we need to join two CSV files on <code className="bg-amber-100 px-1 rounded">Creative ID</code>.
        </p>
      </div>

      <div>
        <h4 className="font-semibold text-gray-900 mb-2">Go to Authorized Buyers Reporting</h4>
        <ol className="list-decimal list-inside text-gray-700 space-y-1">
          <li>Open <a href="https://authorized-buyers.google.com/" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline inline-flex items-center gap-1">Authorized Buyers <ExternalLink className="h-3 w-3" /></a></li>
          <li>Navigate to <strong>Reporting</strong> → <strong>New Report</strong></li>
        </ol>
      </div>

      {/* Main Report: Billing Config Performance */}
      <div className="border-2 border-blue-200 rounded-lg p-4 bg-blue-50">
        <div className="flex items-center gap-2 mb-3">
          <span className="bg-blue-600 text-white text-xs font-bold px-2 py-1 rounded">Required</span>
          <h4 className="font-semibold text-gray-900">Billing Config Performance</h4>
        </div>
        <p className="text-gray-600 mb-3">This is the main report for QPS waste analysis. Shows waste per pretargeting config.</p>

        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Dimensions (in order)</p>
            <ul className="space-y-1 text-gray-700">
              <li className="flex items-center gap-2"><span className="text-green-600 font-bold">✓</span> <strong>Day</strong></li>
              <li className="flex items-center gap-2"><span className="text-green-600 font-bold">✓</span> <strong>Billing ID</strong></li>
              <li className="flex items-center gap-2"><span className="text-green-600 font-bold">✓</span> <strong>Creative ID</strong></li>
              <li className="flex items-center gap-2"><span className="text-green-600 font-bold">✓</span> <strong>Creative size</strong></li>
              <li className="flex items-center gap-2"><span className="text-gray-400">○</span> Creative format <span className="text-xs text-gray-400">(optional)</span></li>
              <li className="flex items-center gap-2"><span className="text-green-600 font-bold">✓</span> <strong>Country</strong></li>
            </ul>
          </div>
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Metrics</p>
            <ul className="space-y-1 text-gray-700">
              <li className="flex items-center gap-2"><span className="text-green-600 font-bold">✓</span> <strong>Reached queries</strong></li>
              <li className="flex items-center gap-2"><span className="text-green-600 font-bold">✓</span> <strong>Impressions</strong></li>
              <li className="flex items-center gap-2"><span className="text-gray-400">○</span> Clicks <span className="text-xs text-gray-400">(optional)</span></li>
              <li className="flex items-center gap-2"><span className="text-gray-400">○</span> Spend <span className="text-xs text-gray-400">(optional)</span></li>
            </ul>
          </div>
        </div>
      </div>

      {/* Optional: Publisher Performance */}
      <div className="border border-gray-200 rounded-lg p-4">
        <div className="flex items-center gap-2 mb-3">
          <span className="bg-gray-200 text-gray-700 text-xs font-bold px-2 py-1 rounded">Optional</span>
          <h4 className="font-semibold text-gray-900">Publisher Performance</h4>
        </div>
        <p className="text-gray-600 mb-3">Shows publisher-level funnel metrics (for advanced analysis)</p>

        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Dimensions</p>
            <ul className="space-y-1 text-gray-700">
              <li className="flex items-center gap-2"><span className="text-green-600">✓</span> Publisher ID</li>
              <li className="flex items-center gap-2"><span className="text-green-600">✓</span> Publisher name</li>
            </ul>
          </div>
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Metrics</p>
            <ul className="space-y-1 text-gray-700">
              <li className="flex items-center gap-2"><span className="text-green-600">✓</span> Bid requests</li>
              <li className="flex items-center gap-2"><span className="text-green-600">✓</span> Reached queries</li>
              <li className="flex items-center gap-2"><span className="text-green-600">✓</span> Impressions</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Schedule Settings */}
      <div>
        <h4 className="font-semibold text-gray-900 mb-2">Schedule Settings</h4>
        <ul className="list-disc list-inside text-gray-700 space-y-1">
          <li>Date range: <strong>Yesterday</strong></li>
          <li>Schedule: <strong>Daily</strong></li>
          <li>File format: <strong>CSV</strong></li>
        </ul>
      </div>

      <div className="bg-blue-50 p-3 rounded-lg">
        <p className="text-blue-800">
          <strong>Tip:</strong> Upload all CSV files here. Cat-Scan automatically detects the report type
          from the column headers and joins them on <code className="bg-blue-100 px-1 rounded">Creative ID</code>.
        </p>
      </div>
    </div>
  );
}

function RequiredColumnsTable() {
  return (
    <div className="space-y-4 text-sm">
      <p className="text-gray-600">
        Cat-Scan imports <strong>all recognized columns</strong> from your CSV.
        The more data you export, the better the analysis.
      </p>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
        <p className="text-blue-800">
          <strong>Creative ID</strong> is the key field that links performance data to your creative inventory.
          Every row must have a Creative ID.
        </p>
      </div>

      <div className="bg-gray-50 p-3 rounded-lg">
        <p className="text-gray-700">
          <strong>Column auto-detection:</strong> Cat-Scan automatically maps Google{"'"}s column names
          (e.g., <code className="bg-gray-200 px-1 rounded">#Creative ID</code> → <code className="bg-gray-200 px-1 rounded">creative_id</code>).
          Unknown columns are safely ignored.
        </p>
      </div>
    </div>
  );
}

function TroubleshootingSection() {
  return (
    <div className="space-y-4 text-sm">
      <p className="text-gray-700">
        If your CSV export is too large (over 100MB or times out):
      </p>

      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
        <h4 className="font-semibold text-yellow-800 mb-2">Split by Date, Keep ALL Data</h4>
        <p className="text-gray-700 mb-2">
          Create multiple scheduled reports for different date ranges, but keep ALL dimensions and metrics in each:
        </p>
        <ul className="space-y-1 text-gray-600 ml-4">
          <li>• Report A: Yesterday (Day 1)</li>
          <li>• Report B: 2 days ago (Day 2)</li>
          <li>• etc.</li>
        </ul>
        <p className="text-gray-600 mt-2">
          Upload each file separately. Cat-Scan will merge them using <strong>Creative ID</strong> as the key.
        </p>
      </div>

      <div className="bg-red-50 border border-red-200 rounded-lg p-3">
        <h4 className="font-semibold text-red-800 mb-2">Do NOT split by metrics</h4>
        <p className="text-gray-700">
          Never create separate exports for different metrics (e.g., one for video, one for display).
          This breaks the data model. Always export ALL metrics together.
        </p>
      </div>

      <div>
        <h4 className="font-semibold text-gray-900 mb-1">Streaming upload</h4>
        <p className="text-gray-600">
          Files over 5MB are automatically uploaded using streaming mode with progress tracking.
          This handles files up to 500MB.
        </p>
      </div>
    </div>
  );
}

function ColumnMappingCard({ columns }: { columns: Record<string, string> }) {
  const mappedColumns = Object.entries(columns).filter(([, v]) => v);

  return (
    <div className="bg-green-50 border border-green-200 rounded-lg p-4">
      <div className="flex items-start gap-2">
        <CheckCircle className="h-5 w-5 text-green-600 mt-0.5" />
        <div className="flex-1">
          <p className="font-medium text-green-900">Columns detected and mapped</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {mappedColumns.map(([key, value]) => (
              <span key={key} className="inline-flex items-center px-2 py-1 bg-green-100 text-green-800 text-xs rounded">
                <span className="font-mono">{value}</span>
                <span className="mx-1 text-green-600">→</span>
                <span>{key}</span>
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function ImportResultCard({
  result,
  onReset,
  onViewCreatives
}: {
  result: ImportResponse;
  onReset: () => void;
  onViewCreatives: () => void;
}) {
  const success = result.success !== false && (result.imported ?? 0) > 0;

  return (
    <div className={`rounded-lg p-6 border ${
      success
        ? "bg-green-50 border-green-200"
        : "bg-red-50 border-red-200"
    }`}>
      <div className="flex items-start gap-3">
        {success ? (
          <CheckCircle className="h-6 w-6 text-green-600 mt-0.5" />
        ) : (
          <XCircle className="h-6 w-6 text-red-600 mt-0.5" />
        )}
        <div className="flex-1">
          <h3 className={`font-semibold text-lg mb-4 ${success ? "text-green-900" : "text-red-900"}`}>
            {success ? "Import Successful" : "Import Failed"}
          </h3>

          {/* Stats Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            <div>
              <p className="text-gray-500 text-sm">Rows imported</p>
              <p className={`font-bold text-xl ${success ? "text-green-700" : "text-gray-700"}`}>
                {(result.imported ?? 0).toLocaleString()}
              </p>
            </div>
            {result.duplicates !== undefined && result.duplicates > 0 && (
              <div>
                <p className="text-gray-500 text-sm">Duplicates skipped</p>
                <p className="font-medium text-gray-600">{result.duplicates.toLocaleString()}</p>
              </div>
            )}
            {result.date_range && (
              <div className="col-span-2">
                <p className="text-gray-500 text-sm">Date range</p>
                <p className="font-medium text-gray-700">
                  {result.date_range.start} → {result.date_range.end}
                </p>
              </div>
            )}
            {result.total_spend !== undefined && result.total_spend > 0 && (
              <div>
                <p className="text-gray-500 text-sm">Total spend</p>
                <p className="font-medium text-gray-700">
                  ${result.total_spend.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </p>
              </div>
            )}
          </div>

          {/* Columns Imported */}
          {success && result.columns_imported && result.columns_imported.length > 0 && (
            <div className="mb-4">
              <p className="text-gray-500 text-sm mb-2">Columns imported:</p>
              <div className="flex flex-wrap gap-1">
                {result.columns_imported.map(col => (
                  <span key={col} className="px-2 py-0.5 bg-green-100 text-green-800 rounded text-xs">
                    {col}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Error if any */}
          {result.error && (
            <p className="text-red-700 mb-4">{result.error}</p>
          )}

          {/* Missing required columns */}
          {result.required_missing && result.required_missing.length > 0 && (
            <div className="mb-4 p-3 bg-red-100 rounded-lg">
              <p className="text-red-800 text-sm font-medium mb-1">Missing required columns:</p>
              <div className="flex flex-wrap gap-1">
                {result.required_missing.map(col => (
                  <span key={col} className="px-2 py-0.5 bg-red-200 text-red-900 rounded text-xs font-medium">
                    {col}
                  </span>
                ))}
              </div>
              {result.fix_instructions && (
                <details className="mt-2">
                  <summary className="text-red-700 text-sm cursor-pointer hover:underline">
                    How to fix this
                  </summary>
                  <pre className="mt-2 text-xs text-red-800 whitespace-pre-wrap">{result.fix_instructions}</pre>
                </details>
              )}
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-3">
            {success && (
              <button onClick={onViewCreatives} className="btn-primary">
                View Creatives
                <ArrowRight className="ml-1 h-4 w-4" />
              </button>
            )}
            <button onClick={onReset} className="btn-secondary">
              {success ? "Import More Data" : "Try Again"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
