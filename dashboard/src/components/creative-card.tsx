"use client";

import { ExternalLink, Play, Eye, Image, FileCode } from "lucide-react";
import type { Creative } from "@/types/api";
import { cn, getFormatColor, getStatusColor, truncate } from "@/lib/utils";

interface CreativeCardProps {
  creative: Creative;
  onPreview?: (creative: Creative) => void;
}

function extractVideoUrlFromVast(vastXml: string): string | null {
  const match = vastXml.match(/<MediaFile[^>]*>(?:<!\[CDATA\[)?(https?:\/\/[^\]<]+)/);
  return match ? match[1].trim() : null;
}

function PreviewThumbnail({ creative }: { creative: Creative }) {
  // For VIDEO: try to show video or placeholder
  if (creative.format === "VIDEO") {
    let videoUrl = creative.video?.video_url;
    if (!videoUrl && creative.video?.vast_xml) {
      videoUrl = extractVideoUrlFromVast(creative.video.vast_xml);
    }

    return (
      <div className="relative h-32 bg-gray-900 flex items-center justify-center">
        {videoUrl ? (
          <>
            <video
              src={videoUrl}
              className="w-full h-full object-cover"
              muted
              preload="none"
            />
            <div className="absolute inset-0 bg-black/30 flex items-center justify-center">
              <Play className="h-10 w-10 text-white" />
            </div>
          </>
        ) : (
          <div className="text-center text-gray-500">
            <Play className="h-8 w-8 mx-auto" />
            <p className="text-xs mt-1">Video</p>
          </div>
        )}
        {creative.video?.duration && (
          <span className="absolute bottom-1 right-1 bg-black/70 text-white text-xs px-1 rounded">
            {creative.video.duration}
          </span>
        )}
      </div>
    );
  }

  // For NATIVE: show image if available
  if (creative.format === "NATIVE" && creative.native?.image?.url) {
    return (
      <div className="relative h-32 bg-gray-100">
        <img
          src={creative.native.image.url}
          alt={creative.native.headline || "Native ad"}
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
      </div>
    );
  }

  // For HTML: show placeholder with dimensions
  if (creative.format === "HTML") {
    const w = creative.html?.width || creative.width || 300;
    const h = creative.html?.height || creative.height || 250;
    return (
      <div className="h-32 bg-gray-100 flex items-center justify-center">
        <div className="text-center text-gray-500">
          <FileCode className="h-8 w-8 mx-auto" />
          <p className="text-xs mt-1">{w}x{h}</p>
        </div>
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

export function CreativeCard({ creative, onPreview }: CreativeCardProps) {
  const hasPreview = creative.video || creative.html || creative.native;

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
            <button
              onClick={() => onPreview?.(creative)}
              className="text-sm font-medium text-gray-900 hover:text-primary-600 truncate block text-left w-full"
            >
              {creative.name || creative.id}
            </button>
            <p className="mt-1 text-xs text-gray-500 truncate">
              {creative.id}
            </p>
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

        {creative.advertiser_name && (
          <p className="mt-3 text-sm text-gray-600">
            {creative.advertiser_name}
          </p>
        )}

        {creative.final_url && (
          <a
            href={creative.final_url}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-3 inline-flex items-center text-xs text-primary-600 hover:text-primary-700"
          >
            <span className="truncate max-w-[200px]">
              {truncate(creative.final_url, 40)}
            </span>
            <ExternalLink className="ml-1 h-3 w-3 flex-shrink-0" />
          </a>
        )}

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
