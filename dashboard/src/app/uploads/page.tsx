"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import {
  CheckCircle,
  XCircle,
  AlertTriangle,
  Calendar,
  Database,
  FileText,
  TrendingDown,
  TrendingUp,
  RefreshCw,
  Upload,
  ChevronDown,
  ArrowRight,
} from "lucide-react";
import {
  getUploadTracking,
  getImportHistory,
  importPerformanceData,
  type DailyUploadSummary,
  type UploadTrackingResponse,
  type ImportHistoryItem,
} from "@/lib/api";
import { ImportDropzone } from "@/components/import-dropzone";
import { ImportProgress } from "@/components/import-progress";
import { ValidationErrors } from "@/components/validation-errors";
import {
  validatePerformanceCSV,
  type ExtendedValidationResult,
} from "@/lib/csv-validator";
import { parseCSV } from "@/lib/csv-parser";
import {
  uploadChunkedCSV,
  previewCSV,
  type UploadProgress,
} from "@/lib/chunked-uploader";
import { extractSeatFromPreview, formatSeatInfo, type SeatInfo } from "@/lib/seat-extractor";
import type { ImportResponse } from "@/lib/types/import";
import { cn } from "@/lib/utils";

type ImportStep = "upload" | "preview" | "importing" | "success" | "error";
const CHUNKED_UPLOAD_THRESHOLD = 5 * 1024 * 1024;

export default function UploadsPage() {
  const [tracking, setTracking] = useState<UploadTrackingResponse | null>(null);
  const [history, setHistory] = useState<ImportHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(30);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [trackingData, historyData] = await Promise.all([
        getUploadTracking(days),
        getImportHistory(50),
      ]);
      setTracking(trackingData);
      setHistory(historyData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [days]);

  const formatNumber = (num: number) => {
    return num.toLocaleString();
  };

  const formatFileSize = (mb: number) => {
    if (mb < 1) return `${(mb * 1024).toFixed(0)} KB`;
    return `${mb.toFixed(1)} MB`;
  };

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Uploads</h1>
        <p className="text-gray-600 mt-1">
          Import CSV data and monitor upload history
        </p>
      </div>

      {/* Manual Import Section */}
      <ManualImportSection onImportSuccess={loadData} />

      {/* Loading and Error States for Tracking */}
      {loading ? (
        <div className="flex items-center justify-center min-h-[200px]">
          <RefreshCw className="h-8 w-8 animate-spin text-gray-400" />
        </div>
      ) : error ? (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-800">
          {error}
        </div>
      ) : (
        <>
          {/* Summary Cards */}
          {tracking && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              <div className="bg-white rounded-lg border border-gray-200 p-4">
                <div className="flex items-center gap-2 text-gray-500 text-sm">
                  <Calendar className="h-4 w-4" />
                  <span>Days Tracked</span>
                </div>
                <p className="text-2xl font-bold text-gray-900 mt-1">
                  {tracking.total_days}
                </p>
              </div>

              <div className="bg-white rounded-lg border border-gray-200 p-4">
                <div className="flex items-center gap-2 text-gray-500 text-sm">
                  <FileText className="h-4 w-4" />
                  <span>Total Uploads</span>
                </div>
                <p className="text-2xl font-bold text-gray-900 mt-1">
                  {formatNumber(tracking.total_uploads)}
                </p>
              </div>

              <div className="bg-white rounded-lg border border-gray-200 p-4">
                <div className="flex items-center gap-2 text-gray-500 text-sm">
                  <Database className="h-4 w-4" />
                  <span>Total Rows</span>
                </div>
                <p className="text-2xl font-bold text-gray-900 mt-1">
                  {formatNumber(tracking.total_rows)}
                </p>
              </div>

              <div className="bg-white rounded-lg border border-gray-200 p-4">
                <div className="flex items-center gap-2 text-gray-500 text-sm">
                  <AlertTriangle className="h-4 w-4" />
                  <span>Anomalies</span>
                </div>
                <p className={`text-2xl font-bold mt-1 ${
                  tracking.days_with_anomalies > 0 ? "text-yellow-600" : "text-green-600"
                }`}>
                  {tracking.days_with_anomalies}
                </p>
              </div>
            </div>
          )}

          {/* Period Selector */}
          <div className="mb-4 flex items-center gap-2">
            <span className="text-sm text-gray-600">Show last:</span>
            {[7, 14, 30, 90].map((d) => (
              <button
                key={d}
                onClick={() => setDays(d)}
                className={`px-3 py-1 text-sm rounded-lg ${
                  days === d
                    ? "bg-blue-100 text-blue-800 font-medium"
                    : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                }`}
              >
                {d} days
              </button>
            ))}
          </div>

          {/* Daily Upload Table */}
          <div className="bg-white rounded-lg border border-gray-200 overflow-hidden mb-6">
            <div className="px-4 py-3 border-b border-gray-200 bg-gray-50">
              <h2 className="font-semibold text-gray-900">Daily Upload Summary</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                      Date
                    </th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">
                      Status
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                      File Size
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                      Rows Written
                    </th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">
                      Alert
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {tracking?.daily_summaries.map((day) => (
                    <DailyRow key={day.upload_date} day={day} />
                  ))}
                  {(!tracking || tracking.daily_summaries.length === 0) && (
                    <tr>
                      <td colSpan={5} className="px-4 py-8 text-center text-gray-500">
                        No upload data available for this period
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Recent Import History */}
          <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-200 bg-gray-50">
              <h2 className="font-semibold text-gray-900">Recent Imports</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                      File
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                      Imported At
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                      Size
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                      Rows
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                      Dupes
                    </th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">
                      Status
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {history.map((item) => (
                    <tr key={item.batch_id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm text-gray-900 font-mono">
                        {item.filename || item.batch_id}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">
                        {new Date(item.imported_at).toLocaleString()}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600 text-right">
                        {formatFileSize(item.file_size_mb)}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-900 text-right font-medium">
                        {formatNumber(item.rows_imported)}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-500 text-right">
                        {item.rows_duplicate > 0 ? formatNumber(item.rows_duplicate) : "-"}
                      </td>
                      <td className="px-4 py-3 text-center">
                        {item.status === "complete" ? (
                          <CheckCircle className="h-5 w-5 text-green-500 inline" />
                        ) : (
                          <XCircle className="h-5 w-5 text-red-500 inline" />
                        )}
                      </td>
                    </tr>
                  ))}
                  {history.length === 0 && (
                    <tr>
                      <td colSpan={6} className="px-4 py-8 text-center text-gray-500">
                        No import history available
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

// ============================================================================
// Manual Import Section
// ============================================================================

function ManualImportSection({ onImportSuccess }: { onImportSuccess: () => void }) {
  const abortControllerRef = useRef<AbortController | null>(null);
  const [step, setStep] = useState<ImportStep>("upload");
  const [file, setFile] = useState<File | null>(null);
  const [validationResult, setValidationResult] = useState<ExtendedValidationResult | null>(null);
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

  const handleFileSelect = async (selectedFile: File) => {
    setFile(selectedFile);
    setStep("preview");
    setIsLargeFile(selectedFile.size > CHUNKED_UPLOAD_THRESHOLD);

    try {
      if (selectedFile.size > CHUNKED_UPLOAD_THRESHOLD) {
        const preview = await previewCSV(selectedFile, 10);
        setPreviewData(preview);
        const seat = extractSeatFromPreview(preview.rows);
        setSeatInfo(seat);
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
        const parseResult = await parseCSV(selectedFile);
        const validation = validatePerformanceCSV(parseResult);
        setValidationResult(validation);
      }
    } catch (error) {
      console.error("CSV parsing error:", error);
      setValidationResult({
        valid: false,
        errors: [{ row: 0, field: "file", error: "Failed to parse CSV file.", value: null }],
        warnings: [],
        anomalies: [],
        rowCount: 0,
        data: [],
      });
    }
  };

  const handleChunkedProgress = useCallback((progress: UploadProgress) => {
    setChunkedProgress(progress);
    setUploadProgress(progress.progress);
  }, []);

  const handleImport = async () => {
    if (!file) return;
    setStep("importing");
    setUploadProgress(0);
    setChunkedProgress(null);
    abortControllerRef.current = new AbortController();

    try {
      if (isLargeFile) {
        const result = await uploadChunkedCSV(file, {
          onProgress: handleChunkedProgress,
          signal: abortControllerRef.current.signal,
        });
        setImportResult({
          success: result.success,
          imported: result.imported,
          duplicates: result.skipped,
          error_details: result.errors.map(e => ({ row: e.row || 0, field: e.field || "unknown", error: e.error, value: e.value })),
          date_range: result.dateRange,
          total_spend: result.totalSpend,
        });
        setStep(result.success || result.imported > 0 ? "success" : "error");
      } else {
        const result = await importPerformanceData(file, (progress) => setUploadProgress(progress));
        setImportResult(result);
        setStep("success");
      }
      onImportSuccess();
    } catch (error) {
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

  const handleCancel = () => {
    if (abortControllerRef.current) abortControllerRef.current.abort();
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

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="mb-8">
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-200 bg-gray-50 flex items-center gap-2">
          <Upload className="h-5 w-5 text-blue-600" />
          <h2 className="font-semibold text-gray-900">Import CSV Data</h2>
        </div>

        <div className="p-4">
          {step === "upload" && (
            <div className="space-y-4">
              <ImportDropzone onFileSelect={handleFileSelect} maxSizeMB={500} />

              <details className="border border-gray-200 rounded-lg">
                <summary className="p-3 cursor-pointer hover:bg-gray-50 text-sm font-medium text-gray-700 flex items-center justify-between">
                  <span>Expected CSV Format</span>
                  <ChevronDown className="h-4 w-4 text-gray-500" />
                </summary>
                <div className="p-3 pt-0 border-t border-gray-200 text-sm text-gray-600">
                  <p className="mb-3">
                    Upload performance reports from Google Authorized Buyers. Create this report in <strong>Authorized Buyers → Reporting → New Report</strong>.
                  </p>
                  <div className="p-3 bg-blue-50 rounded border border-blue-200">
                    <p className="font-medium text-blue-900 mb-2">Report: &quot;catscan-billing-config&quot;</p>
                    <div className="grid grid-cols-2 gap-4 text-xs">
                      <div>
                        <p className="font-semibold text-gray-600 mb-1">Dimensions (required):</p>
                        <ol className="list-decimal list-inside text-gray-700">
                          <li>Day</li>
                          <li>Billing ID</li>
                          <li>Creative ID</li>
                          <li>Creative size</li>
                          <li>Country</li>
                          <li>Creative format <span className="text-gray-400">(optional)</span></li>
                        </ol>
                      </div>
                      <div>
                        <p className="font-semibold text-gray-600 mb-1">Metrics (required):</p>
                        <ul className="text-gray-700">
                          <li>• Reached queries</li>
                          <li>• Impressions</li>
                        </ul>
                        <p className="font-semibold text-gray-600 mt-2 mb-1">Schedule:</p>
                        <p className="text-gray-700">Daily, Yesterday</p>
                      </div>
                    </div>
                  </div>
                  <p className="mt-3 text-xs text-gray-500">
                    Optional additional columns: Clicks, Spend, Publisher ID, etc.
                  </p>
                </div>
              </details>
            </div>
          )}

          {step === "preview" && validationResult && (
            <div className="space-y-4">
              <div className="bg-gray-50 rounded-lg p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-gray-900">{file?.name}</p>
                    <p className="text-sm text-gray-600">
                      {formatFileSize(file?.size || 0)} · {validationResult.rowCount.toLocaleString()} rows
                      {isLargeFile && " (estimated)"}
                    </p>
                  </div>
                  <button onClick={resetForm} className="text-sm text-gray-600 hover:text-gray-800">Remove</button>
                </div>
              </div>

              {seatInfo && (
                <div className="bg-green-50 border border-green-200 rounded-lg p-3">
                  <div className="flex items-start gap-2">
                    <CheckCircle className="h-5 w-5 text-green-600 mt-0.5" />
                    <div>
                      <p className="font-medium text-green-900">Seat detected</p>
                      <p className="text-sm text-green-800 mt-1">{formatSeatInfo(seatInfo)}</p>
                    </div>
                  </div>
                </div>
              )}

              {!validationResult.valid && <ValidationErrors errors={validationResult.errors} />}

              {validationResult.valid && validationResult.detectedColumns && (
                <div className="bg-green-50 border border-green-200 rounded-lg p-3">
                  <div className="flex items-start gap-2">
                    <CheckCircle className="h-5 w-5 text-green-600 mt-0.5" />
                    <div className="flex-1">
                      <p className="font-medium text-green-900">Columns detected</p>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {Object.entries(validationResult.detectedColumns)
                          .filter(([, v]) => v)
                          .map(([key, value]) => (
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
              )}

              {validationResult.valid && (
                <div className="flex gap-3 justify-end">
                  <button onClick={resetForm} className="btn-secondary">Cancel</button>
                  <button onClick={handleImport} className="btn-primary">
                    Import {validationResult.rowCount.toLocaleString()} Rows
                    <ArrowRight className="ml-1 h-4 w-4" />
                  </button>
                </div>
              )}
            </div>
          )}

          {step === "importing" && (
            <div className="space-y-4">
              <ImportProgress progress={uploadProgress} />
              {isLargeFile && chunkedProgress && (
                <div className="bg-gray-50 rounded-lg p-4">
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
                    <div>
                      <p className="text-2xl font-bold text-gray-900">{chunkedProgress.rowsProcessed.toLocaleString()}</p>
                      <p className="text-sm text-gray-600">Rows Processed</p>
                    </div>
                    <div>
                      <p className="text-2xl font-bold text-green-600">{chunkedProgress.rowsImported.toLocaleString()}</p>
                      <p className="text-sm text-gray-600">Imported</p>
                    </div>
                    <div>
                      <p className="text-2xl font-bold text-gray-500">{chunkedProgress.batchesSent}</p>
                      <p className="text-sm text-gray-600">Batches</p>
                    </div>
                    <div>
                      <p className="text-sm font-medium text-gray-700">{chunkedProgress.currentPhase}</p>
                      <p className="text-xs text-gray-500 mt-1">Phase</p>
                    </div>
                  </div>
                </div>
              )}
              {isLargeFile && (
                <div className="flex justify-center">
                  <button onClick={handleCancel} className="btn-secondary text-red-600 hover:text-red-700">
                    Cancel Import
                  </button>
                </div>
              )}
            </div>
          )}

          {step === "success" && importResult && (
            <div className="bg-green-50 border border-green-200 rounded-lg p-4">
              <div className="flex items-start gap-3">
                <CheckCircle className="h-6 w-6 text-green-600 mt-0.5" />
                <div className="flex-1">
                  <h3 className="font-semibold text-green-900 text-lg mb-3">Import Successful</h3>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-4">
                    <div>
                      <p className="text-gray-500 text-sm">Rows imported</p>
                      <p className="font-bold text-xl text-green-700">{(importResult.imported ?? 0).toLocaleString()}</p>
                    </div>
                    {importResult.duplicates !== undefined && importResult.duplicates > 0 && (
                      <div>
                        <p className="text-gray-500 text-sm">Duplicates skipped</p>
                        <p className="font-medium text-gray-600">{importResult.duplicates.toLocaleString()}</p>
                      </div>
                    )}
                    {importResult.date_range && (
                      <div>
                        <p className="text-gray-500 text-sm">Date range</p>
                        <p className="font-medium text-gray-700">{importResult.date_range.start} → {importResult.date_range.end}</p>
                      </div>
                    )}
                  </div>
                  <div className="flex gap-3">
                    <a href="/waste-analysis" className="btn-primary">
                      View Waste Analysis <ArrowRight className="ml-1 h-4 w-4" />
                    </a>
                    <button onClick={resetForm} className="btn-secondary">Import More</button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {step === "error" && importResult && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <div className="flex items-start gap-3">
                <XCircle className="h-6 w-6 text-red-600 mt-0.5" />
                <div className="flex-1">
                  <h3 className="font-semibold text-red-900 text-lg mb-2">Import Failed</h3>
                  {importResult.error && <p className="text-red-800">{importResult.error}</p>}
                  {importResult.error_details && importResult.error_details.length > 0 && (
                    <div className="mt-4"><ValidationErrors errors={importResult.error_details} /></div>
                  )}
                  <div className="mt-4">
                    <button onClick={resetForm} className="btn-primary">Try Again</button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Daily Row Component
// ============================================================================

function DailyRow({ day }: { day: DailyUploadSummary }) {
  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr + "T00:00:00");
    return date.toLocaleDateString("en-US", {
      weekday: "short",
      month: "short",
      day: "numeric",
    });
  };

  const allSuccess = day.failed_uploads === 0 && day.successful_uploads > 0;
  const hasFailed = day.failed_uploads > 0;

  return (
    <tr className={`hover:bg-gray-50 ${day.has_anomaly ? "bg-yellow-50" : ""}`}>
      <td className="px-4 py-3 text-sm text-gray-900 font-medium">
        {formatDate(day.upload_date)}
      </td>
      <td className="px-4 py-3 text-center">
        {allSuccess ? (
          <CheckCircle className="h-5 w-5 text-green-500 inline" />
        ) : hasFailed ? (
          <XCircle className="h-5 w-5 text-red-500 inline" />
        ) : (
          <span className="text-gray-400">-</span>
        )}
      </td>
      <td className="px-4 py-3 text-sm text-gray-600 text-right">
        {day.total_file_size_mb > 0
          ? day.total_file_size_mb < 1
            ? `${(day.total_file_size_mb * 1024).toFixed(0)} KB`
            : `${day.total_file_size_mb.toFixed(1)} MB`
          : "-"}
      </td>
      <td className="px-4 py-3 text-sm text-gray-900 text-right font-medium">
        {day.total_rows_written > 0 ? day.total_rows_written.toLocaleString() : "-"}
      </td>
      <td className="px-4 py-3 text-center">
        {day.has_anomaly ? (
          <div className="inline-flex items-center gap-1 text-yellow-600" title={day.anomaly_reason || ""}>
            <AlertTriangle className="h-5 w-5" />
            {day.anomaly_reason?.includes("dropped") ? (
              <TrendingDown className="h-4 w-4" />
            ) : day.anomaly_reason?.includes("spiked") ? (
              <TrendingUp className="h-4 w-4" />
            ) : null}
          </div>
        ) : (
          <span className="text-gray-300">-</span>
        )}
      </td>
    </tr>
  );
}
