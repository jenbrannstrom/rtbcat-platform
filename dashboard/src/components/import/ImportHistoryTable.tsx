import { RefreshCw } from "lucide-react";
import type { ImportHistoryItem } from "@/lib/api";
import { detectReportType } from "@/lib/report-metadata";
import { useTranslation } from "@/contexts/i18n-context";

interface ImportHistoryTableProps {
  history: ImportHistoryItem[];
  loading: boolean;
  onRefresh: () => void;
}

const CSV_TYPE_CONFIG: Record<
  string,
  { number: number; label: string; color: string; bg: string; border: string }
> = {
  quality: {
    number: 1,
    label: "catscan-quality",
    color: "text-blue-700",
    bg: "bg-blue-50",
    border: "border-blue-200",
  },
  bidsinauction: {
    number: 2,
    label: "catscan-bidsinauction",
    color: "text-emerald-700",
    bg: "bg-emerald-50",
    border: "border-emerald-200",
  },
  "pipeline-geo": {
    number: 3,
    label: "catscan-pipeline-geo",
    color: "text-violet-700",
    bg: "bg-violet-50",
    border: "border-violet-200",
  },
  "pipeline-publisher": {
    number: 4,
    label: "catscan-pipeline",
    color: "text-teal-700",
    bg: "bg-teal-50",
    border: "border-teal-200",
  },
  "bid-filtering": {
    number: 5,
    label: "catscan-bid-filtering",
    color: "text-fuchsia-700",
    bg: "bg-fuchsia-50",
    border: "border-fuchsia-200",
  },
};

function formatTriggerLabel(trigger?: string | null): string {
  if (trigger === "gmail-auto") return "auto";
  return "manual";
}

export function ImportHistoryTable({
  history,
  loading,
  onRefresh,
}: ImportHistoryTableProps) {
  const { t, language } = useTranslation();

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString(language, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  return (
    <div className="bg-white rounded-lg border border-gray-200">
      <div className="p-4 border-b border-gray-200 flex items-center justify-between">
        <h3 className="font-medium text-gray-900">{t.import.recentImports}</h3>
        <button
          onClick={onRefresh}
          disabled={loading}
          className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded"
          title={t.common.refresh}
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

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
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left font-medium text-gray-700 px-4 py-2">
                  {t.import.historyColumnDate}
                </th>
                <th className="text-left font-medium text-gray-700 px-4 py-2">
                  CSV
                </th>
                <th className="text-left font-medium text-gray-700 px-4 py-2">
                  {t.import.historyColumnRows}
                </th>
                <th className="text-left font-medium text-gray-700 px-4 py-2">
                  {t.import.historyColumnResult}
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {history.map((item) => {
                const columns = item.columns_found || [];
                const reportType = detectReportType(columns, item.filename);
                const csvConfig = CSV_TYPE_CONFIG[reportType];
                const isSuccess = item.status === "complete";
                const triggerLabel = formatTriggerLabel(item.import_trigger);

                return (
                  <tr key={item.batch_id} className="hover:bg-gray-50">
                    <td className="px-4 py-2.5 text-gray-700 whitespace-nowrap">
                      {formatDate(item.imported_at)}
                    </td>
                    <td className="px-4 py-2.5">
                      {csvConfig ? (
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${csvConfig.color} ${csvConfig.bg} ${csvConfig.border}`}
                        >
                          ({csvConfig.number}) {csvConfig.label}
                        </span>
                      ) : (
                        <span className="text-xs text-gray-500">
                          {item.filename || "unknown"}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-gray-700 tabular-nums">
                      {item.rows_imported.toLocaleString()}
                    </td>
                    <td className="px-4 py-2.5">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                          isSuccess
                            ? "bg-green-50 text-green-700 border border-green-200"
                            : "bg-red-50 text-red-700 border border-red-200"
                        }`}
                      >
                        {triggerLabel}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
