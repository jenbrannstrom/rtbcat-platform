"use client";

import { AlertTriangle, TrendingDown, Calendar, Clock, Ban, Plus, Maximize, Eye } from "lucide-react";
import type { WasteReport } from "@/types/api";
import { cn } from "@/lib/utils";

interface WasteReportProps {
  report: WasteReport;
  isLoading?: boolean;
}

function formatNumber(num: number): string {
  if (num >= 1000000) {
    return `${(num / 1000000).toFixed(1)}M`;
  }
  if (num >= 1000) {
    return `${(num / 1000).toFixed(1)}K`;
  }
  return num.toLocaleString();
}

function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function getWasteColor(percentage: number): string {
  if (percentage < 10) return "text-green-600";
  if (percentage < 30) return "text-yellow-600";
  return "text-red-600";
}

function getWasteBgColor(percentage: number): string {
  if (percentage < 10) return "bg-green-50 border-green-200";
  if (percentage < 30) return "bg-yellow-50 border-yellow-200";
  return "bg-red-50 border-red-200";
}

export function WasteReportSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="bg-gray-100 rounded-lg h-28" />
        ))}
      </div>
      <div className="bg-gray-100 rounded-lg h-20" />
    </div>
  );
}

export function WasteReportEmpty() {
  return (
    <div className="text-center py-12 px-4">
      <AlertTriangle className="mx-auto h-12 w-12 text-gray-400" />
      <h3 className="mt-4 text-lg font-medium text-gray-900">No Traffic Data</h3>
      <p className="mt-2 text-sm text-gray-500 max-w-md mx-auto">
        There&apos;s no RTB traffic data to analyze yet. Generate mock traffic data or import real
        traffic data to see waste analysis.
      </p>
    </div>
  );
}

export function WasteReportCard({ report, isLoading }: WasteReportProps) {
  if (isLoading) {
    return <WasteReportSkeleton />;
  }

  if (report.total_requests === 0) {
    return <WasteReportEmpty />;
  }

  const summary = report.recommendations_summary;

  return (
    <div className="space-y-6">
      {/* Main Metrics Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {/* Waste Percentage - Hero Card */}
        <div
          className={cn(
            "relative overflow-hidden rounded-xl border-2 p-6",
            getWasteBgColor(report.waste_percentage)
          )}
        >
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Waste Rate</p>
              <p className={cn("text-4xl font-bold mt-1", getWasteColor(report.waste_percentage))}>
                {report.waste_percentage.toFixed(1)}%
              </p>
              <p className="text-xs text-gray-500 mt-2">
                {formatNumber(report.total_waste_requests)} of {formatNumber(report.total_requests)} requests
              </p>
            </div>
            <AlertTriangle className={cn("h-8 w-8", getWasteColor(report.waste_percentage))} />
          </div>
        </div>

        {/* Potential Savings */}
        <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Potential Savings</p>
              <p className="text-3xl font-bold text-gray-900 mt-1">
                {report.potential_savings_qps.toFixed(1)} <span className="text-lg font-normal text-gray-500">QPS</span>
              </p>
              {report.potential_savings_usd && (
                <p className="text-xs text-gray-500 mt-2">
                  ~${report.potential_savings_usd.toFixed(2)}/month
                </p>
              )}
            </div>
            <TrendingDown className="h-8 w-8 text-blue-500" />
          </div>
        </div>

        {/* Size Gaps */}
        <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Size Gaps</p>
              <p className="text-3xl font-bold text-gray-900 mt-1">{report.size_gaps.length}</p>
              <p className="text-xs text-gray-500 mt-2">
                Sizes with no creatives
              </p>
            </div>
            <div className="h-8 w-8 rounded-full bg-orange-100 flex items-center justify-center">
              <span className="text-lg font-bold text-orange-600">!</span>
            </div>
          </div>
        </div>

        {/* Analysis Period */}
        <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Analysis Period</p>
              <p className="text-3xl font-bold text-gray-900 mt-1">
                {report.analysis_period_days} <span className="text-lg font-normal text-gray-500">days</span>
              </p>
              <p className="text-xs text-gray-500 mt-2">
                <Clock className="inline h-3 w-3 mr-1" />
                {formatDate(report.generated_at)}
              </p>
            </div>
            <Calendar className="h-8 w-8 text-gray-400" />
          </div>
        </div>
      </div>

      {/* Recommendations Summary */}
      {(summary.block > 0 || summary.add_creative > 0 || summary.use_flexible > 0 || summary.monitor > 0) && (
        <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-900 mb-4">Recommendations Summary</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {summary.block > 0 && (
              <div className="flex items-center gap-3 p-3 bg-red-50 rounded-lg">
                <Ban className="h-5 w-5 text-red-600" />
                <div>
                  <p className="text-2xl font-bold text-red-700">{summary.block}</p>
                  <p className="text-xs text-red-600">Block</p>
                </div>
              </div>
            )}
            {summary.add_creative > 0 && (
              <div className="flex items-center gap-3 p-3 bg-blue-50 rounded-lg">
                <Plus className="h-5 w-5 text-blue-600" />
                <div>
                  <p className="text-2xl font-bold text-blue-700">{summary.add_creative}</p>
                  <p className="text-xs text-blue-600">Add Creative</p>
                </div>
              </div>
            )}
            {summary.use_flexible > 0 && (
              <div className="flex items-center gap-3 p-3 bg-purple-50 rounded-lg">
                <Maximize className="h-5 w-5 text-purple-600" />
                <div>
                  <p className="text-2xl font-bold text-purple-700">{summary.use_flexible}</p>
                  <p className="text-xs text-purple-600">Use Flexible</p>
                </div>
              </div>
            )}
            {summary.monitor > 0 && (
              <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                <Eye className="h-5 w-5 text-gray-600" />
                <div>
                  <p className="text-2xl font-bold text-gray-700">{summary.monitor}</p>
                  <p className="text-xs text-gray-600">Monitor</p>
                </div>
              </div>
            )}
          </div>

          {summary.top_savings_size && (
            <div className="mt-4 pt-4 border-t border-gray-100">
              <p className="text-sm text-gray-600">
                <span className="font-medium">Top savings opportunity:</span>{" "}
                <span className="text-gray-900">{summary.top_savings_size}</span>{" "}
                <span className="text-blue-600">({summary.top_savings_qps.toFixed(1)} QPS)</span>
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
