"use client";

import { useEffect, useState } from "react";
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
} from "lucide-react";
import {
  getUploadTracking,
  getImportHistory,
  type DailyUploadSummary,
  type UploadTrackingResponse,
  type ImportHistoryItem,
} from "@/lib/api";

export default function UploadsPage() {
  const [tracking, setTracking] = useState<UploadTrackingResponse | null>(null);
  const [history, setHistory] = useState<ImportHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(30);

  useEffect(() => {
    async function loadData() {
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
    }
    loadData();
  }, [days]);

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString("en-US", {
      weekday: "short",
      month: "short",
      day: "numeric",
    });
  };

  const formatNumber = (num: number) => {
    return num.toLocaleString();
  };

  const formatFileSize = (mb: number) => {
    if (mb < 1) return `${(mb * 1024).toFixed(0)} KB`;
    return `${mb.toFixed(1)} MB`;
  };

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center min-h-[400px]">
        <RefreshCw className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-800">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Upload Tracking</h1>
        <p className="text-gray-600 mt-1">
          Monitor CSV import history and data quality
        </p>
      </div>

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
    </div>
  );
}

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
