"use client";

import { useState, useMemo } from "react";
import { ChevronDown, ChevronUp, ArrowUpDown, Ban, Plus, Maximize, Eye, AlertCircle } from "lucide-react";
import type { SizeGap } from "@/types/api";
import { cn } from "@/lib/utils";

interface SizeCoverageChartProps {
  sizeGaps: SizeGap[];
  isLoading?: boolean;
}

type SortField = "request_count" | "estimated_qps" | "estimated_waste_pct" | "recommendation";
type SortDirection = "asc" | "desc";

function formatNumber(num: number): string {
  if (num >= 1000000) {
    return `${(num / 1000000).toFixed(1)}M`;
  }
  if (num >= 1000) {
    return `${(num / 1000).toFixed(1)}K`;
  }
  return num.toLocaleString();
}

function getRecommendationIcon(recommendation: string) {
  const rec = recommendation.toLowerCase();
  if (rec.includes("block")) return Ban;
  if (rec.includes("add")) return Plus;
  if (rec.includes("flexible")) return Maximize;
  return Eye;
}

function getRecommendationColor(recommendation: string) {
  const rec = recommendation.toLowerCase();
  if (rec.includes("block")) return "bg-red-100 text-red-800";
  if (rec.includes("add")) return "bg-blue-100 text-blue-800";
  if (rec.includes("flexible")) return "bg-purple-100 text-purple-800";
  return "bg-gray-100 text-gray-800";
}

function getSeverityColor(requestCount: number): string {
  if (requestCount >= 10000) return "bg-red-500";
  if (requestCount >= 1000) return "bg-yellow-500";
  return "bg-gray-400";
}

function getRecommendationPriority(recommendation: string): number {
  const rec = recommendation.toLowerCase();
  if (rec.includes("block")) return 1;
  if (rec.includes("add")) return 2;
  if (rec.includes("flexible")) return 3;
  return 4;
}

export function SizeCoverageChartSkeleton() {
  return (
    <div className="animate-pulse">
      <div className="h-10 bg-gray-100 rounded-t-lg" />
      {[1, 2, 3, 4, 5].map((i) => (
        <div key={i} className="h-16 bg-gray-50 border-b border-gray-100" />
      ))}
    </div>
  );
}

export function SizeCoverageChartEmpty() {
  return (
    <div className="text-center py-8">
      <div className="mx-auto h-12 w-12 rounded-full bg-green-100 flex items-center justify-center">
        <span className="text-2xl">&#10003;</span>
      </div>
      <h3 className="mt-4 text-lg font-medium text-gray-900">No Size Gaps</h3>
      <p className="mt-2 text-sm text-gray-500">
        All requested sizes have creative coverage. No wasted traffic detected.
      </p>
    </div>
  );
}

export function SizeCoverageChart({ sizeGaps, isLoading }: SizeCoverageChartProps) {
  const [sortField, setSortField] = useState<SortField>("request_count");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  const sortedGaps = useMemo(() => {
    return [...sizeGaps].sort((a, b) => {
      let aVal: number | string;
      let bVal: number | string;

      switch (sortField) {
        case "request_count":
          aVal = a.request_count;
          bVal = b.request_count;
          break;
        case "estimated_qps":
          aVal = a.estimated_qps;
          bVal = b.estimated_qps;
          break;
        case "estimated_waste_pct":
          aVal = a.estimated_waste_pct;
          bVal = b.estimated_waste_pct;
          break;
        case "recommendation":
          aVal = getRecommendationPriority(a.recommendation);
          bVal = getRecommendationPriority(b.recommendation);
          break;
        default:
          return 0;
      }

      if (typeof aVal === "number" && typeof bVal === "number") {
        return sortDirection === "desc" ? bVal - aVal : aVal - bVal;
      }
      return 0;
    });
  }, [sizeGaps, sortField, sortDirection]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection((d) => (d === "desc" ? "asc" : "desc"));
    } else {
      setSortField(field);
      setSortDirection("desc");
    }
  };

  if (isLoading) {
    return <SizeCoverageChartSkeleton />;
  }

  if (sizeGaps.length === 0) {
    return <SizeCoverageChartEmpty />;
  }

  const SortHeader = ({
    field,
    children,
    className,
  }: {
    field: SortField;
    children: React.ReactNode;
    className?: string;
  }) => (
    <button
      onClick={() => handleSort(field)}
      className={cn(
        "flex items-center gap-1 text-xs font-semibold text-gray-600 uppercase tracking-wider hover:text-gray-900",
        className
      )}
    >
      {children}
      {sortField === field ? (
        sortDirection === "desc" ? (
          <ChevronDown className="h-3 w-3" />
        ) : (
          <ChevronUp className="h-3 w-3" />
        )
      ) : (
        <ArrowUpDown className="h-3 w-3 text-gray-400" />
      )}
    </button>
  );

  return (
    <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
      {/* Table Header */}
      <div className="grid grid-cols-12 gap-4 px-4 py-3 bg-gray-50 border-b border-gray-200">
        <div className="col-span-3">
          <span className="text-xs font-semibold text-gray-600 uppercase tracking-wider">Size</span>
        </div>
        <div className="col-span-2 text-right">
          <SortHeader field="request_count">Requests</SortHeader>
        </div>
        <div className="col-span-2 text-right">
          <SortHeader field="estimated_qps">QPS</SortHeader>
        </div>
        <div className="col-span-2 text-right">
          <SortHeader field="estimated_waste_pct">Waste %</SortHeader>
        </div>
        <div className="col-span-3">
          <SortHeader field="recommendation">Recommendation</SortHeader>
        </div>
      </div>

      {/* Table Body */}
      <div className="divide-y divide-gray-100">
        {sortedGaps.map((gap) => {
          const Icon = getRecommendationIcon(gap.recommendation);
          const isExpanded = expandedRow === gap.canonical_size;

          return (
            <div key={gap.canonical_size}>
              {/* Main Row */}
              <button
                onClick={() => setExpandedRow(isExpanded ? null : gap.canonical_size)}
                className="w-full grid grid-cols-12 gap-4 px-4 py-3 hover:bg-gray-50 transition-colors text-left"
              >
                {/* Size with severity indicator */}
                <div className="col-span-3 flex items-center gap-3">
                  <div
                    className={cn("w-2 h-8 rounded-full", getSeverityColor(gap.request_count))}
                    title={gap.request_count >= 10000 ? "High volume" : gap.request_count >= 1000 ? "Medium volume" : "Low volume"}
                  />
                  <div>
                    <p className="font-medium text-gray-900 text-sm truncate" title={gap.canonical_size}>
                      {gap.canonical_size.replace(/\s*\([^)]*\)/, "")}
                    </p>
                    {gap.closest_iab_size && (
                      <p className="text-xs text-gray-500">
                        Near: {gap.closest_iab_size.replace(/\s*\([^)]*\)/, "")}
                      </p>
                    )}
                  </div>
                </div>

                {/* Requests */}
                <div className="col-span-2 text-right flex items-center justify-end">
                  <span className="font-medium text-gray-900">{formatNumber(gap.request_count)}</span>
                </div>

                {/* QPS */}
                <div className="col-span-2 text-right flex items-center justify-end">
                  <span className="text-gray-700">{gap.estimated_qps.toFixed(2)}</span>
                </div>

                {/* Waste % */}
                <div className="col-span-2 text-right flex items-center justify-end">
                  <span className="text-gray-700">{gap.estimated_waste_pct.toFixed(1)}%</span>
                </div>

                {/* Recommendation */}
                <div className="col-span-3 flex items-center gap-2">
                  <span
                    className={cn(
                      "inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium",
                      getRecommendationColor(gap.recommendation)
                    )}
                  >
                    <Icon className="h-3 w-3" />
                    {gap.recommendation}
                  </span>
                  <ChevronDown
                    className={cn(
                      "h-4 w-4 text-gray-400 transition-transform ml-auto",
                      isExpanded && "rotate-180"
                    )}
                  />
                </div>
              </button>

              {/* Expanded Detail */}
              {isExpanded && (
                <div className="px-4 py-4 bg-gray-50 border-t border-gray-100">
                  <div className="flex items-start gap-3 ml-5">
                    <AlertCircle className="h-5 w-5 text-gray-400 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="text-sm text-gray-700">{gap.recommendation_detail}</p>
                      {gap.potential_savings_usd && (
                        <p className="mt-2 text-sm text-gray-500">
                          Potential savings: <span className="font-medium text-green-600">${gap.potential_savings_usd.toFixed(2)}/month</span>
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Summary Footer */}
      <div className="px-4 py-3 bg-gray-50 border-t border-gray-200">
        <div className="flex items-center justify-between text-sm text-gray-600">
          <span>{sizeGaps.length} size gap{sizeGaps.length !== 1 ? "s" : ""} detected</span>
          <span>
            Total waste: {formatNumber(sizeGaps.reduce((sum, g) => sum + g.request_count, 0))} requests
          </span>
        </div>
      </div>
    </div>
  );
}
