"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Download, CheckCircle, XCircle, ArrowRight, Info } from "lucide-react";
import { ImportDropzone } from "@/components/import-dropzone";
import { ImportPreview } from "@/components/import-preview";
import { ImportProgress } from "@/components/import-progress";
import { ValidationErrors } from "@/components/validation-errors";
import { validatePerformanceCSV, type ExtendedValidationResult } from "@/lib/csv-validator";
import { parseCSV, type ParseResult } from "@/lib/csv-parser";
import { importPerformanceData } from "@/lib/api";
import type { ImportResponse } from "@/lib/types/import";

type ImportStep = "upload" | "preview" | "importing" | "success" | "error";

export default function ImportPage() {
  const router = useRouter();

  const [step, setStep] = useState<ImportStep>("upload");
  const [file, setFile] = useState<File | null>(null);
  const [validationResult, setValidationResult] =
    useState<ExtendedValidationResult | null>(null);
  const [importResult, setImportResult] = useState<ImportResponse | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);

  // Handle file selection
  const handleFileSelect = async (selectedFile: File) => {
    setFile(selectedFile);
    setStep("preview");

    try {
      // Parse CSV with flexible column detection
      const parseResult = await parseCSV(selectedFile);

      // Validate
      const validation = validatePerformanceCSV(parseResult);
      setValidationResult(validation);
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
        rowCount: 0,
        data: [],
      });
    }
  };

  // Handle import
  const handleImport = async () => {
    if (!file || !validationResult?.valid) return;

    setStep("importing");
    setUploadProgress(0);

    try {
      const result = await importPerformanceData(file, (progress) => {
        setUploadProgress(progress);
      });

      setImportResult(result);
      setStep("success");
    } catch (error) {
      console.error("Import error:", error);
      setImportResult({
        success: false,
        imported: 0,
        error: error instanceof Error ? error.message : "Import failed",
      });
      setStep("error");
    }
  };

  // Download example CSV
  const downloadExample = () => {
    const csv = `creative_id,date,impressions,clicks,spend,geography
79783,2025-11-29,1000,50,25.50,US
79783,2025-11-28,950,45,23.75,US
79784,2025-11-29,500,10,5.00,BR
79784,2025-11-28,480,12,6.00,BR
79785,2025-11-29,2000,100,50.00,GB`;

    const blob = new Blob([csv], { type: "text/csv" });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "performance_data_example.csv";
    a.click();
    window.URL.revokeObjectURL(url);
  };

  const resetForm = () => {
    setFile(null);
    setValidationResult(null);
    setImportResult(null);
    setUploadProgress(0);
    setStep("upload");
  };

  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">
          Import Performance Data
        </h1>
        <p className="text-gray-600 mt-1">
          Upload CSV file with creative performance metrics
        </p>
      </div>

      {/* Upload Step */}
      {step === "upload" && (
        <div className="space-y-6">
          <ImportDropzone onFileSelect={handleFileSelect} />

          <div className="bg-gray-50 rounded-lg p-6">
            <h3 className="font-semibold text-gray-900 mb-3">
              Supported CSV Formats
            </h3>

            <div className="space-y-4">
              <div>
                <p className="text-sm font-medium text-gray-700 mb-1">
                  Option 1: Simple Format
                </p>
                <code className="block bg-white p-3 rounded text-sm font-mono overflow-x-auto">
                  creative_id,date,impressions,clicks,spend,geography
                </code>
              </div>

              <div>
                <p className="text-sm font-medium text-gray-700 mb-1">
                  Option 2: Google Authorized Buyers Export
                </p>
                <code className="block bg-white p-3 rounded text-sm font-mono overflow-x-auto text-xs">
                  #Creative ID,Day,Country,Impressions,Clicks,Spend (buyer currency)
                </code>
              </div>
            </div>

            <div className="mt-4 p-3 bg-blue-50 rounded-lg">
              <div className="flex gap-2">
                <Info className="h-5 w-5 text-blue-600 flex-shrink-0" />
                <div className="text-sm text-blue-800">
                  <p className="font-medium">Auto-detection enabled</p>
                  <ul className="mt-1 list-disc list-inside text-blue-700">
                    <li>Flexible column names (#Creative ID, creative_id, etc.)</li>
                    <li>Multiple date formats (MM/DD/YY, YYYY-MM-DD)</li>
                    <li>Currency symbols removed automatically ($10.50 → 10.50)</li>
                    <li>Hourly data aggregated to daily totals</li>
                  </ul>
                </div>
              </div>
            </div>

            <div className="mt-4">
              <button
                onClick={downloadExample}
                className="text-primary-600 hover:text-primary-700 text-sm font-medium inline-flex items-center gap-1"
              >
                <Download className="h-4 w-4" />
                Download Example CSV
              </button>
            </div>
          </div>
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
                  {((file?.size || 0) / 1024).toFixed(2)} KB ·{" "}
                  {validationResult.rowCount} rows
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

          {/* Column Detection Info */}
          {validationResult.detectedColumns && validationResult.valid && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <div className="flex items-start gap-2">
                <Info className="h-5 w-5 text-blue-600 mt-0.5" />
                <div>
                  <p className="font-medium text-blue-900">Auto-detected columns:</p>
                  <div className="mt-2 grid grid-cols-2 md:grid-cols-3 gap-2 text-sm">
                    {validationResult.detectedColumns.creative_id && (
                      <div className="text-blue-800">
                        <span className="font-mono bg-blue-100 px-1 rounded">
                          {validationResult.detectedColumns.creative_id}
                        </span>
                        {" → creative_id"}
                      </div>
                    )}
                    {validationResult.detectedColumns.date && (
                      <div className="text-blue-800">
                        <span className="font-mono bg-blue-100 px-1 rounded">
                          {validationResult.detectedColumns.date}
                        </span>
                        {" → date"}
                      </div>
                    )}
                    {validationResult.detectedColumns.impressions && (
                      <div className="text-blue-800">
                        <span className="font-mono bg-blue-100 px-1 rounded">
                          {validationResult.detectedColumns.impressions}
                        </span>
                        {" → impressions"}
                      </div>
                    )}
                    {validationResult.detectedColumns.clicks && (
                      <div className="text-blue-800">
                        <span className="font-mono bg-blue-100 px-1 rounded">
                          {validationResult.detectedColumns.clicks}
                        </span>
                        {" → clicks"}
                      </div>
                    )}
                    {validationResult.detectedColumns.spend && (
                      <div className="text-blue-800">
                        <span className="font-mono bg-blue-100 px-1 rounded">
                          {validationResult.detectedColumns.spend}
                        </span>
                        {" → spend"}
                      </div>
                    )}
                    {validationResult.detectedColumns.geography && (
                      <div className="text-blue-800">
                        <span className="font-mono bg-blue-100 px-1 rounded">
                          {validationResult.detectedColumns.geography}
                        </span>
                        {" → geography"}
                      </div>
                    )}
                  </div>
                  {validationResult.hasHourlyData && (
                    <p className="mt-2 text-blue-700">
                      Hourly data detected - rows aggregated to daily totals
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Validation Errors */}
          {!validationResult.valid && (
            <ValidationErrors errors={validationResult.errors} />
          )}

          {/* Preview */}
          {validationResult.valid && (
            <>
              <ImportPreview data={validationResult.data.slice(0, 10)} />

              {validationResult.data.length > 10 && (
                <p className="text-sm text-gray-600 text-center">
                  Showing first 10 of {validationResult.data.length} rows
                </p>
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
              Import {validationResult.rowCount} Rows
              <ArrowRight className="ml-1 h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {/* Importing Step */}
      {step === "importing" && <ImportProgress progress={uploadProgress} />}

      {/* Success Step */}
      {step === "success" && importResult && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-6">
          <div className="flex items-start gap-3">
            <CheckCircle className="h-6 w-6 text-green-600 mt-0.5" />
            <div className="flex-1">
              <h3 className="font-semibold text-green-900 text-lg mb-2">
                Import Complete!
              </h3>
              <div className="space-y-1 text-green-800">
                <p>Successfully imported {importResult.imported} rows</p>
                {importResult.duplicates !== undefined &&
                  importResult.duplicates > 0 && (
                    <p>Skipped {importResult.duplicates} duplicates</p>
                  )}
                {importResult.date_range && (
                  <p>
                    Date range: {importResult.date_range.start} to{" "}
                    {importResult.date_range.end}
                  </p>
                )}
                {importResult.total_spend !== undefined && (
                  <p>Total spend: ${importResult.total_spend.toFixed(2)}</p>
                )}
              </div>
              <div className="mt-6 flex gap-3">
                <button
                  onClick={() => router.push("/creatives")}
                  className="btn-primary"
                >
                  View Creatives
                  <ArrowRight className="ml-1 h-4 w-4" />
                </button>
                <button onClick={resetForm} className="btn-secondary">
                  Import More Data
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Error Step */}
      {step === "error" && importResult && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-6">
          <div className="flex items-start gap-3">
            <XCircle className="h-6 w-6 text-red-600 mt-0.5" />
            <div className="flex-1">
              <h3 className="font-semibold text-red-900 text-lg mb-2">
                Import Failed
              </h3>
              <p className="text-red-800">{importResult.error}</p>

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
