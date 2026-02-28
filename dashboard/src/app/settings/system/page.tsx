"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Server, Database, Video, Loader2, CheckCircle, XCircle, AlertTriangle, Image, Cpu, BarChart3 } from "lucide-react";
import {
  getHealth,
  getStats,
  getThumbnailStatus,
  generateThumbnailsBatch,
  getSystemStatus,
  getSystemDataHealth,
  getOptimizerModels,
  listOptimizerSegmentScores,
  listOptimizerProposals,
} from "@/lib/api";
import { LoadingPage } from "@/components/loading";
import { ErrorPage } from "@/components/error";
import { cn } from "@/lib/utils";
import { useTranslation } from "@/contexts/i18n-context";
import { useAccount } from "@/contexts/account-context";

export default function SystemStatusPage() {
  const queryClient = useQueryClient();
  const { t } = useTranslation();
  const { selectedBuyerId } = useAccount();
  const [batchLimit, setBatchLimit] = useState(50);
  const [forceRetry, setForceRetry] = useState(false);
  const [healthDays, setHealthDays] = useState(7);
  const [healthLimit, setHealthLimit] = useState(20);
  const [healthStateFilter, setHealthStateFilter] = useState<"all" | "healthy" | "degraded" | "unavailable">("all");
  const [minCompleteness, setMinCompleteness] = useState<string>("");
  const parsedMinCompleteness = Number(minCompleteness);
  const normalizedMinCompleteness =
    minCompleteness.trim() === "" || !Number.isFinite(parsedMinCompleteness)
      ? undefined
      : Math.min(100, Math.max(0, parsedMinCompleteness));

  const {
    data: health,
    isLoading: healthLoading,
    error: healthError,
    refetch: refetchHealth,
  } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
  });

  const { data: stats } = useQuery({
    queryKey: ["stats"],
    queryFn: getStats,
  });

  const { data: thumbnailStatus, isLoading: thumbnailStatusLoading } = useQuery({
    queryKey: ["thumbnailStatus"],
    queryFn: () => getThumbnailStatus(),
  });

  const { data: systemStatus, isLoading: systemStatusLoading } = useQuery({
    queryKey: ["systemStatus"],
    queryFn: getSystemStatus,
  });

  const { data: dataHealth, isLoading: dataHealthLoading } = useQuery({
    queryKey: [
      "systemDataHealth",
      selectedBuyerId,
      healthDays,
      healthLimit,
      healthStateFilter,
      minCompleteness,
    ],
    queryFn: () =>
      getSystemDataHealth({
        days: healthDays,
        buyer_id: selectedBuyerId || undefined,
        limit: healthLimit,
        availability_state: healthStateFilter === "all" ? undefined : healthStateFilter,
        min_completeness_pct: normalizedMinCompleteness,
      }),
  });

  const {
    data: optimizerModels,
    isLoading: optimizerModelsLoading,
    error: optimizerModelsError,
  } = useQuery({
    queryKey: ["optimizerModels", selectedBuyerId],
    queryFn: () =>
      getOptimizerModels({
        buyer_id: selectedBuyerId || undefined,
        include_inactive: true,
        limit: 200,
        offset: 0,
      }),
  });

  const {
    data: optimizerScores,
    isLoading: optimizerScoresLoading,
    error: optimizerScoresError,
  } = useQuery({
    queryKey: ["optimizerScores", selectedBuyerId],
    queryFn: () =>
      listOptimizerSegmentScores({
        buyer_id: selectedBuyerId || undefined,
        days: 14,
        limit: 20,
        offset: 0,
      }),
  });

  const {
    data: optimizerProposals,
    isLoading: optimizerProposalsLoading,
    error: optimizerProposalsError,
  } = useQuery({
    queryKey: ["optimizerProposals", selectedBuyerId],
    queryFn: () =>
      listOptimizerProposals({
        buyer_id: selectedBuyerId || undefined,
        limit: 100,
        offset: 0,
      }),
  });

  const generateMutation = useMutation({
    mutationFn: () => generateThumbnailsBatch({ limit: batchLimit, force: forceRetry }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["thumbnailStatus"] });
    },
  });

  const activeModelCount = optimizerModels?.rows.filter((row) => row.is_active).length ?? 0;
  const proposalRows = optimizerProposals?.rows ?? [];
  const proposalStatusCounts = proposalRows.reduce(
    (acc, row) => {
      const key = row.status || "draft";
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>,
  );
  const optimizerPanelLoading =
    optimizerModelsLoading || optimizerScoresLoading || optimizerProposalsLoading;
  const optimizerPanelError =
    optimizerModelsError || optimizerScoresError || optimizerProposalsError;

  if (healthLoading) {
    return <LoadingPage />;
  }

  if (healthError) {
    return (
      <ErrorPage
        message={
          healthError instanceof Error
            ? healthError.message
            : t.settings.failedToCheckApiStatus
        }
        onRetry={() => refetchHealth()}
      />
    );
  }

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">{t.settingsNav.systemStatus}</h1>
        <p className="mt-1 text-sm text-gray-500">
          {t.settings.systemConfiguration}
        </p>
      </div>

      <div className="max-w-2xl space-y-6">
        {/* API Status */}
        <div className="card p-6">
          <div className="flex items-center mb-4">
            <Server className="h-5 w-5 text-gray-400 mr-2" />
            <h2 className="text-lg font-medium text-gray-900">{t.settings.apiStatus}</h2>
          </div>

          <div className="space-y-4">
            <div className="flex items-center justify-between py-2 border-b border-gray-100">
              <span className="text-sm text-gray-600">{t.settings.status}</span>
              <span className="flex items-center text-sm font-medium text-green-600">
                <CheckCircle className="h-4 w-4 mr-1" />
                {health?.status}
              </span>
            </div>

            <div className="flex items-center justify-between py-2 border-b border-gray-100">
              <span className="text-sm text-gray-600">{t.settings.version}</span>
              <span className="text-sm font-medium text-gray-900">
                {health?.version}
              </span>
            </div>

            <div className="flex items-center justify-between py-2">
              <span className="text-sm text-gray-600">{t.settings.configured}</span>
              <span
                className={`flex items-center text-sm font-medium ${
                  health?.configured ? "text-green-600" : "text-red-600"
                }`}
              >
                {health?.configured ? (
                  <>
                    <CheckCircle className="h-4 w-4 mr-1" />
                    {t.settings.yes}
                  </>
                ) : (
                  <>
                    <XCircle className="h-4 w-4 mr-1" />
                    {t.settings.no}
                  </>
                )}
              </span>
            </div>
          </div>
        </div>

        {/* System Status Panel */}
        <div className="card p-6">
          <div className="flex items-center mb-4">
            <Cpu className="h-5 w-5 text-gray-400 mr-2" />
            <h2 className="text-lg font-medium text-gray-900">{t.settings.systemStatus}</h2>
          </div>

          {systemStatusLoading ? (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
            </div>
          ) : systemStatus ? (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="flex items-center justify-between py-2">
                  <span className="text-sm text-gray-600">{t.settings.python}</span>
                  <span className="text-sm font-medium text-gray-900">
                    {systemStatus.python_version}
                  </span>
                </div>

                <div className="flex items-center justify-between py-2">
                  <span className="text-sm text-gray-600">{t.settings.nodejs}</span>
                  <span className={cn(
                    "text-sm font-medium",
                    systemStatus.node_available ? "text-green-600" : "text-yellow-600"
                  )}>
                    {systemStatus.node_version || (systemStatus.node_available ? t.settings.installed : t.settings.notFound)}
                  </span>
                </div>

                <div className="flex items-center justify-between py-2">
                  <span className="text-sm text-gray-600">{t.settings.ffmpeg}</span>
                  <span className={cn(
                    "text-sm font-medium",
                    systemStatus.ffmpeg_available ? "text-green-600" : "text-yellow-600"
                  )}>
                    {systemStatus.ffmpeg_version || (systemStatus.ffmpeg_available ? t.settings.installed : t.settings.notInstalled)}
                  </span>
                </div>

                <div className="flex items-center justify-between py-2">
                  <span className="text-sm text-gray-600">{t.settings.diskSpace}</span>
                  <span className="text-sm font-medium text-gray-900">
                    {systemStatus.disk_space_gb} {t.settings.gbFree}
                  </span>
                </div>
              </div>

              <div className="pt-3 border-t border-gray-100">
                <div className="flex items-center justify-between py-1">
                  <span className="text-sm text-gray-600">{t.settings.databaseSize}</span>
                  <span className="text-sm font-medium text-gray-900">
                    {systemStatus.database_size_mb} {t.settings.mb}
                  </span>
                </div>
                <div className="flex items-center justify-between py-1">
                  <span className="text-sm text-gray-600">{t.settings.thumbnailsGenerated}</span>
                  <span className="text-sm font-medium text-gray-900">
                    {systemStatus.thumbnails_count} / {systemStatus.videos_count} {t.settings.videos}
                  </span>
                </div>
              </div>

              {!systemStatus.ffmpeg_available && (
                <div className="p-3 bg-yellow-50 rounded-lg text-sm text-yellow-800">
                  <strong>{t.settings.ffmpegNotInstalled}</strong>
                  <code className="block mt-1 bg-yellow-100 p-2 rounded font-mono text-xs">
                    sudo apt install ffmpeg
                  </code>
                </div>
              )}
            </div>
          ) : (
            <div className="text-sm text-gray-500">{t.settings.systemStatusUnavailable}</div>
          )}
        </div>

        {/* Optimizer Control Plane Panel */}
        <div className="card p-6">
          <div className="flex items-center mb-4">
            <BarChart3 className="h-5 w-5 text-gray-400 mr-2" />
            <h2 className="text-lg font-medium text-gray-900">Optimizer Control Plane</h2>
          </div>

          {optimizerPanelLoading ? (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
            </div>
          ) : optimizerPanelError ? (
            <div className="text-sm text-red-600">
              {optimizerPanelError instanceof Error
                ? optimizerPanelError.message
                : "Failed to load optimizer control plane data."}
            </div>
          ) : (
            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-3">
                <div className="rounded-lg border border-gray-200 p-3">
                  <div className="text-xs text-gray-500">Models</div>
                  <div className="mt-1 text-lg font-semibold text-gray-900">
                    {activeModelCount}/{optimizerModels?.meta.total ?? 0}
                  </div>
                  <div className="text-xs text-gray-500">active/total</div>
                </div>
                <div className="rounded-lg border border-gray-200 p-3">
                  <div className="text-xs text-gray-500">Scores (14d)</div>
                  <div className="mt-1 text-lg font-semibold text-gray-900">
                    {optimizerScores?.meta.total ?? 0}
                  </div>
                  <div className="text-xs text-gray-500">
                    latest: {optimizerScores?.rows[0]?.score_date || "-"}
                  </div>
                </div>
                <div className="rounded-lg border border-gray-200 p-3">
                  <div className="text-xs text-gray-500">Proposals</div>
                  <div className="mt-1 text-lg font-semibold text-gray-900">
                    {optimizerProposals?.meta.total ?? 0}
                  </div>
                  <div className="text-xs text-gray-500">
                    draft {proposalStatusCounts.draft || 0}, approved {proposalStatusCounts.approved || 0}, applied{" "}
                    {proposalStatusCounts.applied || 0}
                  </div>
                </div>
              </div>

              <div className="rounded-lg border border-gray-200 overflow-hidden">
                <div className="px-3 py-2 text-xs font-semibold text-gray-600 bg-gray-50">
                  Recent Segment Scores
                </div>
                {optimizerScores?.rows.length ? (
                  <div className="max-h-52 overflow-auto">
                    <table className="min-w-full text-xs">
                      <thead className="bg-gray-50 text-gray-600">
                        <tr>
                          <th className="text-left px-3 py-2">Date</th>
                          <th className="text-left px-3 py-2">Billing</th>
                          <th className="text-left px-3 py-2">Score</th>
                          <th className="text-left px-3 py-2">Confidence</th>
                        </tr>
                      </thead>
                      <tbody>
                        {optimizerScores.rows.slice(0, 8).map((row) => (
                          <tr key={row.score_id} className="border-t border-gray-100">
                            <td className="px-3 py-2 text-gray-700">{row.score_date || "-"}</td>
                            <td className="px-3 py-2 font-mono text-gray-700">{row.billing_id || "-"}</td>
                            <td className="px-3 py-2 text-gray-700">{row.value_score.toFixed(3)}</td>
                            <td className="px-3 py-2 text-gray-700">{row.confidence.toFixed(3)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="px-3 py-4 text-xs text-gray-500">No segment scores found.</div>
                )}
              </div>

              <div className="rounded-lg border border-gray-200 overflow-hidden">
                <div className="px-3 py-2 text-xs font-semibold text-gray-600 bg-gray-50">
                  Recent QPS Proposals
                </div>
                {optimizerProposals?.rows.length ? (
                  <div className="max-h-52 overflow-auto">
                    <table className="min-w-full text-xs">
                      <thead className="bg-gray-50 text-gray-600">
                        <tr>
                          <th className="text-left px-3 py-2">Updated</th>
                          <th className="text-left px-3 py-2">Billing</th>
                          <th className="text-left px-3 py-2">Delta QPS</th>
                          <th className="text-left px-3 py-2">Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {optimizerProposals.rows.slice(0, 8).map((row) => (
                          <tr key={row.proposal_id} className="border-t border-gray-100">
                            <td className="px-3 py-2 text-gray-700">{row.updated_at || row.created_at || "-"}</td>
                            <td className="px-3 py-2 font-mono text-gray-700">{row.billing_id || "-"}</td>
                            <td
                              className={cn(
                                "px-3 py-2 font-medium",
                                row.delta_qps >= 0 ? "text-green-700" : "text-red-700",
                              )}
                            >
                              {row.delta_qps >= 0 ? "+" : ""}
                              {row.delta_qps.toFixed(2)}
                            </td>
                            <td className="px-3 py-2">
                              <span
                                className={cn(
                                  "inline-flex rounded px-2 py-0.5 text-xs font-medium",
                                  row.status === "draft" && "bg-slate-100 text-slate-700",
                                  row.status === "approved" && "bg-blue-50 text-blue-700",
                                  row.status === "applied" && "bg-green-50 text-green-700",
                                  row.status === "rejected" && "bg-red-50 text-red-700",
                                )}
                              >
                                {row.status}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="px-3 py-4 text-xs text-gray-500">No proposals found.</div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Database Panel */}
        <div className="card p-6">
          <div className="flex items-center mb-4">
            <BarChart3 className="h-5 w-5 text-gray-400 mr-2" />
            <h2 className="text-lg font-medium text-gray-900">Optimizer Readiness</h2>
          </div>

          {dataHealthLoading ? (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
            </div>
          ) : dataHealth ? (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <label className="text-xs text-gray-600">
                  Window
                  <select
                    value={healthDays}
                    onChange={(e) => setHealthDays(Number(e.target.value))}
                    className="mt-1 block w-full input py-1 text-sm"
                  >
                    <option value={7}>7 days</option>
                    <option value={14}>14 days</option>
                    <option value={30}>30 days</option>
                  </select>
                </label>
                <label className="text-xs text-gray-600">
                  State Filter
                  <select
                    value={healthStateFilter}
                    onChange={(e) =>
                      setHealthStateFilter(
                        e.target.value as "all" | "healthy" | "degraded" | "unavailable"
                      )
                    }
                    className="mt-1 block w-full input py-1 text-sm"
                  >
                    <option value="all">all</option>
                    <option value="healthy">healthy</option>
                    <option value="degraded">degraded</option>
                    <option value="unavailable">unavailable</option>
                  </select>
                </label>
                <label className="text-xs text-gray-600">
                  Min Completeness %
                  <input
                    type="number"
                    min={0}
                    max={100}
                    placeholder="none"
                    value={minCompleteness}
                    onChange={(e) => setMinCompleteness(e.target.value)}
                    className="mt-1 block w-full input py-1 text-sm"
                  />
                </label>
                <label className="text-xs text-gray-600">
                  Row Limit
                  <select
                    value={healthLimit}
                    onChange={(e) => setHealthLimit(Number(e.target.value))}
                    className="mt-1 block w-full input py-1 text-sm"
                  >
                    <option value={20}>20</option>
                    <option value={50}>50</option>
                    <option value={100}>100</option>
                  </select>
                </label>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="rounded-lg border border-gray-200 p-3">
                  <div className="text-xs text-gray-500">Report Type Coverage</div>
                  <div className="mt-1 text-lg font-semibold text-gray-900">
                    {dataHealth.optimizer_readiness.report_completeness.available_report_types}/
                    {dataHealth.optimizer_readiness.report_completeness.expected_report_types}
                  </div>
                  <div className="text-xs text-gray-500">
                    {dataHealth.optimizer_readiness.report_completeness.coverage_pct}% available
                  </div>
                </div>
                <div className="rounded-lg border border-gray-200 p-3">
                  <div className="text-xs text-gray-500">Quality Freshness</div>
                  <div className="mt-1 text-lg font-semibold text-gray-900">
                    {dataHealth.optimizer_readiness.rtb_quality_freshness.age_days ?? "-"} day(s)
                  </div>
                  <div className="text-xs text-gray-500">
                    state: {dataHealth.optimizer_readiness.rtb_quality_freshness.availability_state}
                  </div>
                </div>
                <div className="rounded-lg border border-gray-200 p-3">
                  <div className="text-xs text-gray-500">Bidstream Dimension Coverage</div>
                  <div className="mt-1 text-sm font-semibold text-gray-900">
                    platform {100 - dataHealth.optimizer_readiness.bidstream_dimension_coverage.platform_missing_pct}%
                  </div>
                  <div className="text-xs text-gray-500">
                    env {100 - dataHealth.optimizer_readiness.bidstream_dimension_coverage.environment_missing_pct}%,
                    deal {100 - dataHealth.optimizer_readiness.bidstream_dimension_coverage.transaction_type_missing_pct}%
                  </div>
                </div>
                <div className="rounded-lg border border-gray-200 p-3">
                  <div className="text-xs text-gray-500">Seat-Day Completeness</div>
                  <div className="mt-1 text-lg font-semibold text-gray-900">
                    {dataHealth.optimizer_readiness.seat_day_completeness.summary.avg_completeness_pct}%
                  </div>
                  <div className="text-xs text-gray-500">
                    {dataHealth.optimizer_readiness.seat_day_completeness.summary.total_seat_days} seat-day rows
                  </div>
                </div>
              </div>

              <div className="text-xs text-gray-500">
                Seat-day rollup refreshed at:{" "}
                {dataHealth.optimizer_readiness.seat_day_completeness.refreshed_at || "unknown"}
              </div>

              <div className="rounded-lg border border-gray-200 overflow-hidden">
                <div className="px-3 py-2 text-xs font-semibold text-gray-600 bg-gray-50">
                  Latest Seat-Day Completeness Rows
                </div>
                <div className="max-h-56 overflow-auto">
                  <table className="min-w-full text-xs">
                    <thead className="bg-gray-50 text-gray-600">
                      <tr>
                        <th className="text-left px-3 py-2">Date</th>
                        <th className="text-left px-3 py-2">Seat</th>
                        <th className="text-left px-3 py-2">Reports</th>
                        <th className="text-left px-3 py-2">Completeness</th>
                        <th className="text-left px-3 py-2">State</th>
                      </tr>
                    </thead>
                    <tbody>
                      {dataHealth.optimizer_readiness.seat_day_completeness.rows.slice(0, 10).map((row) => (
                        <tr key={`${row.metric_date}-${row.buyer_account_id}`} className="border-t border-gray-100">
                          <td className="px-3 py-2 text-gray-700">{row.metric_date || "-"}</td>
                          <td className="px-3 py-2 font-mono text-gray-700">{row.buyer_account_id}</td>
                          <td className="px-3 py-2 text-gray-700">
                            {row.available_report_types}/{row.expected_report_types}
                          </td>
                          <td className="px-3 py-2 text-gray-700">{row.completeness_pct}%</td>
                          <td className="px-3 py-2">
                            <span
                              className={cn(
                                "inline-flex rounded px-2 py-0.5 text-xs font-medium",
                                row.availability_state === "healthy" && "bg-green-50 text-green-700",
                                row.availability_state === "degraded" && "bg-yellow-50 text-yellow-700",
                                row.availability_state === "unavailable" && "bg-red-50 text-red-700"
                              )}
                            >
                              {row.availability_state}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          ) : (
            <div className="text-sm text-gray-500">Data health details unavailable.</div>
          )}
        </div>

        {/* Database Panel */}
        <div className="card p-6">
          <div className="flex items-center mb-4">
            <Database className="h-5 w-5 text-gray-400 mr-2" />
            <h2 className="text-lg font-medium text-gray-900">{t.settings.database}</h2>
          </div>

          <div className="space-y-4">
            <div className="flex items-center justify-between py-2 border-b border-gray-100">
              <span className="text-sm text-gray-600">{t.settings.path}</span>
              <span className="text-sm font-mono text-gray-900">
                {stats?.db_path || t.settings.notAvailable}
              </span>
            </div>

            <div className="flex items-center justify-between py-2 border-b border-gray-100">
              <span className="text-sm text-gray-600">{t.settings.creatives}</span>
              <span className="text-sm font-medium text-gray-900">
                {stats?.creative_count ?? 0}
              </span>
            </div>

            <div className="flex items-center justify-between py-2 border-b border-gray-100">
              <span className="text-sm text-gray-600">{t.settings.campaigns}</span>
              <span className="text-sm font-medium text-gray-900">
                {stats?.campaign_count ?? 0}
              </span>
            </div>

            <div className="flex items-center justify-between py-2">
              <span className="text-sm text-gray-600">{t.settings.clusters}</span>
              <span className="text-sm font-medium text-gray-900">
                {stats?.cluster_count ?? 0}
              </span>
            </div>
          </div>
        </div>

        {/* Thumbnail Generation Panel */}
        <div className="card p-6">
          <div className="flex items-center mb-4">
            <Video className="h-5 w-5 text-gray-400 mr-2" />
            <h2 className="text-lg font-medium text-gray-900">{t.settings.videoThumbnails}</h2>
          </div>

          {thumbnailStatusLoading ? (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
            </div>
          ) : thumbnailStatus ? (
            <div className="space-y-4">
              {/* Status Summary */}
              <div className="grid grid-cols-4 gap-4">
                <div className="text-center p-3 bg-gray-50 rounded-lg">
                  <div className="text-2xl font-bold text-gray-900">
                    {thumbnailStatus.total_videos}
                  </div>
                  <div className="text-xs text-gray-500">{t.settings.totalVideos}</div>
                </div>
                <div className="text-center p-3 bg-green-50 rounded-lg">
                  <div className="text-2xl font-bold text-green-600">
                    {thumbnailStatus.with_thumbnails}
                  </div>
                  <div className="text-xs text-gray-500">{t.settings.withThumbnails}</div>
                </div>
                <div className="text-center p-3 bg-yellow-50 rounded-lg">
                  <div className="text-2xl font-bold text-yellow-600">
                    {thumbnailStatus.pending}
                  </div>
                  <div className="text-xs text-gray-500">{t.settings.pending}</div>
                </div>
                <div className="text-center p-3 bg-red-50 rounded-lg">
                  <div className="text-2xl font-bold text-red-600">
                    {thumbnailStatus.failed}
                  </div>
                  <div className="text-xs text-gray-500">{t.settings.failed}</div>
                </div>
              </div>

              {/* Coverage Bar */}
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gray-600">{t.settings.coverage}</span>
                  <span className="font-medium">{thumbnailStatus.coverage_percent}%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-green-500 h-2 rounded-full transition-all"
                    style={{ width: `${thumbnailStatus.coverage_percent}%` }}
                  />
                </div>
              </div>

              {/* ffmpeg Status */}
              <div className="flex items-center justify-between py-2 border-t border-gray-100">
                <span className="text-sm text-gray-600">{t.settings.ffmpegAvailable}</span>
                {thumbnailStatus.ffmpeg_available ? (
                  <span className="flex items-center text-sm font-medium text-green-600">
                    <CheckCircle className="h-4 w-4 mr-1" />
                    {t.settings.installed}
                  </span>
                ) : (
                  <span className="flex items-center text-sm font-medium text-red-600">
                    <AlertTriangle className="h-4 w-4 mr-1" />
                    {t.settings.notFound}
                  </span>
                )}
              </div>

              {/* Generation Controls */}
              {thumbnailStatus.ffmpeg_available && thumbnailStatus.pending > 0 && (
                <div className="pt-4 border-t border-gray-100">
                  <div className="flex items-center gap-4 mb-3">
                    <label className="text-sm text-gray-600">
                      {t.settings.batchSize}
                      <select
                        value={batchLimit}
                        onChange={(e) => setBatchLimit(Number(e.target.value))}
                        className="ml-2 input py-1 text-sm"
                        disabled={generateMutation.isPending}
                      >
                        <option value={10}>10</option>
                        <option value={25}>25</option>
                        <option value={50}>50</option>
                        <option value={100}>100</option>
                      </select>
                    </label>
                    <label className="flex items-center text-sm text-gray-600">
                      <input
                        type="checkbox"
                        checked={forceRetry}
                        onChange={(e) => setForceRetry(e.target.checked)}
                        className="mr-2"
                        disabled={generateMutation.isPending}
                      />
                      {t.settings.retryFailed}
                    </label>
                  </div>
                  <button
                    onClick={() => generateMutation.mutate()}
                    disabled={generateMutation.isPending}
                    className={cn(
                      "btn-primary w-full",
                      generateMutation.isPending && "opacity-50 cursor-not-allowed"
                    )}
                  >
                    {generateMutation.isPending ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        {t.settings.generating}
                      </>
                    ) : (
                      <>
                        <Image className="h-4 w-4 mr-2" />
                        {t.settings.generateThumbnails}
                      </>
                    )}
                  </button>

                  {/* Results */}
                  {generateMutation.data && (
                    <div className="mt-3 p-3 bg-gray-50 rounded-lg text-sm">
                      <div className="font-medium text-gray-900 mb-1">
                        {t.settings.processedVideos.replace('{count}', String(generateMutation.data.total_processed))}
                      </div>
                      <div className="text-gray-600">
                        {t.settings.succeededFailed
                          .replace('{success}', String(generateMutation.data.success_count))
                          .replace('{failed}', String(generateMutation.data.failed_count))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {!thumbnailStatus.ffmpeg_available && (
                <div className="p-3 bg-yellow-50 rounded-lg text-sm text-yellow-800">
                  <strong>{t.settings.ffmpegNotFoundInstall}</strong>
                  <code className="block mt-1 bg-yellow-100 p-2 rounded font-mono text-xs">
                    sudo apt install ffmpeg
                  </code>
                </div>
              )}

              {thumbnailStatus.pending === 0 && thumbnailStatus.with_thumbnails > 0 && (
                <div className="p-3 bg-green-50 rounded-lg text-sm text-green-800">
                  {t.settings.allThumbnailsGenerated}
                </div>
              )}
            </div>
          ) : (
            <div className="text-sm text-gray-500">{t.settings.noThumbnailData}</div>
          )}
        </div>
      </div>
    </div>
  );
}
