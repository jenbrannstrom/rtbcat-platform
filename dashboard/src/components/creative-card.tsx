"use client";

import { useState } from "react";
import { ExternalLink, Play, Eye, Image, FileCode, DollarSign, TrendingUp, MousePointer, Copy, Check } from "lucide-react";
import type { Creative, CreativePerformanceSummary } from "@/types/api";
import { cn, getFormatColor, getStatusColor, truncate } from "@/lib/utils";
import { getGoogleAuthBuyersUrl, extractBuyerIdFromName } from "@/lib/url-utils";

interface CreativeCardProps {
  creative: Creative;
  onPreview?: (creative: Creative) => void;
  performance?: CreativePerformanceSummary;
}

// Format micros to USD string
function formatUSD(micros: number): string {
  const dollars = micros / 1_000_000;
  if (dollars >= 1000) {
    return `$${(dollars / 1000).toFixed(1)}K`;
  } else if (dollars >= 1) {
    return `$${dollars.toFixed(2)}`;
  } else {
    return `$${dollars.toFixed(4)}`;
  }
}

// Format CPM/CPC in micros to USD
function formatCostMetric(micros: number | null): string {
  if (micros === null) return "-";
  const dollars = micros / 1_000_000;
  return `$${dollars.toFixed(2)}`;
}

// Get CPC color based on thresholds: green <$0.30, yellow $0.30-$0.60, red >$0.60
function getCpcColor(cpcMicros: number | null): string {
  if (cpcMicros === null) return "text-gray-500";
  const dollars = cpcMicros / 1_000_000;
  if (dollars < 0.30) return "text-green-600";
  if (dollars <= 0.60) return "text-yellow-600";
  return "text-red-600";
}

function extractVideoUrlFromVast(vastXml: string): string | null {
  const match = vastXml.match(/<MediaFile[^>]*>(?:<!\[CDATA\[)?(https?:\/\/[^\]<]+)/);
  return match ? match[1].trim() : null;
}

function PreviewThumbnail({ creative }: { creative: Creative }) {
  // For VIDEO: show thumbnail if available, otherwise gradient placeholder
  if (creative.format === "VIDEO") {
    const thumbnailUrl = creative.video?.thumbnail_url;

    return (
      <div className="relative h-32 bg-gradient-to-br from-gray-800 to-gray-900 flex items-center justify-center overflow-hidden">
        {thumbnailUrl ? (
          <>
            <img
              src={thumbnailUrl}
              alt="Video thumbnail"
              className="w-full h-full object-cover"
              onError={(e) => {
                // Hide broken image, show placeholder
                (e.target as HTMLImageElement).style.display = "none";
              }}
            />
            <div className="absolute inset-0 bg-black/30 flex items-center justify-center">
              <div className="w-12 h-12 rounded-full bg-black/50 flex items-center justify-center">
                <Play className="h-6 w-6 text-white ml-0.5" fill="currentColor" />
              </div>
            </div>
          </>
        ) : (
          <div className="flex flex-col items-center">
            <div className="w-12 h-12 rounded-full bg-white/20 flex items-center justify-center">
              <Play className="h-6 w-6 text-white ml-0.5" fill="currentColor" />
            </div>
            <p className="text-xs text-gray-400 mt-2">Video</p>
          </div>
        )}
        {creative.video?.duration && (
          <span className="absolute bottom-1 right-1 bg-black/70 text-white text-xs px-1.5 py-0.5 rounded">
            {creative.video.duration}
          </span>
        )}
        {creative.width && creative.height && (
          <span className="absolute top-1 left-1 bg-black/50 text-white text-xs px-1.5 py-0.5 rounded">
            {creative.width}x{creative.height}
          </span>
        )}
      </div>
    );
  }

  // For NATIVE: prefer logo/icon, fall back to main image
  if (creative.format === "NATIVE") {
    const imageUrl = creative.native?.logo?.url || creative.native?.image?.url;
    if (imageUrl) {
      return (
        <div className="relative h-32 bg-gradient-to-br from-green-50 to-green-100">
          <img
            src={imageUrl}
            alt={creative.native?.headline || "Native ad"}
            className="w-full h-full object-cover"
            onError={(e) => {
              (e.target as HTMLImageElement).parentElement!.innerHTML = `
                <div class="flex items-center justify-center h-full text-gray-400">
                  <svg class="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                </div>
              `;
            }}
          />
          {creative.native?.headline && (
            <span className="absolute bottom-1 left-1 right-1 bg-black/60 text-white text-xs px-1.5 py-0.5 rounded truncate">
              {creative.native.headline}
            </span>
          )}
        </div>
      );
    }
  }

  // For HTML: show placeholder with dimensions
  if (creative.format === "HTML") {
    const w = creative.html?.width || creative.width || 300;
    const h = creative.html?.height || creative.height || 250;
    return (
      <div className="relative h-32 bg-gradient-to-br from-blue-50 to-blue-100 flex items-center justify-center">
        <div className="flex flex-col items-center">
          <div className="w-12 h-12 rounded-full bg-blue-200 flex items-center justify-center">
            <FileCode className="h-6 w-6 text-blue-600" />
          </div>
          <p className="text-xs text-blue-600 mt-2">HTML</p>
        </div>
        <span className="absolute top-1 left-1 bg-blue-600/80 text-white text-xs px-1.5 py-0.5 rounded">
          {w}x{h}
        </span>
      </div>
    );
  }

  // Default placeholder
  return (
    <div className="h-32 bg-gray-100 flex items-center justify-center text-gray-400">
      <Image className="h-8 w-8" />
    </div>
  );
}

export function CreativeCard({ creative, onPreview, performance }: CreativeCardProps) {
  const [copied, setCopied] = useState(false);
  const hasPreview = creative.video || creative.html || creative.native;

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    await navigator.clipboard.writeText(creative.id);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="card overflow-hidden hover:shadow-md transition-shadow">
      {/* Thumbnail */}
      <div
        className={cn("cursor-pointer", hasPreview && "hover:opacity-90")}
        onClick={() => hasPreview && onPreview?.(creative)}
      >
        <PreviewThumbnail creative={creative} />
      </div>

      <div className="p-4">
        <div className="flex items-start justify-between">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1">
              <button
                onClick={() => onPreview?.(creative)}
                className="text-sm font-medium text-gray-900 hover:text-primary-600 truncate text-left font-mono"
                title={creative.id}
              >
                {creative.id}
              </button>
              <button
                onClick={handleCopy}
                className="p-0.5 text-gray-400 hover:text-gray-600 rounded flex-shrink-0"
                title="Copy ID"
              >
                {copied ? <Check className="h-3.5 w-3.5 text-green-500" /> : <Copy className="h-3.5 w-3.5" />}
              </button>
            </div>
            {creative.name && (
              <p className="mt-1 text-xs text-gray-500 truncate" title={creative.name}>
                {creative.name}
              </p>
            )}
          </div>
          <div className="flex gap-1 ml-2">
            {hasPreview && (
              <button
                onClick={() => onPreview?.(creative)}
                className="p-1 text-gray-400 hover:text-primary-600 rounded"
                title="Preview"
              >
                <Eye className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>

        <div className="mt-3 flex flex-wrap gap-2">
          <span className={cn("badge", getFormatColor(creative.format))}>
            {creative.format}
          </span>
          {creative.approval_status && (
            <span className={cn("badge", getStatusColor(creative.approval_status))}>
              {creative.approval_status.replace("_", " ")}
            </span>
          )}
          {creative.width && creative.height && (
            <span className="badge bg-gray-100 text-gray-700">
              {creative.width}x{creative.height}
            </span>
          )}
        </div>

        {/* Performance Metrics */}
        {performance?.has_data && (
          <div className="mt-3 pt-3 border-t border-gray-100">
            <div className="grid grid-cols-2 gap-2 text-xs">
              {/* Spend - bold when >$1,000 */}
              <div className="flex items-center gap-1 text-green-600">
                <DollarSign className="h-3 w-3" />
                <span className={cn(
                  "font-medium",
                  performance.total_spend_micros > 1_000_000_000 && "font-bold"
                )}>
                  {formatUSD(performance.total_spend_micros)}
                </span>
              </div>
              {/* CTR */}
              {performance.ctr_percent !== null && (
                <div className="flex items-center gap-1 text-blue-600">
                  <MousePointer className="h-3 w-3" />
                  <span className="font-medium">{performance.ctr_percent.toFixed(2)}% CTR</span>
                </div>
              )}
              {/* CPM */}
              {performance.avg_cpm_micros !== null && (
                <div className="text-gray-500">
                  CPM: {formatCostMetric(performance.avg_cpm_micros)}
                </div>
              )}
              {/* CPC - color coded */}
              {performance.avg_cpc_micros !== null && (
                <div className={getCpcColor(performance.avg_cpc_micros)}>
                  CPC: {formatCostMetric(performance.avg_cpc_micros)}
                </div>
              )}
            </div>
            {/* Impressions & Clicks Summary */}
            <div className="mt-1 text-xs text-gray-400">
              {performance.total_impressions.toLocaleString()} imps · {performance.total_clicks.toLocaleString()} clicks
            </div>
          </div>
        )}

        {(creative.seat_name || creative.advertiser_name) && (
          <p className="mt-3 text-sm text-gray-600">
            {creative.seat_name || creative.advertiser_name}
          </p>
        )}

        {/* Google Auth Buyers Link */}
        {(() => {
          const buyerId = creative.buyer_id || extractBuyerIdFromName(creative.name);
          if (!buyerId) return null;
          return (
            <a
              href={getGoogleAuthBuyersUrl(buyerId, creative.id)}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-3 inline-flex items-center text-xs text-primary-600 hover:text-primary-700"
              title="View in Google Authorized Buyers"
            >
              <span>Google Auth. Buyers</span>
              <ExternalLink className="ml-1 h-3 w-3 flex-shrink-0" />
            </a>
          );
        })()}

        {(creative.utm_campaign || creative.utm_source) && (
          <div className="mt-3 pt-3 border-t border-gray-100">
            <p className="text-xs text-gray-500">
              {creative.utm_campaign && (
                <span className="mr-2">
                  Campaign: <span className="font-medium">{creative.utm_campaign}</span>
                </span>
              )}
              {creative.utm_source && (
                <span>
                  Source: <span className="font-medium">{creative.utm_source}</span>
                </span>
              )}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
