"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { Settings, CheckCircle, XCircle, Database, Server, Users, Clock, ChevronRight, Video, Loader2, AlertTriangle, Image } from "lucide-react";
import { getHealth, getStats, getThumbnailStatus, generateThumbnailsBatch, getSystemStatus } from "@/lib/api";
import { HardDrive, Cpu } from "lucide-react";
import { LoadingPage } from "@/components/loading";
import { ErrorPage } from "@/components/error";
import { cn } from "@/lib/utils";

export default function SettingsPage() {
  const queryClient = useQueryClient();
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
            : "Failed to check API status"
        }
        onRetry={() => refetchHealth()}
      />
    );
  }

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="mt-1 text-sm text-gray-500">
          System configuration and status
        </p>
      </div>

      <div className="max-w-2xl space-y-6">
        <div className="card p-6">
          <div className="flex items-center mb-4">
            <Server className="h-5 w-5 text-gray-400 mr-2" />
            <h2 className="text-lg font-medium text-gray-900">API Status</h2>
          </div>

          <div className="space-y-4">
            <div className="flex items-center justify-between py-2 border-b border-gray-100">
              <span className="text-sm text-gray-600">Status</span>
              <span className="flex items-center text-sm font-medium text-green-600">
                <CheckCircle className="h-4 w-4 mr-1" />
                {health?.status}
              </span>
            </div>

            <div className="flex items-center justify-between py-2 border-b border-gray-100">
              <span className="text-sm text-gray-600">Version</span>
              <span className="text-sm font-medium text-gray-900">
                {health?.version}
              </span>
            </div>

            <div className="flex items-center justify-between py-2">
              <span className="text-sm text-gray-600">Configured</span>
              <span
                className={`flex items-center text-sm font-medium ${
                  health?.configured ? "text-green-600" : "text-red-600"
                }`}
              >
                {health?.configured ? (
                  <>
                    <CheckCircle className="h-4 w-4 mr-1" />
                    Yes
                  </>
                ) : (
                  <>
                    <XCircle className="h-4 w-4 mr-1" />
                    No
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
            <h2 className="text-lg font-medium text-gray-900">System Status</h2>
          </div>

          {systemStatusLoading ? (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
            </div>
          ) : systemStatus ? (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="flex items-center justify-between py-2">
                  <span className="text-sm text-gray-600">Python</span>
                  <span className="text-sm font-medium text-gray-900">
                    {systemStatus.python_version}
                  </span>
                </div>

                <div className="flex items-center justify-between py-2">
                  <span className="text-sm text-gray-600">Node.js</span>
                  <span className={cn(
                    "text-sm font-medium",
                    systemStatus.node_available ? "text-green-600" : "text-yellow-600"
                  )}>
                    {systemStatus.node_version || (systemStatus.node_available ? "Installed" : "Not found")}
                  </span>
                </div>

                <div className="flex items-center justify-between py-2">
                  <span className="text-sm text-gray-600">ffmpeg</span>
                  <span className={cn(
                    "text-sm font-medium",
                    systemStatus.ffmpeg_available ? "text-green-600" : "text-yellow-600"
                  )}>
                    {systemStatus.ffmpeg_version || (systemStatus.ffmpeg_available ? "Installed" : "Not installed")}
                  </span>
                </div>

                <div className="flex items-center justify-between py-2">
                  <span className="text-sm text-gray-600">Disk Space</span>
                  <span className="text-sm font-medium text-gray-900">
                    {systemStatus.disk_space_gb} GB free
                  </span>
                </div>
              </div>

              <div className="pt-3 border-t border-gray-100">
                <div className="flex items-center justify-between py-1">
                  <span className="text-sm text-gray-600">Database Size</span>
                  <span className="text-sm font-medium text-gray-900">
                    {systemStatus.database_size_mb} MB
                  </span>
                </div>
                <div className="flex items-center justify-between py-1">
                  <span className="text-sm text-gray-600">Thumbnails Generated</span>
                  <span className="text-sm font-medium text-gray-900">
                    {systemStatus.thumbnails_count} / {systemStatus.videos_count} videos
                  </span>
                </div>
              </div>

              {!systemStatus.ffmpeg_available && (
                <div className="p-3 bg-yellow-50 rounded-lg text-sm text-yellow-800">
                  <strong>ffmpeg not installed.</strong> Video thumbnails require ffmpeg:
                  <code className="block mt-1 bg-yellow-100 p-2 rounded font-mono text-xs">
                    sudo apt install ffmpeg
                  </code>
                </div>
              )}
            </div>
          ) : (
            <div className="text-sm text-gray-500">System status unavailable</div>
          )}
        </div>

        <div className="card p-6">
          <div className="flex items-center mb-4">
            <Database className="h-5 w-5 text-gray-400 mr-2" />
            <h2 className="text-lg font-medium text-gray-900">Database</h2>
          </div>

          <div className="space-y-4">
            <div className="flex items-center justify-between py-2 border-b border-gray-100">
              <span className="text-sm text-gray-600">Path</span>
              <span className="text-sm font-mono text-gray-900">
                {stats?.db_path || "N/A"}
              </span>
            </div>

            <div className="flex items-center justify-between py-2 border-b border-gray-100">
              <span className="text-sm text-gray-600">Creatives</span>
              <span className="text-sm font-medium text-gray-900">
                {stats?.creative_count ?? 0}
              </span>
            </div>

            <div className="flex items-center justify-between py-2 border-b border-gray-100">
              <span className="text-sm text-gray-600">Campaigns</span>
              <span className="text-sm font-medium text-gray-900">
                {stats?.campaign_count ?? 0}
              </span>
            </div>

            <div className="flex items-center justify-between py-2">
              <span className="text-sm text-gray-600">Clusters</span>
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
            <h2 className="text-lg font-medium text-gray-900">Video Thumbnails</h2>
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
                  <div className="text-xs text-gray-500">Total Videos</div>
                </div>
                <div className="text-center p-3 bg-green-50 rounded-lg">
                  <div className="text-2xl font-bold text-green-600">
                    {thumbnailStatus.with_thumbnails}
                  </div>
                  <div className="text-xs text-gray-500">With Thumbnails</div>
                </div>
                <div className="text-center p-3 bg-yellow-50 rounded-lg">
                  <div className="text-2xl font-bold text-yellow-600">
                    {thumbnailStatus.pending}
                  </div>
                  <div className="text-xs text-gray-500">Pending</div>
                </div>
                <div className="text-center p-3 bg-red-50 rounded-lg">
                  <div className="text-2xl font-bold text-red-600">
                    {thumbnailStatus.failed}
                  </div>
                  <div className="text-xs text-gray-500">Failed</div>
                </div>
              </div>

              {/* Coverage Bar */}
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gray-600">Coverage</span>
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
                <span className="text-sm text-gray-600">ffmpeg Available</span>
                {thumbnailStatus.ffmpeg_available ? (
                  <span className="flex items-center text-sm font-medium text-green-600">
                    <CheckCircle className="h-4 w-4 mr-1" />
                    Installed
                  </span>
                ) : (
                  <span className="flex items-center text-sm font-medium text-red-600">
                    <AlertTriangle className="h-4 w-4 mr-1" />
                    Not Found
                  </span>
                )}
              </div>

              {/* Generation Controls */}
              {thumbnailStatus.ffmpeg_available && thumbnailStatus.pending > 0 && (
                <div className="pt-4 border-t border-gray-100">
                  <div className="flex items-center gap-4 mb-3">
                    <label className="text-sm text-gray-600">
                      Batch size:
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
                      Retry failed
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
                        Generating...
                      </>
                    ) : (
                      <>
                        <Image className="h-4 w-4 mr-2" />
                        Generate Thumbnails
                      </>
                    )}
                  </button>

                  {/* Results */}
                  {generateMutation.data && (
                    <div className="mt-3 p-3 bg-gray-50 rounded-lg text-sm">
                      <div className="font-medium text-gray-900 mb-1">
                        Processed {generateMutation.data.total_processed} videos
                      </div>
                      <div className="text-gray-600">
                        {generateMutation.data.success_count} succeeded,{" "}
                        {generateMutation.data.failed_count} failed
                      </div>
                    </div>
                  )}
                </div>
              )}

              {!thumbnailStatus.ffmpeg_available && (
                <div className="p-3 bg-yellow-50 rounded-lg text-sm text-yellow-800">
                  <strong>ffmpeg not found.</strong> Install ffmpeg to generate video thumbnails:
                  <code className="block mt-1 bg-yellow-100 p-2 rounded font-mono text-xs">
                    sudo apt install ffmpeg
                  </code>
                </div>
              )}

              {thumbnailStatus.pending === 0 && thumbnailStatus.with_thumbnails > 0 && (
                <div className="p-3 bg-green-50 rounded-lg text-sm text-green-800">
                  All video thumbnails have been generated.
                </div>
              )}
            </div>
          ) : (
            <div className="text-sm text-gray-500">No thumbnail data available</div>
          )}
        </div>

        <div className="card p-6">
          <div className="flex items-center mb-4">
            <Settings className="h-5 w-5 text-gray-400 mr-2" />
            <h2 className="text-lg font-medium text-gray-900">Configuration</h2>
          </div>

          <div className="space-y-2">
            <Link
              href="/connect"
              className="flex items-center justify-between p-3 rounded-lg hover:bg-gray-50 border border-gray-200"
            >
              <div className="flex items-center">
                <Settings className="h-5 w-5 text-primary-600 mr-3" />
                <div>
                  <div className="font-medium text-gray-900">Google Credentials</div>
                  <div className="text-sm text-gray-500">
                    {health?.configured
                      ? "Manage your Authorized Buyers connection"
                      : "Connect your Authorized Buyers account"}
                  </div>
                </div>
              </div>
              <div className="flex items-center">
                {health?.configured ? (
                  <span className="mr-2 text-xs font-medium text-green-600 bg-green-50 px-2 py-1 rounded">
                    Connected
                  </span>
                ) : (
                  <span className="mr-2 text-xs font-medium text-yellow-600 bg-yellow-50 px-2 py-1 rounded">
                    Not Connected
                  </span>
                )}
                <ChevronRight className="h-5 w-5 text-gray-400" />
              </div>
            </Link>
          </div>
        </div>

        <div className="card p-6">
          <div className="flex items-center mb-4">
            <Users className="h-5 w-5 text-gray-400 mr-2" />
            <h2 className="text-lg font-medium text-gray-900">Manage</h2>
          </div>

          <div className="space-y-2">
            <Link
              href="/settings/seats"
              className="flex items-center justify-between p-3 rounded-lg hover:bg-gray-50 border border-gray-200"
            >
              <div className="flex items-center">
                <Users className="h-5 w-5 text-primary-600 mr-3" />
                <div>
                  <div className="font-medium text-gray-900">Buyer Seats</div>
                  <div className="text-sm text-gray-500">
                    Manage seat display names and view creative counts
                  </div>
                </div>
              </div>
              <ChevronRight className="h-5 w-5 text-gray-400" />
            </Link>

            <Link
              href="/settings/retention"
              className="flex items-center justify-between p-3 rounded-lg hover:bg-gray-50 border border-gray-200"
            >
              <div className="flex items-center">
                <Clock className="h-5 w-5 text-primary-600 mr-3" />
                <div>
                  <div className="font-medium text-gray-900">Data Retention</div>
                  <div className="text-sm text-gray-500">
                    Configure retention periods and cleanup schedules
                  </div>
                </div>
              </div>
              <ChevronRight className="h-5 w-5 text-gray-400" />
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
