import { History, RefreshCw, CheckCircle, XCircle } from "lucide-react";
import type { ImportHistoryItem } from "@/lib/api";
import {
  detectReportType,
  getMissingRequiredColumns,
  getRequiredColumns,
} from "@/lib/report-metadata";
import { useTranslation } from "@/contexts/i18n-context";

interface ImportHistorySectionProps {
  history: ImportHistoryItem[];
  loading: boolean;
  onRefresh: () => void;
}

/**
 * Displays recent import history.
 */
export function ImportHistorySection({
  history,
  loading,
  onRefresh,
}: ImportHistorySectionProps) {
  const { t, language } = useTranslation();
  const normalizeColumn = (column: string) =>
    column.replace(/^#/, "").trim().toLowerCase();

  const formatFileSize = (mb: number) => {
    if (mb < 1) return `${(mb * 1024).toFixed(0)} KB`;
    return `${mb.toFixed(1)} MB`;
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return t.import.justNow;
    if (diffMins < 60) return t.import.minutesAgoShort.replace("{count}", String(diffMins));
    if (diffHours < 24) return t.import.hoursAgoShort.replace("{count}", String(diffHours));
    if (diffDays < 7) return t.import.daysAgoShort.replace("{count}", String(diffDays));
    return date.toLocaleDateString(language);
  };

  return (
    <div className="bg-white rounded-lg border border-gray-200">
      <div className="p-4 border-b border-gray-200 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <History className="h-5 w-5 text-gray-400" />
          <h3 className="font-medium text-gray-900">{t.import.recentImports}</h3>
        </div>
        <button
          onClick={onRefresh}
          disabled={loading}
          className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded"
          title={t.common.refresh}
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

      <div className="divide-y divide-gray-100">
        {loading ? (
          <div className="p-8 text-center text-gray-500">
            <RefreshCw className="h-5 w-5 animate-spin mx-auto mb-2" />
            {t.import.loading}
          </div>
        ) : history.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            {t.import.noImportsYet}
          </div>
        ) : (
          history.map((item) => {
            const columns = item.columns_found || [];
            const reportType = detectReportType(columns, item.filename);
            const required = getRequiredColumns(reportType);
            const missing = getMissingRequiredColumns(columns, reportType);
            const missingOptional = (item.columns_missing || []).filter(
              (column) =>
                !missing.some(
                  (requiredColumn) =>
                    normalizeColumn(requiredColumn) === normalizeColumn(column)
                )
            );

            return (
              <div key={item.batch_id} className="px-4 py-3 hover:bg-gray-50">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3 min-w-0">
                      {item.status === "complete" ? (
                        <CheckCircle className="h-5 w-5 text-green-500 flex-shrink-0" />
                  ) : (
                    <XCircle className="h-5 w-5 text-red-500 flex-shrink-0" />
                  )}
                  <div className="min-w-0">
                    <p className="font-medium text-gray-900 truncate">
                      {item.filename || item.batch_id}
                    </p>
                    <p className="text-sm text-gray-500">
                      {formatDate(item.imported_at)} · {formatFileSize(item.file_size_mb)}
                      {reportType !== "unknown" && (
                        <span className="ml-2 text-xs text-gray-400">
                          {reportType.replace("-", " ")}
                        </span>
                      )}
                    </p>
                  </div>
                </div>
                <div className="text-right flex-shrink-0 ml-4">
                  <p className="font-medium text-gray-900">
                    {item.rows_imported.toLocaleString()}
                  </p>
                  <p className="text-sm text-gray-500">{t.import.rows}</p>
                </div>
              </div>
                    {item.rows_duplicate > 0 && (
                      <p className="text-xs text-gray-400 mt-1 ml-8">
                        {t.import.duplicatesSkippedCount.replace(
                          "{count}",
                          item.rows_duplicate.toLocaleString()
                        )}
                      </p>
                    )}
              {columns.length > 0 && (
                <div className="mt-3 ml-8">
                  <div className="flex flex-wrap gap-2">
                    {columns.map((column) => {
                      const isRequired = required.some(
                        (requiredColumn) =>
                          normalizeColumn(requiredColumn) === normalizeColumn(column)
                      );
                      return (
                        <span
                          key={column}
                          className={`text-xs px-2 py-1 rounded-full border ${
                            isRequired
                              ? "border-blue-200 bg-blue-50 text-blue-700"
                              : "border-gray-200 bg-white text-gray-600"
                          }`}
                          title={isRequired ? t.import.requiredColumnTitle : t.import.optionalColumnTitle}
                        >
                          {isRequired ? "[R] " : ""}
                          {column}
                        </span>
                      );
                    })}
                    {missing.map((column) => (
                      <span
                        key={`missing-${column}`}
                        className="text-xs px-2 py-1 rounded-full border border-red-200 bg-red-50 text-red-700"
                        title={t.import.missingRequiredColumnTitle}
                      >
                        [M] {column}
                      </span>
                    ))}
                  </div>
                  {missingOptional.length > 0 && (
                    <p className="text-xs text-gray-400 mt-2">
                      {t.import.missingOptionalColumns
                        .replace("{columns}", missingOptional.join(", "))}
                    </p>
                      )}
                    </div>
                  )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
