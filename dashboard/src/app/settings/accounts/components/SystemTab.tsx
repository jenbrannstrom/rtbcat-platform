"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle,
  Database,
  Server,
  Video,
  Loader2,
  ImageIcon,
  Cpu,
} from "lucide-react";
import {
  getHealth,
  getStats,
  getThumbnailStatus,
  generateThumbnailsBatch,
  getSystemStatus,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import { useTranslation } from "@/contexts/i18n-context";

/**
 * System status and configuration tab.
 * Shows API status, database stats, and thumbnail generation controls.
 */
export function SystemTab() {
  const queryClient = useQueryClient();
  const { t } = useTranslation();
  const [batchLimit, setBatchLimit] = useState(50);
  const [forceRetry, setForceRetry] = useState(false);

  const { data: health } = useQuery({ queryKey: ["health"], queryFn: getHealth });
  const { data: stats } = useQuery({ queryKey: ["stats"], queryFn: getStats });
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
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["thumbnailStatus"] }),
  });

  return (
    <div className="space-y-6">
      {/* API Status */}
      <div className="card p-6">
        <div className="flex items-center mb-4">
          <Server className="h-5 w-5 text-gray-400 mr-2" />
          <h3 className="text-lg font-medium text-gray-900">{t.settings.apiStatus}</h3>
        </div>
        <div className="grid grid-cols-3 gap-4">
          <div className="p-3 bg-gray-50 rounded-lg">
            <p className="text-sm text-gray-500">{t.settings.status}</p>
            <p className="font-medium text-green-600 flex items-center gap-1">
              <CheckCircle className="h-4 w-4" /> {health?.status}
            </p>
          </div>
          <div className="p-3 bg-gray-50 rounded-lg">
            <p className="text-sm text-gray-500">{t.settings.version}</p>
            <p className="font-medium text-gray-900">{health?.version}</p>
          </div>
          <div className="p-3 bg-gray-50 rounded-lg">
            <p className="text-sm text-gray-500">{t.settings.configured}</p>
            <p className={cn("font-medium", health?.configured ? "text-green-600" : "text-red-600")}>
              {health?.configured ? t.settings.yes : t.settings.no}
            </p>
          </div>
        </div>
      </div>

      {/* System Status */}
      <div className="card p-6">
        <div className="flex items-center mb-4">
          <Cpu className="h-5 w-5 text-gray-400 mr-2" />
          <h3 className="text-lg font-medium text-gray-900">{t.settings.systemStatus}</h3>
        </div>
        {systemStatusLoading ? (
          <div className="flex items-center justify-center py-4">
            <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
          </div>
        ) : systemStatus ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-3 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-500">{t.settings.python}</p>
              <p className="font-medium text-gray-900">{systemStatus.python_version}</p>
            </div>
            <div className="p-3 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-500">{t.settings.ffmpeg}</p>
              <p className={cn("font-medium", systemStatus.ffmpeg_available ? "text-green-600" : "text-yellow-600")}>
                {systemStatus.ffmpeg_available ? t.settings.installed : t.settings.notInstalled}
              </p>
            </div>
            <div className="p-3 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-500">{t.settings.diskSpace}</p>
              <p className="font-medium text-gray-900">{systemStatus.disk_space_gb} {t.settings.gbFree}</p>
            </div>
            <div className="p-3 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-500">{t.settings.database}</p>
              <p className="font-medium text-gray-900">{systemStatus.database_size_mb} {t.settings.mb}</p>
            </div>
          </div>
        ) : null}
      </div>

      {/* Database */}
      <div className="card p-6">
        <div className="flex items-center mb-4">
          <Database className="h-5 w-5 text-gray-400 mr-2" />
          <h3 className="text-lg font-medium text-gray-900">{t.settings.database}</h3>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-3 bg-gray-50 rounded-lg">
            <p className="text-sm text-gray-500">{t.settings.creatives}</p>
            <p className="font-bold text-xl text-gray-900">{stats?.creative_count ?? 0}</p>
          </div>
          <div className="p-3 bg-gray-50 rounded-lg">
            <p className="text-sm text-gray-500">{t.settings.campaigns}</p>
            <p className="font-bold text-xl text-gray-900">{stats?.campaign_count ?? 0}</p>
          </div>
          <div className="p-3 bg-gray-50 rounded-lg">
            <p className="text-sm text-gray-500">{t.settings.clusters}</p>
            <p className="font-bold text-xl text-gray-900">{stats?.cluster_count ?? 0}</p>
          </div>
          <div className="p-3 bg-gray-50 rounded-lg">
            <p className="text-sm text-gray-500">{t.settings.path}</p>
            <p className="text-xs font-mono text-gray-600 truncate" title={stats?.db_path}>{stats?.db_path || t.settings.notAvailable}</p>
          </div>
        </div>
      </div>

      {/* Video Thumbnails */}
      <div className="card p-6">
        <div className="flex items-center mb-4">
          <Video className="h-5 w-5 text-gray-400 mr-2" />
          <h3 className="text-lg font-medium text-gray-900">{t.settings.videoThumbnails}</h3>
        </div>
        {thumbnailStatusLoading ? (
          <div className="flex items-center justify-center py-4">
            <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
          </div>
        ) : thumbnailStatus ? (
          <div className="space-y-4">
            <div className="grid grid-cols-4 gap-4">
              <div className="text-center p-3 bg-gray-50 rounded-lg">
                <div className="text-xl font-bold text-gray-900">{thumbnailStatus.total_videos}</div>
                <div className="text-xs text-gray-500">{t.settings.totalVideos}</div>
              </div>
              <div className="text-center p-3 bg-green-50 rounded-lg">
                <div className="text-xl font-bold text-green-600">{thumbnailStatus.with_thumbnails}</div>
                <div className="text-xs text-gray-500">{t.settings.withThumbnails}</div>
              </div>
              <div className="text-center p-3 bg-yellow-50 rounded-lg">
                <div className="text-xl font-bold text-yellow-600">{thumbnailStatus.pending}</div>
                <div className="text-xs text-gray-500">{t.settings.pending}</div>
              </div>
              <div className="text-center p-3 bg-red-50 rounded-lg">
                <div className="text-xl font-bold text-red-600">{thumbnailStatus.failed}</div>
                <div className="text-xs text-gray-500">{t.settings.failed}</div>
              </div>
            </div>

            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-600">{t.settings.coverage}</span>
                <span className="font-medium">{thumbnailStatus.coverage_percent}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div className="bg-green-500 h-2 rounded-full transition-all" style={{ width: `${thumbnailStatus.coverage_percent}%` }} />
              </div>
            </div>

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
                  className={cn("btn-primary w-full", generateMutation.isPending && "opacity-50")}
                >
                  {generateMutation.isPending ? (
                    <><Loader2 className="h-4 w-4 mr-2 animate-spin" />{t.settings.generating}</>
                  ) : (
                    <><ImageIcon className="h-4 w-4 mr-2" />{t.settings.generateThumbnails}</>
                  )}
                </button>
              </div>
            )}

            {!thumbnailStatus.ffmpeg_available && (
              <div className="p-3 bg-yellow-50 rounded-lg text-sm text-yellow-800">
                <strong>{t.setup.ffmpegNotFound}</strong> {t.setup.installToGenerate}
                <code className="block mt-1 bg-yellow-100 p-2 rounded font-mono text-xs">sudo apt install ffmpeg</code>
              </div>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}
