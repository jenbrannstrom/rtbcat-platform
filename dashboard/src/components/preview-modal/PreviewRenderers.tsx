"use client";

import { useEffect, useRef } from "react";
import { Play } from "lucide-react";
import { useTranslation } from "@/contexts/i18n-context";
import type { Creative } from "@/types/api";
import { cn } from "@/lib/utils";

/**
 * Extract video URL from VAST XML.
 */
function extractVideoUrlFromVast(vastXml: string): string | null {
  const parser = new DOMParser();
  const doc = parser.parseFromString(vastXml, "text/xml");
  const mediaFile = doc.querySelector("MediaFile");
  if (mediaFile) {
    return mediaFile.textContent?.trim() || null;
  }
  return null;
}

/**
 * Video preview player component.
 */
export function VideoPreviewPlayer({ creative }: { creative: Creative }) {
  const { t } = useTranslation();
  const videoRef = useRef<HTMLVideoElement>(null);

  let videoUrl = creative.video?.video_url;
  if (!videoUrl && creative.video?.vast_xml) {
    videoUrl = extractVideoUrlFromVast(creative.video.vast_xml);
  }

  const creativeWidth = creative.width || 640;
  const creativeHeight = creative.height || 360;
  const maxWidth = 640;
  const maxHeight = 400;
  const scale = Math.min(1, maxWidth / creativeWidth, maxHeight / creativeHeight);
  const displayWidth = Math.round(creativeWidth * scale);
  const displayHeight = Math.round(creativeHeight * scale);

  if (!videoUrl) {
    return (
      <div className="flex flex-col items-center justify-center h-48 bg-gray-900 text-gray-400">
        <Play className="h-10 w-10 mx-auto mb-2 opacity-50" />
        <p>{t.previewModal.noVideoUrlAvailable}</p>
      </div>
    );
  }

  return (
    <div className="bg-black flex flex-col items-center justify-center p-4">
      <video
        ref={videoRef}
        src={videoUrl}
        controls
        width={displayWidth}
        height={displayHeight}
        className="bg-black"
      />
      {creative.width && creative.height && (
        <div className="mt-2 text-xs text-gray-400">
          {creative.width} × {creative.height}
          {creative.video?.duration && ` · ${creative.video.duration}`}
        </div>
      )}
    </div>
  );
}

/**
 * HTML preview iframe component.
 */
export function HtmlPreviewFrame({ creative, destinationUrl }: { creative: Creative; destinationUrl?: string }) {
  const { t } = useTranslation();
  const iframeRef = useRef<HTMLIFrameElement>(null);

  const creativeWidth = creative.html?.width || creative.width || 300;
  const creativeHeight = creative.html?.height || creative.height || 250;

  useEffect(() => {
    if (iframeRef.current && creative.html?.snippet) {
      const doc = iframeRef.current.contentDocument;
      if (doc) {
        doc.open();
        doc.write(`
          <!DOCTYPE html>
          <html>
          <head>
            <style>
              * { box-sizing: border-box; }
              html, body {
                margin: 0;
                padding: 0;
                width: ${creativeWidth}px;
                height: ${creativeHeight}px;
                overflow: hidden;
                background: #fff;
              }
              body {
                display: flex;
                justify-content: center;
                align-items: center;
              }
              img, video, canvas {
                max-width: 100%;
                max-height: 100%;
              }
            </style>
          </head>
          <body>${creative.html.snippet}</body>
          </html>
        `);
        doc.close();
      }
    }
  }, [creative.html?.snippet, creativeWidth, creativeHeight]);

  if (!creative.html?.snippet) {
    return (
      <div className="flex items-center justify-center h-48 bg-gray-100 text-gray-400">
        {t.previewModal.noHtmlSnippetAvailable}
      </div>
    );
  }

  const maxWidth = 640;
  const maxHeight = 500;
  const scale = Math.min(1, maxWidth / creativeWidth, maxHeight / creativeHeight);
  const displayWidth = Math.round(creativeWidth * scale);
  const displayHeight = Math.round(creativeHeight * scale);

  const handleClick = () => {
    if (destinationUrl) {
      window.open(destinationUrl, '_blank', 'noopener,noreferrer');
    }
  };

  return (
    <div className="flex flex-col items-center p-4 bg-gray-100">
      <div
        className={cn(
          "border border-gray-300 bg-white overflow-hidden relative",
          destinationUrl && "cursor-pointer group"
        )}
        style={{ width: displayWidth, height: displayHeight }}
        onClick={handleClick}
        title={destinationUrl ? t.previewModal.clickToOpenDestination : undefined}
      >
        <iframe
          ref={iframeRef}
          title={t.previewModal.creativeIframeTitle.replace("{id}", creative.id)}
          width={creativeWidth}
          height={creativeHeight}
          className="border-0 pointer-events-none"
          style={{
            transform: scale < 1 ? `scale(${scale})` : undefined,
            transformOrigin: 'top left',
          }}
          sandbox="allow-scripts allow-same-origin"
        />
        {destinationUrl && (
          <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors flex items-center justify-center">
            <span className="opacity-0 group-hover:opacity-100 bg-white/90 text-gray-700 text-xs px-2 py-1 rounded shadow transition-opacity">
              {t.previewModal.clickToOpenDestination}
            </span>
          </div>
        )}
      </div>
      <div className="mt-2 text-xs text-gray-500">
        {creativeWidth} × {creativeHeight}
        {scale < 1 && ` (${t.previewModal.scaledToPercent.replace("{percent}", String(Math.round(scale * 100)))})`}
      </div>
    </div>
  );
}

/**
 * Native ad preview card component.
 */
export function NativePreviewCard({ creative }: { creative: Creative }) {
  const { t } = useTranslation();
  const native = creative.native;

  if (!native) {
    return (
      <div className="flex items-center justify-center h-48 bg-gray-100 text-gray-400">
        {t.previewModal.noNativeContentAvailable}
      </div>
    );
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-hidden max-w-sm mx-auto">
      {native.image?.url && (
        <img
          src={native.image.url}
          alt={native.headline || t.previewModal.nativeAdAlt}
          className="w-full h-40 object-cover"
          onError={(e) => {
            (e.target as HTMLImageElement).style.display = "none";
          }}
        />
      )}
      <div className="p-3">
        <div className="flex items-start gap-2">
          {native.logo?.url && (
            <img
              src={native.logo.url}
              alt={t.previewModal.logoAlt}
              className="w-8 h-8 rounded object-cover flex-shrink-0"
              onError={(e) => {
                (e.target as HTMLImageElement).style.display = "none";
              }}
            />
          )}
          <div className="flex-1">
            {native.headline && (
              <h3 className="font-semibold text-gray-900 text-sm line-clamp-2">{native.headline}</h3>
            )}
            {native.body && <p className="mt-1 text-xs text-gray-600 line-clamp-2">{native.body}</p>}
          </div>
        </div>
        {native.call_to_action && (
          <button className="mt-3 w-full py-1.5 px-3 bg-blue-600 text-white rounded text-xs font-medium">
            {native.call_to_action}
          </button>
        )}
      </div>
    </div>
  );
}
