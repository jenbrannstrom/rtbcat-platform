import { useState } from "react";
import { RefreshCw } from "lucide-react";
import type { DataFreshnessGridResponse, FreshnessStatus } from "@/lib/api";

interface DataFreshnessGridProps {
  grid: DataFreshnessGridResponse | null;
  loading: boolean;
  selectedDays: number;
  onDaysChange: (days: number) => void;
  onRefresh: () => void;
}

const CSV_TYPE_LABELS: Record<string, string> = {
  quality: "Quality",
  bidsinauction: "Performance",
  "pipeline-geo": "Geo",
  "pipeline-publisher": "Publisher",
  "bid-filtering": "Filtering",
};

const DAY_OPTIONS = [7, 14, 30] as const;

function formatDateLabel(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function getCoverageBadgeClass(pct: number): string {
  if (pct >= 90) return "bg-green-100 text-green-800";
  if (pct >= 70) return "bg-yellow-100 text-yellow-800";
  return "bg-red-100 text-red-800";
}

function CellTooltip({
  date,
  csvType,
  status,
  children,
}: {
  date: string;
  csvType: string;
  status: FreshnessStatus;
  children: React.ReactNode;
}) {
  const [show, setShow] = useState(false);
  const label = CSV_TYPE_LABELS[csvType] || csvType;
  const statusText = status === "imported" ? "Data present" : "No data";

  return (
    <div
      className="relative inline-block"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      {children}
      {show && (
        <div className="absolute z-10 bottom-full left-1/2 -translate-x-1/2 mb-1.5 px-2 py-1 text-xs rounded bg-gray-900 text-white whitespace-nowrap pointer-events-none">
          {formatDateLabel(date)} — {label}: {statusText}
        </div>
      )}
    </div>
  );
}

export function DataFreshnessGrid({
  grid,
  loading,
  selectedDays,
  onDaysChange,
  onRefresh,
}: DataFreshnessGridProps) {
  const coveragePct = grid?.summary.coverage_pct ?? 0;

  return (
    <div className="bg-white rounded-lg border border-gray-200">
      {/* Header */}
      <div className="p-4 border-b border-gray-200">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1">
            <div className="flex items-center gap-3">
              <h3 className="font-medium text-gray-900">Data Freshness</h3>
              {grid && (
                <span
                  className={`px-2 py-0.5 rounded-full text-xs font-medium ${getCoverageBadgeClass(coveragePct)}`}
                >
                  {coveragePct}% coverage
                </span>
              )}
            </div>
            <p className="text-xs text-gray-500 mt-1">
              Does the last {selectedDays} days have data?
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

        {/* Day toggle pills */}
        <div className="mt-3 flex gap-1.5">
          {DAY_OPTIONS.map((d) => (
            <button
              key={d}
              onClick={() => onDaysChange(d)}
              className={`px-3 py-1 text-xs font-medium rounded-full transition-colors ${
                selectedDays === d
                  ? "bg-gray-900 text-white"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
            >
              {d} days
            </button>
          ))}
        </div>
      </div>

      {/* Grid body */}
      {loading ? (
        <div className="p-8 text-center text-gray-500">
          <RefreshCw className="h-5 w-5 animate-spin mx-auto mb-2" />
          Loading freshness data...
        </div>
      ) : !grid || grid.dates.length === 0 ? (
        <div className="p-8 text-center text-gray-500">
          No data freshness information available.
        </div>
      ) : (
        <div className="p-4 overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr>
                <th className="text-left text-xs font-medium text-gray-500 pb-2 pr-3 w-20" />
                {grid.csv_types.map((ct) => (
                  <th
                    key={ct}
                    className="text-center text-xs font-medium text-gray-500 pb-2 px-1"
                  >
                    {CSV_TYPE_LABELS[ct] || ct}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {grid.dates.map((date) => (
                <tr key={date}>
                  <td className="text-xs text-gray-600 pr-3 py-0.5 whitespace-nowrap">
                    {formatDateLabel(date)}
                  </td>
                  {grid.csv_types.map((ct) => {
                    const status: FreshnessStatus =
                      (grid.cells[date]?.[ct] as FreshnessStatus) || "missing";
                    return (
                      <td key={ct} className="px-1 py-0.5 text-center">
                        <CellTooltip date={date} csvType={ct} status={status}>
                          <div
                            className={`w-8 h-6 rounded mx-auto ${
                              status === "imported"
                                ? "bg-green-500"
                                : "bg-gray-200"
                            }`}
                          />
                        </CellTooltip>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>

          {/* Legend */}
          <div className="mt-3 flex items-center gap-4 text-xs text-gray-500">
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-3 rounded bg-green-500" />
              <span>Data present</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-3 rounded bg-gray-200" />
              <span>No data</span>
            </div>
            {grid.summary && (
              <span className="ml-auto text-gray-400">
                {grid.summary.imported_count}/{grid.summary.total_cells} cells
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
