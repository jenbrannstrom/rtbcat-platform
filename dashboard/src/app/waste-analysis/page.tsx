"use client";

import { useState, useCallback, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, Database, AlertTriangle } from "lucide-react";
import { getWasteReport, generateMockTraffic } from "@/lib/api";
import { SeatSelector } from "@/components/seat-selector";
import { WasteReportCard, WasteReportSkeleton, WasteReportEmpty } from "@/components/waste-report";
import { SizeCoverageChart, SizeCoverageChartSkeleton } from "@/components/size-coverage-chart";
import { cn } from "@/lib/utils";

const PERIOD_OPTIONS = [
  { value: 7, label: "7 days" },
  { value: 14, label: "14 days" },
  { value: 30, label: "30 days" },
];

function WasteAnalysisContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();

  // Get initial values from URL params
  const initialSeatId = searchParams.get("seat") || null;
  const initialDays = parseInt(searchParams.get("days") || "7", 10);

  const [selectedSeatId, setSelectedSeatId] = useState<string | null>(initialSeatId);
  const [days, setDays] = useState<number>(initialDays);
  const [mockTrafficMessage, setMockTrafficMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Update URL when seat or days changes
  const updateUrl = useCallback(
    (seatId: string | null, newDays: number) => {
      const params = new URLSearchParams();
      if (seatId) params.set("seat", seatId);
      params.set("days", String(newDays));
      router.replace(`/waste-analysis?${params.toString()}`, { scroll: false });
    },
    [router]
  );

  const handleSeatChange = useCallback(
    (seatId: string | null) => {
      setSelectedSeatId(seatId);
      updateUrl(seatId, days);
    },
    [days, updateUrl]
  );

  const handleDaysChange = useCallback(
    (newDays: number) => {
      setDays(newDays);
      updateUrl(selectedSeatId, newDays);
    },
    [selectedSeatId, updateUrl]
  );

  // Fetch waste report
  const {
    data: wasteReport,
    isLoading: reportLoading,
    error: reportError,
    refetch: refetchReport,
  } = useQuery({
    queryKey: ["waste-report", selectedSeatId, days],
    queryFn: () =>
      getWasteReport({
        buyer_id: selectedSeatId || undefined,
        days,
      }),
  });

  // Generate mock traffic mutation
  const mockTrafficMutation = useMutation({
    mutationFn: () =>
      generateMockTraffic({
        days: 7,
        buyer_id: selectedSeatId || undefined,
        base_daily_requests: 100000,
        waste_bias: 0.4,
      }),
    onSuccess: (data) => {
      setMockTrafficMessage({ type: "success", text: data.message });
      queryClient.invalidateQueries({ queryKey: ["waste-report"] });
      setTimeout(() => setMockTrafficMessage(null), 5000);
    },
    onError: (error) => {
      setMockTrafficMessage({
        type: "error",
        text: error instanceof Error ? error.message : "Failed to generate traffic",
      });
      setTimeout(() => setMockTrafficMessage(null), 5000);
    },
  });

  const handleGenerateMockTraffic = () => {
    mockTrafficMutation.mutate();
  };

  const handleRefresh = () => {
    refetchReport();
  };

  return (
    <div className="p-8">
      {/* Page Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Waste Analysis</h1>
            <p className="mt-1 text-sm text-gray-500">
              Identify RTB bandwidth waste by comparing bid requests against your creative inventory
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={handleRefresh}
              disabled={reportLoading}
              className={cn(
                "flex items-center gap-2 px-4 py-2",
                "bg-white border border-gray-300 rounded-lg shadow-sm",
                "hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500",
                "disabled:opacity-50 disabled:cursor-not-allowed",
                "text-sm font-medium text-gray-700"
              )}
            >
              <RefreshCw className={cn("h-4 w-4", reportLoading && "animate-spin")} />
              Refresh
            </button>
          </div>
        </div>
      </div>

      {/* Controls Bar */}
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4 p-4 bg-white rounded-lg border border-gray-200 shadow-sm">
        <div className="flex items-center gap-6">
          {/* Seat Selector */}
          <SeatSelector selectedSeatId={selectedSeatId} onSeatChange={handleSeatChange} />
        </div>

        <div className="flex items-center gap-4">
          {/* Period Selector */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-600">Period:</span>
            <div className="flex rounded-lg border border-gray-300 overflow-hidden">
              {PERIOD_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  onClick={() => handleDaysChange(option.value)}
                  className={cn(
                    "px-3 py-1.5 text-sm font-medium transition-colors",
                    days === option.value
                      ? "bg-primary-600 text-white"
                      : "bg-white text-gray-700 hover:bg-gray-50"
                  )}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          {/* Generate Mock Traffic */}
          <button
            onClick={handleGenerateMockTraffic}
            disabled={mockTrafficMutation.isPending}
            className={cn(
              "flex items-center gap-2 px-4 py-2",
              "bg-amber-600 text-white rounded-lg shadow-sm",
              "hover:bg-amber-700 focus:outline-none focus:ring-2 focus:ring-amber-500",
              "disabled:opacity-50 disabled:cursor-not-allowed",
              "text-sm font-medium"
            )}
            title="Generate synthetic traffic data for testing"
          >
            <Database className={cn("h-4 w-4", mockTrafficMutation.isPending && "animate-pulse")} />
            {mockTrafficMutation.isPending ? "Generating..." : "Generate Test Data"}
          </button>
        </div>
      </div>

      {/* Mock Traffic Message */}
      {mockTrafficMessage && (
        <div
          className={cn(
            "mb-6 flex items-center gap-2 px-4 py-3 rounded-lg text-sm",
            mockTrafficMessage.type === "success"
              ? "bg-green-50 text-green-700 border border-green-200"
              : "bg-red-50 text-red-700 border border-red-200"
          )}
          role="alert"
        >
          {mockTrafficMessage.type === "success" ? (
            <Database className="h-4 w-4" />
          ) : (
            <AlertTriangle className="h-4 w-4" />
          )}
          <span>{mockTrafficMessage.text}</span>
        </div>
      )}

      {/* Error State */}
      {reportError && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-red-500" />
            <p className="text-sm text-red-700">
              {reportError instanceof Error ? reportError.message : "Failed to load waste report"}
            </p>
          </div>
          <button
            onClick={handleRefresh}
            className="mt-2 text-sm text-red-600 hover:text-red-800 underline"
          >
            Try again
          </button>
        </div>
      )}

      {/* Waste Report */}
      <section className="mb-8">
        {reportLoading ? (
          <WasteReportSkeleton />
        ) : wasteReport ? (
          <WasteReportCard report={wasteReport} />
        ) : (
          <WasteReportEmpty />
        )}
      </section>

      {/* Size Gaps Table */}
      <section>
        <div className="mb-4">
          <h2 className="text-lg font-semibold text-gray-900">Size Gaps</h2>
          <p className="text-sm text-gray-500">
            Sizes receiving bid requests but with no matching creatives in your inventory
          </p>
        </div>

        {reportLoading ? (
          <SizeCoverageChartSkeleton />
        ) : wasteReport?.size_gaps ? (
          <SizeCoverageChart sizeGaps={wasteReport.size_gaps} />
        ) : null}
      </section>
    </div>
  );
}

function WasteAnalysisLoading() {
  return (
    <div className="p-8">
      <div className="mb-8">
        <div className="h-8 w-48 bg-gray-200 rounded animate-pulse" />
        <div className="mt-2 h-4 w-96 bg-gray-100 rounded animate-pulse" />
      </div>
      <div className="mb-6 h-24 bg-gray-100 rounded-lg animate-pulse" />
      <WasteReportSkeleton />
    </div>
  );
}

export default function WasteAnalysisPage() {
  return (
    <Suspense fallback={<WasteAnalysisLoading />}>
      <WasteAnalysisContent />
    </Suspense>
  );
}
