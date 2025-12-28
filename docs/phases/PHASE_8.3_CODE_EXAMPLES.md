# Phase 8.3: Code Examples - CSV Import UI

**Companion to:** PHASE_8.3_PROMPT.md  
**Purpose:** Production-ready code for CSV upload and validation

---

## 📁 Component Structure

```
dashboard/
├── app/
│   └── import/
│       └── page.tsx              # Main import page
├── components/
│   ├── ImportDropzone.tsx        # File upload dropzone
│   ├── ImportPreview.tsx         # Data preview table
│   ├── ImportProgress.tsx        # Upload progress
│   └── ValidationErrors.tsx      # Error display
└── lib/
    ├── csv-validator.ts          # Validation logic
    ├── csv-parser.ts             # CSV parsing
    └── api.ts                    # API integration (update)
```

---

## 🔧 TypeScript Types

### `lib/types/import.ts`

```typescript
export interface PerformanceRow {
  creative_id: number;
  date: string; // YYYY-MM-DD
  impressions: number;
  clicks: number;
  spend: number;
  geography?: string; // 2-letter code
}

export interface ValidationError {
  row: number;
  field: string;
  error: string;
  value: any;
}

export interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
  rowCount: number;
  data: PerformanceRow[];
}

export interface ImportResponse {
  success: boolean;
  imported: number;
  duplicates?: number;
  errors?: number;
  error_details?: ValidationError[];
  date_range?: {
    start: string;
    end: string;
  };
  total_spend?: number;
  error?: string;
}
```

---

## 🎨 Components

### 1. Import Page

**`app/import/page.tsx`**

```typescript
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { ImportDropzone } from '@/components/ImportDropzone';
import { ImportPreview } from '@/components/ImportPreview';
import { ImportProgress } from '@/components/ImportProgress';
import { ValidationErrors } from '@/components/ValidationErrors';
import { validatePerformanceCSV } from '@/lib/csv-validator';
import { parseCSV } from '@/lib/csv-parser';
import { importPerformanceData } from '@/lib/api';
import type { ValidationResult, ImportResponse, PerformanceRow } from '@/lib/types/import';

type ImportStep = 'upload' | 'preview' | 'importing' | 'success' | 'error';

export default function ImportPage() {
  const router = useRouter();
  
  const [step, setStep] = useState<ImportStep>('upload');
  const [file, setFile] = useState<File | null>(null);
  const [validationResult, setValidationResult] = useState<ValidationResult | null>(null);
  const [importResult, setImportResult] = useState<ImportResponse | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);

  // Handle file selection
  const handleFileSelect = async (selectedFile: File) => {
    setFile(selectedFile);
    setStep('preview');
    
    try {
      // Parse CSV
      const parsedData = await parseCSV(selectedFile);
      
      // Validate
      const validation = validatePerformanceCSV(parsedData);
      setValidationResult(validation);
      
    } catch (error) {
      console.error('CSV parsing error:', error);
      setValidationResult({
        valid: false,
        errors: [{
          row: 0,
          field: 'file',
          error: 'Failed to parse CSV file. Please check the file format.',
          value: null
        }],
        rowCount: 0,
        data: []
      });
    }
  };

  // Handle import
  const handleImport = async () => {
    if (!file || !validationResult?.valid) return;
    
    setStep('importing');
    setUploadProgress(0);
    
    try {
      const result = await importPerformanceData(file, (progress) => {
        setUploadProgress(progress);
      });
      
      setImportResult(result);
      setStep('success');
      
      // Redirect to creatives page after 3 seconds
      setTimeout(() => {
        router.push('/creatives?sort=performance&period=7d');
      }, 3000);
      
    } catch (error) {
      console.error('Import error:', error);
      setImportResult({
        success: false,
        imported: 0,
        error: error instanceof Error ? error.message : 'Import failed'
      });
      setStep('error');
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
    
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'performance_data_example.csv';
    a.click();
    window.URL.revokeObjectURL(url);
  };

  return (
    <div className="container mx-auto px-4 py-8 max-w-4xl">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">
          Import Performance Data
        </h1>
        <p className="text-gray-600 mt-2">
          Upload CSV file with creative performance metrics
        </p>
      </div>

      {/* Upload Step */}
      {step === 'upload' && (
        <div className="space-y-6">
          <ImportDropzone onFileSelect={handleFileSelect} />
          
          <div className="bg-gray-50 rounded-lg p-6">
            <h3 className="font-semibold text-gray-900 mb-3">
              Expected CSV Format
            </h3>
            <code className="block bg-white p-3 rounded text-sm">
              creative_id,date,impressions,clicks,spend,geography
            </code>
            <div className="mt-4">
              <button
                onClick={downloadExample}
                className="text-blue-600 hover:text-blue-700 text-sm font-medium"
              >
                📥 Download Example CSV
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Preview Step */}
      {step === 'preview' && validationResult && (
        <div className="space-y-6">
          {/* File Info */}
          <div className="bg-gray-50 rounded-lg p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium text-gray-900">{file?.name}</p>
                <p className="text-sm text-gray-600">
                  {(file!.size / 1024).toFixed(2)} KB · {validationResult.rowCount} rows
                </p>
              </div>
              <button
                onClick={() => {
                  setFile(null);
                  setValidationResult(null);
                  setStep('upload');
                }}
                className="text-sm text-gray-600 hover:text-gray-800"
              >
                Remove
              </button>
            </div>
          </div>

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
            <button
              onClick={() => {
                setFile(null);
                setValidationResult(null);
                setStep('upload');
              }}
              className="px-4 py-2 border border-gray-300 rounded-md 
                         hover:bg-gray-50 text-gray-700"
            >
              Cancel
            </button>
            <button
              onClick={handleImport}
              disabled={!validationResult.valid}
              className="px-4 py-2 bg-blue-600 text-white rounded-md 
                         hover:bg-blue-700 disabled:bg-gray-300 
                         disabled:cursor-not-allowed"
            >
              Import {validationResult.rowCount} Rows →
            </button>
          </div>
        </div>
      )}

      {/* Importing Step */}
      {step === 'importing' && (
        <ImportProgress progress={uploadProgress} />
      )}

      {/* Success Step */}
      {step === 'success' && importResult && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-6">
          <div className="flex items-start gap-3">
            <div className="text-green-600 text-2xl">✅</div>
            <div className="flex-1">
              <h3 className="font-semibold text-green-900 text-lg mb-2">
                Import Complete!
              </h3>
              <div className="space-y-1 text-green-800">
                <p>📊 Successfully imported {importResult.imported} rows</p>
                {importResult.duplicates && importResult.duplicates > 0 && (
                  <p>🔄 Skipped {importResult.duplicates} duplicates</p>
                )}
                {importResult.date_range && (
                  <p>
                    ⏱️ Date range: {importResult.date_range.start} to{' '}
                    {importResult.date_range.end}
                  </p>
                )}
                {importResult.total_spend && (
                  <p>💰 Total spend: ${importResult.total_spend.toFixed(2)}</p>
                )}
              </div>
              <p className="text-green-700 mt-4 text-sm">
                Redirecting to creatives page...
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Error Step */}
      {step === 'error' && importResult && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-6">
          <div className="flex items-start gap-3">
            <div className="text-red-600 text-2xl">❌</div>
            <div className="flex-1">
              <h3 className="font-semibold text-red-900 text-lg mb-2">
                Import Failed
              </h3>
              <p className="text-red-800">{importResult.error}</p>
              
              {importResult.error_details && importResult.error_details.length > 0 && (
                <div className="mt-4">
                  <ValidationErrors errors={importResult.error_details} />
                </div>
              )}
              
              <div className="mt-4">
                <button
                  onClick={() => {
                    setFile(null);
                    setValidationResult(null);
                    setImportResult(null);
                    setStep('upload');
                  }}
                  className="px-4 py-2 bg-red-600 text-white rounded-md 
                             hover:bg-red-700"
                >
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
```

---

### 2. Import Dropzone Component

**`components/ImportDropzone.tsx`**

```typescript
'use client';

import { useState, useCallback } from 'react';

interface ImportDropzoneProps {
  onFileSelect: (file: File) => void;
  maxSizeMB?: number;
}

export function ImportDropzone({ 
  onFileSelect, 
  maxSizeMB = 10 
}: ImportDropzoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const validateFile = (file: File): string | null => {
    // Check file type
    if (!file.name.endsWith('.csv')) {
      return 'Please upload a .csv file';
    }
    
    // Check file size
    const maxBytes = maxSizeMB * 1024 * 1024;
    if (file.size > maxBytes) {
      return `File size exceeds ${maxSizeMB}MB limit`;
    }
    
    return null;
  };

  const handleFile = (file: File) => {
    const validationError = validateFile(file);
    
    if (validationError) {
      setError(validationError);
      return;
    }
    
    setError(null);
    onFileSelect(file);
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      handleFile(files[0]);
    }
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleClick = () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.csv';
    input.onchange = (e) => {
      const files = (e.target as HTMLInputElement).files;
      if (files && files.length > 0) {
        handleFile(files[0]);
      }
    };
    input.click();
  };

  return (
    <div>
      <div
        onClick={handleClick}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        className={`
          border-2 border-dashed rounded-lg p-12 text-center cursor-pointer
          transition-colors
          ${isDragging 
            ? 'border-blue-500 bg-blue-50' 
            : 'border-gray-300 hover:border-gray-400 bg-gray-50'
          }
        `}
      >
        <div className="text-6xl mb-4">
          {isDragging ? '↓' : '📁'}
        </div>
        <p className="text-lg font-medium text-gray-900 mb-2">
          {isDragging 
            ? 'Drop file to upload' 
            : 'Drag & drop CSV file here'
          }
        </p>
        <p className="text-sm text-gray-600">
          or click to browse
        </p>
        <p className="text-xs text-gray-500 mt-2">
          Max file size: {maxSizeMB}MB
        </p>
      </div>
      
      {error && (
        <div className="mt-3 text-sm text-red-600">
          ❌ {error}
        </div>
      )}
    </div>
  );
}
```

---

### 3. Import Preview Component

**`components/ImportPreview.tsx`**

```typescript
import type { PerformanceRow } from '@/lib/types/import';

interface ImportPreviewProps {
  data: PerformanceRow[];
}

export function ImportPreview({ data }: ImportPreviewProps) {
  if (data.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        No data to preview
      </div>
    );
  }

  return (
    <div className="border rounded-lg overflow-hidden">
      <div className="bg-gray-50 px-4 py-3 border-b">
        <h3 className="font-semibold text-gray-900">
          Preview (first {data.length} rows)
        </h3>
      </div>
      
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                Creative ID
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                Date
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                Impressions
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                Clicks
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                Spend
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                Geo
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {data.map((row, index) => (
              <tr key={index} className="hover:bg-gray-50">
                <td className="px-4 py-3 text-sm text-gray-900">
                  {row.creative_id}
                </td>
                <td className="px-4 py-3 text-sm text-gray-900">
                  {row.date}
                </td>
                <td className="px-4 py-3 text-sm text-gray-900 text-right">
                  {row.impressions.toLocaleString()}
                </td>
                <td className="px-4 py-3 text-sm text-gray-900 text-right">
                  {row.clicks.toLocaleString()}
                </td>
                <td className="px-4 py-3 text-sm text-gray-900 text-right">
                  ${row.spend.toFixed(2)}
                </td>
                <td className="px-4 py-3 text-sm text-gray-900">
                  {row.geography || '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

---

### 4. Validation Errors Component

**`components/ValidationErrors.tsx`**

```typescript
import type { ValidationError } from '@/lib/types/import';

interface ValidationErrorsProps {
  errors: ValidationError[];
  maxShow?: number;
}

export function ValidationErrors({ errors, maxShow = 10 }: ValidationErrorsProps) {
  const displayErrors = errors.slice(0, maxShow);
  const remaining = errors.length - maxShow;

  return (
    <div className="bg-red-50 border border-red-200 rounded-lg p-4">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-red-600 text-xl">❌</span>
        <h3 className="font-semibold text-red-900">
          {errors.length} Validation {errors.length === 1 ? 'Error' : 'Errors'}
        </h3>
      </div>
      
      <div className="space-y-2 max-h-60 overflow-y-auto">
        {displayErrors.map((error, index) => (
          <div key={index} className="text-sm text-red-800">
            <span className="font-medium">
              Row {error.row}
              {error.field && ` (${error.field})`}:
            </span>{' '}
            {error.error}
            {error.value !== null && error.value !== undefined && (
              <span className="text-red-600 ml-1">
                (got: {JSON.stringify(error.value)})
              </span>
            )}
          </div>
        ))}
      </div>
      
      {remaining > 0 && (
        <div className="mt-3 text-sm text-red-700">
          ... and {remaining} more error{remaining === 1 ? '' : 's'}
        </div>
      )}
    </div>
  );
}
```

---

### 5. Import Progress Component

**`components/ImportProgress.tsx`**

```typescript
interface ImportProgressProps {
  progress: number; // 0-100
}

export function ImportProgress({ progress }: ImportProgressProps) {
  return (
    <div className="bg-white border rounded-lg p-8">
      <div className="text-center mb-6">
        <div className="text-4xl mb-4">☁️</div>
        <h3 className="text-lg font-semibold text-gray-900 mb-2">
          Importing Data...
        </h3>
        <p className="text-sm text-gray-600">
          Please wait while we process your file
        </p>
      </div>
      
      <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
        <div
          className="bg-blue-600 h-full transition-all duration-300 ease-out"
          style={{ width: `${progress}%` }}
        />
      </div>
      
      <div className="text-center mt-3 text-sm text-gray-600">
        {progress}%
      </div>
    </div>
  );
}
```

---

## 🔌 API Integration

### Update `lib/api.ts`

```typescript
import type { ImportResponse } from '@/lib/types/import';

/**
 * Import performance data from CSV file
 */
export async function importPerformanceData(
  file: File,
  onProgress?: (progress: number) => void
): Promise<ImportResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch('/api/performance/import', {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Import failed');
  }

  const result: ImportResponse = await response.json();
  
  if (onProgress) {
    onProgress(100);
  }
  
  return result;
}
```

---

## 🧪 CSV Parser

### `lib/csv-parser.ts`

```typescript
import Papa from 'papaparse';
import type { PerformanceRow } from '@/lib/types/import';

export function parseCSV(file: File): Promise<PerformanceRow[]> {
  return new Promise((resolve, reject) => {
    Papa.parse(file, {
      header: true,
      skipEmptyLines: true,
      transformHeader: (header) => header.trim().toLowerCase(),
      complete: (results) => {
        try {
          const data = results.data.map((row: any) => ({
            creative_id: parseInt(row.creative_id),
            date: row.date,
            impressions: parseInt(row.impressions),
            clicks: parseInt(row.clicks),
            spend: parseFloat(row.spend),
            geography: row.geography || undefined,
          }));
          
          resolve(data);
        } catch (error) {
          reject(error);
        }
      },
      error: (error) => {
        reject(error);
      },
    });
  });
}
```

---

## ✅ Complete validation logic available in PHASE_8.3_PROMPT.md

---

**These components are production-ready. Install papaparse and start building! 🚀**
