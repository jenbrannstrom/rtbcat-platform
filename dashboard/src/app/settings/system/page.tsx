"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Server, Database, Video, Loader2, CheckCircle, XCircle, AlertTriangle, Image, Cpu, HardDrive } from "lucide-react";
import { getHealth, getStats, getThumbnailStatus, generateThumbnailsBatch, getSystemStatus } from "@/lib/api";
import { LoadingPage } from "@/components/loading";
import { ErrorPage } from "@/components/error";
import { cn } from "@/lib/utils";
import { useTranslation } from "@/contexts/i18n-context";

export default function SystemStatusPage() {
  const queryClient = useQueryClient();
  const { t } = useTranslation();
  const [batchLimit, setBatchLimit] = useState(50);
  const [forceRetry, setForceRetry] = useState(false);

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

  const generateMutation = useMutation({
    mutationFn: () => generateThumbnailsBatch({ limit: batchLimit, force: forceRetry }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["thumbnailStatus"] });
    },
  });

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
                    {systemStatus.database_size_mb} MB
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
