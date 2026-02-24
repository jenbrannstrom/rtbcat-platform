import { CheckCircle, XCircle, ArrowRight } from "lucide-react";
import type { ImportResponse } from "@/lib/types/import";
import { useTranslation } from "@/contexts/i18n-context";

interface ImportResultCardProps {
  result: ImportResponse;
  onReset: () => void;
  onViewCreatives: () => void;
}

/**
 * Displays the result of an import operation.
 */
export function ImportResultCard({
  result,
  onReset,
  onViewCreatives
}: ImportResultCardProps) {
  const { t } = useTranslation();
  // Success if backend says success AND we processed rows (imported or duplicates)
  const success = result.success !== false && ((result.imported ?? 0) > 0 || (result.duplicates ?? 0) > 0);

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
            {success
              ? ((result.imported ?? 0) === 0 && (result.duplicates ?? 0) > 0
                  ? t.import.alreadyImported
                  : t.import.importSuccessful)
              : t.import.importFailed}
          </h3>

          {/* Stats Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            <div>
              <p className="text-gray-500 text-sm">{t.import.rowsImported}</p>
              <p className={`font-bold text-xl ${success ? "text-green-700" : "text-gray-700"}`}>
                {(result.imported ?? 0).toLocaleString()}
              </p>
            </div>
            {result.duplicates !== undefined && result.duplicates > 0 && (
              <div>
                <p className="text-gray-500 text-sm">{t.import.duplicatesSkipped}</p>
                <p className="font-medium text-gray-600">{result.duplicates.toLocaleString()}</p>
              </div>
            )}
            {result.date_range && (
              <div className="col-span-2">
                <p className="text-gray-500 text-sm">{t.import.dateRange}</p>
                <p className="font-medium text-gray-700">
                  {result.date_range.start} → {result.date_range.end}
                </p>
              </div>
            )}
            {result.total_spend !== undefined && result.total_spend > 0 && (
              <div>
                <p className="text-gray-500 text-sm">{t.import.totalSpend}</p>
                <p className="font-medium text-gray-700">
                  ${result.total_spend.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </p>
              </div>
            )}
          </div>

          {/* Columns Imported */}
          {success && result.columns_imported && result.columns_imported.length > 0 && (
            <div className="mb-4">
              <p className="text-gray-500 text-sm mb-2">{t.import.columnsImported}</p>
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
          {!result.error && Array.isArray(result.errors) && result.errors.length > 0 && (
            <p className="text-red-700 mb-4">{String(result.errors[0])}</p>
          )}

          {/* Missing required columns */}
          {result.required_missing && result.required_missing.length > 0 && (
            <div className="mb-4 p-3 bg-red-100 rounded-lg">
              <p className="text-red-800 text-sm font-medium mb-1">{t.import.missingRequiredColumns}</p>
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
                    {t.import.howToFix}
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
                {t.import.viewCreatives}
                <ArrowRight className="ml-1 h-4 w-4" />
              </button>
            )}
            <button onClick={onReset} className="btn-secondary">
              {success ? t.import.importMoreData : t.import.tryAgain}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
