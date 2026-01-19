import { History, RefreshCw, CheckCircle, XCircle } from "lucide-react";
import type { ImportHistoryItem } from "@/lib/api";

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
  const normalizeColumn = (column: string) =>
    column.replace(/^#/, "").trim().toLowerCase();

  const detectReportType = (columns: string[], filename?: string | null) => {
    const normalized = new Set(columns.map(normalizeColumn));
    const name = (filename || "").toLowerCase();

    if (normalized.has("bid filtering reason") || name.includes("bid-filtering")) {
      return "bid-filtering";
    }
    if (normalized.has("bid requests") || name.includes("pipeline")) {
      if (normalized.has("publisher id") || name.includes("rtb-pipeline")) {
        return "pipeline-publisher";
      }
      return "pipeline-geo";
    }
    if (normalized.has("billing id") && normalized.has("creative id")) {
      return "quality";
    }
    if (normalized.has("bids in auction") && normalized.has("creative id")) {
      return "bidsinauction";
    }
    return "unknown";
  };

  const REQUIRED_COLUMNS: Record<string, string[]> = {
    "quality": [
      "Buyer account ID",
      "Billing ID",
      "Creative ID",
      "Creative size",
      "Day",
      "Country",
      "Reached queries",
      "Impressions",
    ],
    "bidsinauction": [
      "Buyer account ID",
      "Country",
      "Creative ID",
      "Day",
      "Hour",
      "Bids in auction",
      "Auctions won",
      "Bids",
    ],
    "pipeline-geo": [
      "Buyer account ID",
      "Country",
      "Day",
      "Hour",
      "Bid requests",
    ],
    "pipeline-publisher": [
      "Buyer account ID",
      "Country",
      "Publisher ID",
      "Day",
      "Hour",
      "Bid requests",
    ],
    "bid-filtering": [
      "Buyer account ID",
      "Country",
      "Creative ID",
      "Bid filtering reason",
      "Day",
      "Hour",
      "Bids",
    ],
    "unknown": [],
  };

  const getRequiredMissing = (columns: string[], filename?: string | null) => {
    const reportType = detectReportType(columns, filename);
    const required = REQUIRED_COLUMNS[reportType] || [];
    const normalized = new Set(columns.map(normalizeColumn));
    const missing = required.filter(
      (column) => !normalized.has(normalizeColumn(column))
    );
    return { reportType, required, missing };
  };

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

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  return (
    <div className="bg-white rounded-lg border border-gray-200">
      <div className="p-4 border-b border-gray-200 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <History className="h-5 w-5 text-gray-400" />
          <h3 className="font-medium text-gray-900">Recent Imports</h3>
        </div>
        <button
          onClick={onRefresh}
          disabled={loading}
          className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded"
          title="Refresh"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

      <div className="divide-y divide-gray-100">
        {loading ? (
          <div className="p-8 text-center text-gray-500">
            <RefreshCw className="h-5 w-5 animate-spin mx-auto mb-2" />
            Loading...
          </div>
        ) : history.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            No imports yet. Upload your first CSV above.
          </div>
        ) : (
          history.map((item) => {
            const columns = item.columns_found || [];
            const { reportType, required, missing } = getRequiredMissing(
              columns,
              item.filename
            );
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
                  <p className="text-sm text-gray-500">rows</p>
                </div>
              </div>
                    {item.rows_duplicate > 0 && (
                      <p className="text-xs text-gray-400 mt-1 ml-8">
                        {item.rows_duplicate.toLocaleString()} duplicates skipped
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
                          title={isRequired ? "Required column" : "Optional column"}
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
                        title="Missing required column"
                      >
                        [M] {column}
                      </span>
                    ))}
                  </div>
                  {missingOptional.length > 0 && (
                    <p className="text-xs text-gray-400 mt-2">
                      Missing optional: {missingOptional.join(", ")}
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
