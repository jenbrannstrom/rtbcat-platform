import { CheckCircle2, Clock, RefreshCw, XCircle } from "lucide-react";
import type { ImportTrackingMatrixResponse, ImportMatrixCell } from "@/lib/api";

interface ImportTrackingMatrixSectionProps {
  matrix: ImportTrackingMatrixResponse | null;
  loading: boolean;
  onRefresh: () => void;
}

const CSV_TYPE_LABELS: Record<string, string> = {
  quality: "Quality",
  bidsinauction: "Bids In Auction",
  "pipeline-geo": "Pipeline Geo",
  "pipeline-publisher": "Pipeline Publisher",
  "bid-filtering": "Bid Filtering",
};

const SOURCE_LABELS: Record<string, string> = {
  manual: "Manual Upload",
  "gmail-auto": "Gmail Auto",
  "gmail-manual": "Gmail Manual",
};

function formatRelativeTime(value?: string | null): string {
  if (!value) return "-";

  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.getTime())) return "-";

  const diffMs = Date.now() - timestamp.getTime();
  const minutes = Math.floor(diffMs / 60000);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days < 14) return `${days}d ago`;
  return timestamp.toLocaleDateString();
}

function getStatusStyles(status: ImportMatrixCell["status"]): string {
  if (status === "pass") return "bg-green-50 text-green-700 border-green-200";
  if (status === "fail") return "bg-red-50 text-red-700 border-red-200";
  return "bg-gray-50 text-gray-600 border-gray-200";
}

function renderStatus(status: ImportMatrixCell["status"]) {
  if (status === "pass") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium bg-green-50 text-green-700 border-green-200">
        <CheckCircle2 className="h-3.5 w-3.5" />
        Pass
      </span>
    );
  }

  if (status === "fail") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium bg-red-50 text-red-700 border-red-200">
        <XCircle className="h-3.5 w-3.5" />
        Fail
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium bg-gray-50 text-gray-600 border-gray-200">
      <Clock className="h-3.5 w-3.5" />
      Not Imported
    </span>
  );
}

export function ImportTrackingMatrixSection({
  matrix,
  loading,
  onRefresh,
}: ImportTrackingMatrixSectionProps) {
  const rows = (matrix?.accounts || []).flatMap((account) =>
    account.csv_types.map((cell) => ({
      buyerId: account.buyer_id,
      displayName: account.display_name || account.buyer_id,
      csvType: cell.csv_type,
      status: cell.status,
      source: cell.source,
      lastImportedAt: cell.last_imported_at,
      errorSummary: cell.error_summary,
    }))
  );

  return (
    <div className="bg-white rounded-lg border border-gray-200">
      <div className="p-4 border-b border-gray-200">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="font-medium text-gray-900">Import Coverage Matrix</h3>
            <p className="text-xs text-gray-500 mt-1">
              Account x CSV type status: pass, fail, or not imported
            </p>
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
        {matrix && (
          <div className="mt-3 flex flex-wrap gap-2 text-xs">
            <span className="px-2 py-1 rounded border border-gray-200 text-gray-700">
              Accounts: {matrix.total_accounts}
            </span>
            <span className={`px-2 py-1 rounded border ${getStatusStyles("pass")}`}>
              Pass: {matrix.pass_count}
            </span>
            <span className={`px-2 py-1 rounded border ${getStatusStyles("fail")}`}>
              Fail: {matrix.fail_count}
            </span>
            <span className={`px-2 py-1 rounded border ${getStatusStyles("not_imported")}`}>
              Not imported: {matrix.not_imported_count}
            </span>
          </div>
        )}
      </div>

      {loading ? (
        <div className="p-8 text-center text-gray-500">
          <RefreshCw className="h-5 w-5 animate-spin mx-auto mb-2" />
          Loading matrix...
        </div>
      ) : rows.length === 0 ? (
        <div className="p-8 text-center text-gray-500">
          No import coverage data yet.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left font-medium text-gray-700 px-4 py-2">Account</th>
                <th className="text-left font-medium text-gray-700 px-4 py-2">CSV Type</th>
                <th className="text-left font-medium text-gray-700 px-4 py-2">Status</th>
                <th className="text-left font-medium text-gray-700 px-4 py-2">Source</th>
                <th className="text-left font-medium text-gray-700 px-4 py-2">Last Import</th>
                <th className="text-left font-medium text-gray-700 px-4 py-2">Error</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {rows.map((row) => (
                <tr key={`${row.buyerId}-${row.csvType}`}>
                  <td className="px-4 py-2 text-gray-900">
                    <div className="font-medium truncate">{row.displayName}</div>
                    {row.displayName !== row.buyerId && (
                      <div className="text-xs text-gray-500">{row.buyerId}</div>
                    )}
                  </td>
                  <td className="px-4 py-2 text-gray-800">
                    {CSV_TYPE_LABELS[row.csvType] || row.csvType}
                  </td>
                  <td className="px-4 py-2">{renderStatus(row.status)}</td>
                  <td className="px-4 py-2 text-gray-700">
                    {row.status === "not_imported"
                      ? "-"
                      : SOURCE_LABELS[row.source || ""] || "Manual Upload"}
                  </td>
                  <td className="px-4 py-2 text-gray-700">
                    {row.status === "not_imported"
                      ? "-"
                      : formatRelativeTime(row.lastImportedAt)}
                  </td>
                  <td className="px-4 py-2 text-gray-500 max-w-[280px] truncate" title={row.errorSummary || ""}>
                    {row.status === "fail" ? (row.errorSummary || "-") : "-"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
