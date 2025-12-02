"use client";

import { useEffect, useRef, useState } from "react";
import { X, Play, ExternalLink, Copy, Check, Loader2, Info, AlertTriangle, ChevronDown } from "lucide-react";
import type { Creative, CreativePerformanceSummary } from "@/types/api";
import { cn, getFormatColor, getStatusColor } from "@/lib/utils";
import { getCreative } from "@/lib/api";
import {
  parseDestinationUrls,
  getGoogleAuthBuyersUrl,
  extractBuyerIdFromName,
  isValidUrl,
  getUrlDisplayText,
  type ParsedUrl,
} from "@/lib/url-utils";

interface PreviewModalProps {
  creative: Creative;
  performance?: CreativePerformanceSummary;
  onClose: () => void;
}

// ============================================================================
// Formatting Helpers
// ============================================================================

function formatSpend(microDollars: number | null | undefined): string {
  if (!microDollars) return "$0";
  const dollars = microDollars / 1_000_000;
  if (dollars >= 1000) return `$${(dollars / 1000).toFixed(1)}K`;
  return `$${dollars.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatNumber(n: number | null | undefined): string {
  if (!n) return "0";
  return n.toLocaleString();
}

function formatCTR(ctr: number | null | undefined): string {
  if (ctr === null || ctr === undefined) return "-";
  return `${ctr.toFixed(2)}%`;
}

function formatCostMetric(micros: number | null | undefined): string {
  if (!micros) return "-";
  const dollars = micros / 1_000_000;
  return `$${dollars.toFixed(2)}`;
}

// ============================================================================
// Data Notes (Factual observations, not judgments)
// ============================================================================

type DataNote = {
  icon: "info" | "alert";
  message: string;
};

function getDataNotes(creative: Creative, performance?: CreativePerformanceSummary): DataNote[] {
  const notes: DataNote[] = [];

  if (!performance?.has_data) {
    return [{ icon: "info", message: "No performance data imported yet" }];
  }

  const imps = performance.total_impressions || 0;
  const clicks = performance.total_clicks || 0;

  // Clicks exceed impressions
  if (clicks > imps && imps > 0) {
    notes.push({
      icon: "alert",
      message: `Clicks (${clicks.toLocaleString()}) exceed impressions (${imps.toLocaleString()})`,
    });
  }

  // Zero clicks with impressions
  if (clicks === 0 && imps > 100) {
    notes.push({
      icon: "info",
      message: `Zero clicks recorded across ${imps.toLocaleString()} impressions`,
    });
  }

  // Video-specific note
  if (creative.format === "VIDEO") {
    notes.push({
      icon: "info",
      message: "Video completion data not available",
    });
  }

  return notes;
}

// ============================================================================
// Tracking Parameters Extraction
// ============================================================================

function extractTrackingParams(url: string | null | undefined): Record<string, string> {
  if (!url) return {};
  const params: Record<string, string> = {};
  try {
    const urlObj = new URL(url.startsWith("http") ? url : `https://${url}`);
    const trackingPrefixes = [
      "utm_", "af_", "adjust_", "c_", "pid", "campaign", "adgroup",
      "ad_id", "creative_id", "clickid", "gclid", "fbclid", "ttclid",
    ];

    urlObj.searchParams.forEach((value, key) => {
      const keyLower = key.toLowerCase();
      if (trackingPrefixes.some((prefix) => keyLower.startsWith(prefix) || keyLower === prefix)) {
        params[key] = value;
      }
    });
  } catch {
    // Invalid URL
  }
  return params;
}

// ============================================================================
// Subcomponents
// ============================================================================

function CopyButton({ text, className }: { text: string; className?: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <button
      onClick={handleCopy}
      className={cn("p-1 text-gray-400 hover:text-gray-600 rounded", className)}
      title="Copy"
    >
      {copied ? <Check className="h-3.5 w-3.5 text-green-500" /> : <Copy className="h-3.5 w-3.5" />}
    </button>
  );
}

function CollapsibleSection({
  title,
  children,
  defaultOpen = false,
  isEmpty = false,
}: {
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
  isEmpty?: boolean;
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  if (isEmpty) {
    return (
      <div className="border-t border-gray-200 py-2 px-4 text-sm text-gray-400">
        {title}: <span className="italic">none</span>
      </div>
    );
  }

  return (
    <div className="border-t border-gray-200">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full py-2 px-4 flex items-center justify-between text-sm font-medium hover:bg-gray-50"
      >
        <span>{title}</span>
        <ChevronDown className={cn("h-4 w-4 transition-transform", isOpen && "rotate-180")} />
      </button>
      {isOpen && <div className="px-4 pb-3 text-sm">{children}</div>}
    </div>
  );
}

function MetricCard({ value, label }: { value: string; label: string }) {
  return (
    <div className="text-center p-3 bg-gray-50 rounded-lg">
      <div className="text-lg font-semibold text-gray-900">{value}</div>
      <div className="text-xs text-gray-500">{label}</div>
    </div>
  );
}

function DataNotesSection({ notes }: { notes: DataNote[] }) {
  if (notes.length === 0) return null;

  return (
    <div className="bg-gray-50 border border-gray-200 rounded-lg p-3 space-y-2">
      {notes.map((note, i) => (
        <div key={i} className="flex items-start gap-2 text-sm">
          {note.icon === "alert" ? (
            <AlertTriangle className="h-4 w-4 text-amber-500 flex-shrink-0 mt-0.5" />
          ) : (
            <Info className="h-4 w-4 text-blue-500 flex-shrink-0 mt-0.5" />
          )}
          <span className={note.icon === "alert" ? "text-amber-700" : "text-gray-600"}>
            {note.message}
          </span>
        </div>
      ))}
    </div>
  );
}

// ============================================================================
// Preview Components
// ============================================================================

function extractVideoUrlFromVast(vastXml: string): string | null {
  const parser = new DOMParser();
  const doc = parser.parseFromString(vastXml, "text/xml");
  const mediaFile = doc.querySelector("MediaFile");
  if (mediaFile) {
    return mediaFile.textContent?.trim() || null;
  }
  return null;
}

function VideoPreviewPlayer({ creative }: { creative: Creative }) {
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
        <p>No video URL available</p>
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

function HtmlPreviewFrame({ creative }: { creative: Creative }) {
  const iframeRef = useRef<HTMLIFrameElement>(null);

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
              body { margin: 0; display: flex; justify-content: center; align-items: center; min-height: 100%; background: #f3f4f6; }
            </style>
          </head>
          <body>${creative.html.snippet}</body>
          </html>
        `);
        doc.close();
      }
    }
  }, [creative.html?.snippet]);

  if (!creative.html?.snippet) {
    return (
      <div className="flex items-center justify-center h-48 bg-gray-100 text-gray-400">
        No HTML snippet available
      </div>
    );
  }

  const creativeWidth = creative.html.width || creative.width || 300;
  const creativeHeight = creative.html.height || creative.height || 250;
  const maxWidth = 640;
  const maxHeight = 500;
  const scale = Math.min(1, maxWidth / creativeWidth, maxHeight / creativeHeight);
  const width = Math.round(creativeWidth * scale);
  const height = Math.round(creativeHeight * scale);

  return (
    <div className="flex flex-col items-center p-4 bg-gray-100">
      <iframe
        ref={iframeRef}
        title={`Creative ${creative.id}`}
        width={width}
        height={height}
        className="border border-gray-300 bg-white"
        sandbox="allow-scripts allow-same-origin"
      />
      <div className="mt-2 text-xs text-gray-500">
        {creativeWidth} × {creativeHeight}
        {scale < 1 && ` (scaled to ${Math.round(scale * 100)}%)`}
      </div>
    </div>
  );
}

function NativePreviewCard({ creative }: { creative: Creative }) {
  const native = creative.native;

  if (!native) {
    return (
      <div className="flex items-center justify-center h-48 bg-gray-100 text-gray-400">
        No native content available
      </div>
    );
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-hidden max-w-sm mx-auto">
      {native.image?.url && (
        <img
          src={native.image.url}
          alt={native.headline || "Native ad"}
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
              alt="Logo"
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

// ============================================================================
// Main Modal Component
// ============================================================================

export function PreviewModal({ creative: initialCreative, performance, onClose }: PreviewModalProps) {
  const [creative, setCreative] = useState<Creative>(initialCreative);
  const [isLoadingFull, setIsLoadingFull] = useState(false);

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleEsc);
    return () => window.removeEventListener("keydown", handleEsc);
  }, [onClose]);

  // Fetch full creative data for HTML format
  useEffect(() => {
    if (initialCreative.format === "HTML" && !initialCreative.html?.snippet) {
      setIsLoadingFull(true);
      getCreative(initialCreative.id)
        .then((fullCreative) => setCreative(fullCreative))
        .catch((err) => console.error("Failed to fetch full creative:", err))
        .finally(() => setIsLoadingFull(false));
    }
  }, [initialCreative.id, initialCreative.format, initialCreative.html?.snippet]);

  // Extract data from raw_data
  const rawData = (creative as unknown as { raw_data?: Record<string, unknown> }).raw_data;
  const rejectionReason = rawData?.rejectionReason as string | undefined;
  const declaredUrls = rawData?.declaredClickThroughUrls as string[] | undefined;
  const appName = rawData?.appName as string | undefined;
  const bundleId = rawData?.bundleId as string | undefined;

  // Google Console URL
  const buyerId = creative.buyer_id || extractBuyerIdFromName(creative.name);
  const googleUrl = buyerId ? getGoogleAuthBuyersUrl(buyerId, creative.id) : null;

  // Data notes
  const dataNotes = getDataNotes(creative, performance);

  // Parse URLs and tracking params
  const htmlSnippet = creative.html?.snippet || "";
  const allRawUrls = [creative.final_url, ...(declaredUrls || []), htmlSnippet].filter(Boolean).join(" ");
  const parsedUrls = parseDestinationUrls(allRawUrls);
  const trackingParams = extractTrackingParams(creative.final_url);
  const hasTrackingParams = Object.keys(trackingParams).length > 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />

      {/* Modal */}
      <div className="relative bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b flex-shrink-0">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-semibold text-gray-900 font-mono">#{creative.id}</h2>
              <CopyButton text={creative.id} />
            </div>
            {googleUrl && (
              <a
                href={googleUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-xs text-primary-600 hover:text-primary-700 mt-1"
              >
                <ExternalLink className="h-3 w-3" />
                View in Google Console
              </a>
            )}
          </div>
          <button onClick={onClose} className="ml-4 p-2 hover:bg-gray-100 rounded-full flex-shrink-0">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Scrollable content */}
        <div className="overflow-y-auto flex-1">
          {/* Preview Area */}
          <div className="bg-gray-50">
            {creative.format === "VIDEO" && <VideoPreviewPlayer creative={creative} />}
            {creative.format === "HTML" &&
              (isLoadingFull ? (
                <div className="flex items-center justify-center h-48 bg-gray-100 text-gray-500">
                  <Loader2 className="h-6 w-6 animate-spin mr-2" />
                  Loading HTML preview...
                </div>
              ) : (
                <HtmlPreviewFrame creative={creative} />
              ))}
            {creative.format === "NATIVE" && (
              <div className="p-4">
                <NativePreviewCard creative={creative} />
              </div>
            )}
            {!["VIDEO", "HTML", "NATIVE"].includes(creative.format) && (
              <div className="flex items-center justify-center h-48 bg-gray-100 text-gray-400">
                Preview not available for {creative.format} format
              </div>
            )}
          </div>

          {/* Performance Section */}
          <div className="p-4 border-b">
            {performance?.has_data ? (
              <>
                {/* 4-metric grid */}
                <div className="grid grid-cols-4 gap-2">
                  <MetricCard value={formatSpend(performance.total_spend_micros)} label="Spend" />
                  <MetricCard value={formatNumber(performance.total_impressions)} label="Imps" />
                  <MetricCard value={formatNumber(performance.total_clicks)} label="Clicks" />
                  <MetricCard value={formatCTR(performance.ctr_percent)} label="CTR" />
                </div>
                {/* CPM/CPC secondary */}
                <div className="mt-2 text-xs text-gray-500 text-center">
                  CPM: {formatCostMetric(performance.avg_cpm_micros)} · CPC:{" "}
                  {formatCostMetric(performance.avg_cpc_micros)}
                </div>
              </>
            ) : (
              <div className="text-center text-gray-400 py-4">No performance data available</div>
            )}
          </div>

          {/* Data Notes */}
          {dataNotes.length > 0 && (
            <div className="p-4 border-b">
              <DataNotesSection notes={dataNotes} />
            </div>
          )}

          {/* Collapsible Sections */}
          <div>
            {/* Creative Details - Open by default */}
            <CollapsibleSection title="Creative Details" defaultOpen={true}>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-gray-500">Status</span>
                  <span className={cn("badge", getStatusColor(creative.approval_status || ""))}>
                    {creative.approval_status?.replace(/_/g, " ") || "-"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Format</span>
                  <span>
                    {creative.format}
                    {creative.width && creative.height && ` (${creative.width}×${creative.height})`}
                  </span>
                </div>
                {rejectionReason && (
                  <div className="flex justify-between">
                    <span className="text-gray-500">Rejection</span>
                    <span className="text-red-600">{rejectionReason}</span>
                  </div>
                )}
                {creative.advertiser_name && (
                  <div className="flex justify-between">
                    <span className="text-gray-500">Advertiser</span>
                    <span>{creative.advertiser_name}</span>
                  </div>
                )}
                {appName && (
                  <div className="flex justify-between">
                    <span className="text-gray-500">App Name</span>
                    <span>{appName}</span>
                  </div>
                )}
              </div>
            </CollapsibleSection>

            {/* Destination URLs */}
            <CollapsibleSection title="Destination URLs" isEmpty={parsedUrls.length === 0}>
              <div className="space-y-2">
                {parsedUrls.slice(0, 5).map((url, i) => (
                  <div key={i} className="flex items-start gap-2">
                    <span className="text-gray-400">→</span>
                    <a
                      href={url.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-primary-600 hover:text-primary-700 truncate flex-1"
                    >
                      {getUrlDisplayText(url)}
                    </a>
                  </div>
                ))}
                {parsedUrls.length > 5 && (
                  <div className="text-xs text-gray-400">+{parsedUrls.length - 5} more URLs</div>
                )}
              </div>
            </CollapsibleSection>

            {/* Tracking Parameters */}
            <CollapsibleSection title="Tracking Parameters" isEmpty={!hasTrackingParams}>
              <div className="space-y-1">
                {Object.entries(trackingParams).map(([key, value]) => (
                  <div key={key} className="flex justify-between text-xs">
                    <span className="text-gray-500 font-mono">{key}</span>
                    <span className="text-gray-700 truncate max-w-[200px]">{value}</span>
                  </div>
                ))}
              </div>
            </CollapsibleSection>

            {/* Technical IDs */}
            <CollapsibleSection title="Technical IDs">
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-gray-500">Creative ID</span>
                  <div className="flex items-center gap-1">
                    <span className="font-mono text-xs">{creative.id}</span>
                    <CopyButton text={creative.id} />
                  </div>
                </div>
                {creative.account_id && (
                  <div className="flex justify-between items-center">
                    <span className="text-gray-500">Account ID</span>
                    <div className="flex items-center gap-1">
                      <span className="font-mono text-xs">{creative.account_id}</span>
                      <CopyButton text={creative.account_id} />
                    </div>
                  </div>
                )}
                {creative.buyer_id && (
                  <div className="flex justify-between items-center">
                    <span className="text-gray-500">Buyer ID</span>
                    <div className="flex items-center gap-1">
                      <span className="font-mono text-xs">{creative.buyer_id}</span>
                      <CopyButton text={creative.buyer_id} />
                    </div>
                  </div>
                )}
                {bundleId && (
                  <div className="flex justify-between items-center">
                    <span className="text-gray-500">Bundle ID</span>
                    <div className="flex items-center gap-1">
                      <span className="font-mono text-xs">{bundleId}</span>
                      <CopyButton text={bundleId} />
                    </div>
                  </div>
                )}
              </div>
            </CollapsibleSection>
          </div>
        </div>
      </div>
    </div>
  );
}
