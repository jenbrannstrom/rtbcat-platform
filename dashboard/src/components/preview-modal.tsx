"use client";

import { useEffect, useRef, useState } from "react";
import { X, Play, ExternalLink, Copy, Check, Loader2, Info, ChevronDown, ChevronUp } from "lucide-react";
import type { Creative } from "@/types/api";
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
  onClose: () => void;
}

function extractVideoUrlFromVast(vastXml: string): string | null {
  const parser = new DOMParser();
  const doc = parser.parseFromString(vastXml, "text/xml");
  const mediaFile = doc.querySelector("MediaFile");
  if (mediaFile) {
    return mediaFile.textContent?.trim() || null;
  }
  return null;
}

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
      {copied ? (
        <Check className="h-3.5 w-3.5 text-green-500" />
      ) : (
        <Copy className="h-3.5 w-3.5" />
      )}
    </button>
  );
}

function Tooltip({ content, children }: { content: string; children: React.ReactNode }) {
  const [show, setShow] = useState(false);

  return (
    <div className="relative inline-flex">
      <div
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => setShow(false)}
      >
        {children}
      </div>
      {show && (
        <div className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 text-xs text-white bg-gray-900 rounded shadow-lg whitespace-nowrap max-w-xs">
          {content}
          <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-900" />
        </div>
      )}
    </div>
  );
}

function UrlRow({ parsedUrl }: { parsedUrl: ParsedUrl }) {
  const [showCopy, setShowCopy] = useState(false);

  if (!isValidUrl(parsedUrl.url)) {
    return (
      <div className="flex items-center gap-2 py-1.5 px-2 text-sm text-red-600">
        <span className="text-gray-400">→</span>
        <span>Invalid URL</span>
      </div>
    );
  }

  return (
    <div
      className="flex items-center gap-2 py-1.5 px-2 rounded hover:bg-gray-50 group"
      onMouseEnter={() => setShowCopy(true)}
      onMouseLeave={() => setShowCopy(false)}
    >
      <span className="text-gray-400 flex-shrink-0">→</span>
      <a
        href={parsedUrl.url}
        target="_blank"
        rel="noopener noreferrer"
        className="flex-1 min-w-0 flex items-center gap-2 text-sm hover:text-primary-600"
      >
        <span className="text-gray-700 font-medium">{parsedUrl.label}:</span>
        <span className="font-mono text-gray-600 truncate">
          {getUrlDisplayText(parsedUrl)}
        </span>
        {parsedUrl.isPrimary && (
          <span className="flex-shrink-0 px-1.5 py-0.5 text-[10px] font-medium bg-green-100 text-green-700 rounded">
            PRIMARY
          </span>
        )}
        <ExternalLink className="h-3 w-3 text-gray-400 flex-shrink-0" />
      </a>
      {parsedUrl.tooltip && (
        <Tooltip content={parsedUrl.tooltip}>
          <Info className="h-3.5 w-3.5 text-gray-400 hover:text-gray-600 cursor-help flex-shrink-0" />
        </Tooltip>
      )}
      <CopyButton
        text={parsedUrl.url}
        className={cn("flex-shrink-0 transition-opacity", showCopy ? "opacity-100" : "opacity-0")}
      />
    </div>
  );
}

function DestinationUrlsSection({ creative }: { creative: Creative }) {
  const [showAll, setShowAll] = useState(false);
  const MAX_VISIBLE = 5;

  // Combine all possible URL sources
  const rawData = (creative as unknown as { raw_data?: Record<string, unknown> }).raw_data;
  const declaredUrls = rawData?.declaredClickThroughUrls as string[] | undefined;

  // For HTML creatives, the real URLs are often embedded in the HTML snippet
  const htmlSnippet = creative.html?.snippet || "";

  // Parse URLs from final_url, declared URLs, and HTML snippet
  const allRawUrls = [
    creative.final_url,
    ...(declaredUrls || []),
    htmlSnippet, // This may contain embedded URLs
  ].filter(Boolean).join(" ");

  const parsedUrls = parseDestinationUrls(allRawUrls);

  if (parsedUrls.length === 0) {
    return (
      <div className="py-2">
        <dt className="text-xs font-medium text-gray-500 uppercase tracking-wider">
          Destination URLs
        </dt>
        <dd className="mt-1 text-sm text-gray-500 italic">
          No destination URL specified
        </dd>
      </div>
    );
  }

  const visibleUrls = showAll ? parsedUrls : parsedUrls.slice(0, MAX_VISIBLE);
  const hiddenCount = parsedUrls.length - MAX_VISIBLE;

  return (
    <div className="py-2">
      <dt className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">
        Destination URLs
      </dt>
      <dd className="bg-gray-50 rounded-lg border border-gray-100 py-1">
        {visibleUrls.map((url, index) => (
          <UrlRow key={`${url.url}-${index}`} parsedUrl={url} />
        ))}
        {hiddenCount > 0 && !showAll && (
          <button
            onClick={() => setShowAll(true)}
            className="w-full flex items-center justify-center gap-1 py-1.5 px-2 text-xs text-primary-600 hover:text-primary-700 hover:bg-gray-100"
          >
            <ChevronDown className="h-3.5 w-3.5" />
            Show {hiddenCount} more URL{hiddenCount > 1 ? "s" : ""}
          </button>
        )}
        {showAll && parsedUrls.length > MAX_VISIBLE && (
          <button
            onClick={() => setShowAll(false)}
            className="w-full flex items-center justify-center gap-1 py-1.5 px-2 text-xs text-gray-500 hover:text-gray-700 hover:bg-gray-100"
          >
            <ChevronUp className="h-3.5 w-3.5" />
            Show less
          </button>
        )}
      </dd>
    </div>
  );
}

function GoogleAuthBuyersLink({ creative }: { creative: Creative }) {
  // Try buyer_id first, fallback to extracting from name
  const buyerId = creative.buyer_id || extractBuyerIdFromName(creative.name);

  if (!buyerId) return null;

  const url = getGoogleAuthBuyersUrl(buyerId, creative.id);

  return (
    <div className="py-2">
      <dt className="text-xs font-medium text-gray-500 uppercase tracking-wider">
        Google Console
      </dt>
      <dd className="mt-1">
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 text-sm text-primary-600 hover:text-primary-700"
        >
          <span>Google Auth. Buyers</span>
          <ExternalLink className="h-3.5 w-3.5" />
        </a>
      </dd>
    </div>
  );
}

function LabeledField({
  label,
  value,
  isLink = false,
  copyable = false,
}: {
  label: string;
  value: string | null | undefined;
  isLink?: boolean;
  copyable?: boolean;
}) {
  if (!value) return null;

  return (
    <div className="py-2">
      <dt className="text-xs font-medium text-gray-500 uppercase tracking-wider">
        {label}
      </dt>
      <dd className="mt-1 flex items-center gap-2">
        {isLink ? (
          <a
            href={value.startsWith("http") ? value : `https://${value}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-primary-600 hover:text-primary-700 truncate max-w-md"
          >
            {value}
            <ExternalLink className="inline ml-1 h-3 w-3" />
          </a>
        ) : (
          <span className="text-sm text-gray-900 truncate max-w-md">{value}</span>
        )}
        {copyable && <CopyButton text={value} />}
      </dd>
    </div>
  );
}

function VideoPreviewPlayer({ creative }: { creative: Creative }) {
  const videoRef = useRef<HTMLVideoElement>(null);

  let videoUrl = creative.video?.video_url;
  if (!videoUrl && creative.video?.vast_xml) {
    videoUrl = extractVideoUrlFromVast(creative.video.vast_xml);
  }

  if (!videoUrl) {
    return (
      <div className="flex items-center justify-center h-48 bg-gray-900 text-gray-400">
        <div className="text-center">
          <Play className="h-10 w-10 mx-auto mb-2 opacity-50" />
          <p>No video URL available</p>
          {creative.video?.vast_xml && (
            <p className="text-xs mt-2">VAST XML present but no MediaFile found</p>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="bg-black flex items-center justify-center">
      <video
        ref={videoRef}
        src={videoUrl}
        controls
        className="max-w-full max-h-[300px] w-auto h-auto"
        poster=""
      >
        Your browser does not support the video tag.
      </video>
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

  const width = Math.min(creative.html.width || creative.width || 300, 600);
  const height = Math.min(creative.html.height || creative.height || 250, 300);

  return (
    <div className="flex justify-center p-4 bg-gray-100">
      <iframe
        ref={iframeRef}
        title={`Creative ${creative.id}`}
        width={width}
        height={height}
        className="border border-gray-300 bg-white"
        sandbox="allow-scripts allow-same-origin"
      />
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
              <h3 className="font-semibold text-gray-900 text-sm line-clamp-2">
                {native.headline}
              </h3>
            )}
            {native.body && (
              <p className="mt-1 text-xs text-gray-600 line-clamp-2">
                {native.body}
              </p>
            )}
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

export function PreviewModal({ creative: initialCreative, onClose }: PreviewModalProps) {
  const [creative, setCreative] = useState<Creative>(initialCreative);
  const [isLoadingFull, setIsLoadingFull] = useState(false);

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleEsc);
    return () => window.removeEventListener("keydown", handleEsc);
  }, [onClose]);

  // Fetch full creative data for HTML format (slim mode excludes html_snippet)
  useEffect(() => {
    if (initialCreative.format === "HTML" && !initialCreative.html?.snippet) {
      setIsLoadingFull(true);
      getCreative(initialCreative.id)
        .then((fullCreative) => {
          setCreative(fullCreative);
        })
        .catch((err) => {
          console.error("Failed to fetch full creative:", err);
        })
        .finally(() => {
          setIsLoadingFull(false);
        });
    }
  }, [initialCreative.id, initialCreative.format, initialCreative.html?.snippet]);

  // Extract rejection reason from raw_data if present
  const rawData = (creative as unknown as { raw_data?: Record<string, unknown> }).raw_data;
  const rejectionReason = rawData?.rejectionReason as string | undefined;
  const declaredUrls = rawData?.declaredClickThroughUrls as string[] | undefined;
  const appStoreUrl = rawData?.appStoreUrl as string | undefined;
  const appName = rawData?.appName as string | undefined;
  const bundleId = rawData?.bundleId as string | undefined;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b flex-shrink-0">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-semibold text-gray-900">
                {creative.id}
              </h2>
              <CopyButton text={creative.id} />
            </div>
            <p className="text-xs text-gray-500 truncate">{creative.name}</p>
          </div>
          <button
            onClick={onClose}
            className="ml-4 p-2 hover:bg-gray-100 rounded-full flex-shrink-0"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Scrollable content */}
        <div className="overflow-y-auto flex-1">
          {/* Preview - Top section */}
          <div className="bg-gray-50">
            {creative.format === "VIDEO" && (
              <VideoPreviewPlayer creative={creative} />
            )}
            {creative.format === "HTML" && (
              isLoadingFull ? (
                <div className="flex items-center justify-center h-48 bg-gray-100 text-gray-500">
                  <Loader2 className="h-6 w-6 animate-spin mr-2" />
                  Loading HTML preview...
                </div>
              ) : (
                <HtmlPreviewFrame creative={creative} />
              )
            )}
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

          {/* Labeled Fields - Card below preview */}
          <div className="p-4">
            {/* Status badges */}
            <div className="flex flex-wrap gap-2 mb-4">
              <span className={cn("badge", getFormatColor(creative.format))}>
                {creative.format}
              </span>
              {creative.approval_status && (
                <span className={cn("badge", getStatusColor(creative.approval_status))}>
                  {creative.approval_status.replace(/_/g, " ")}
                </span>
              )}
              {creative.width && creative.height && (
                <span className="badge bg-gray-100 text-gray-700">
                  {creative.width}x{creative.height}
                </span>
              )}
            </div>

            {/* Fields grid */}
            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 divide-y sm:divide-y-0">
              <div className="sm:border-r sm:border-gray-100 sm:pr-6">
                <LabeledField label="Type" value={creative.format} />
                <LabeledField label="Status" value={creative.approval_status?.replace(/_/g, " ")} />
                <LabeledField label="Rejection Reason" value={rejectionReason} />
                <LabeledField label="Advertiser" value={creative.advertiser_name} />
                <LabeledField label="Account ID" value={creative.account_id} copyable />
                <LabeledField label="Buyer ID" value={creative.buyer_id} copyable />
                <GoogleAuthBuyersLink creative={creative} />
              </div>
              <div className="sm:pl-6">
                <DestinationUrlsSection creative={creative} />
                <LabeledField label="App Name" value={appName} />
                <LabeledField label="Bundle ID" value={bundleId} copyable />
              </div>
            </dl>

            {/* UTM Parameters section */}
            {(creative.utm_campaign || creative.utm_source || creative.utm_medium) && (
              <div className="mt-4 pt-4 border-t border-gray-100">
                <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-3">
                  UTM Parameters
                </h3>
                <dl className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  {creative.utm_source && (
                    <div>
                      <dt className="text-xs text-gray-500">Source</dt>
                      <dd className="text-sm text-gray-900">{creative.utm_source}</dd>
                    </div>
                  )}
                  {creative.utm_medium && (
                    <div>
                      <dt className="text-xs text-gray-500">Medium</dt>
                      <dd className="text-sm text-gray-900">{creative.utm_medium}</dd>
                    </div>
                  )}
                  {creative.utm_campaign && (
                    <div>
                      <dt className="text-xs text-gray-500">Campaign</dt>
                      <dd className="text-sm text-gray-900">{creative.utm_campaign}</dd>
                    </div>
                  )}
                  {creative.utm_content && (
                    <div>
                      <dt className="text-xs text-gray-500">Content</dt>
                      <dd className="text-sm text-gray-900">{creative.utm_content}</dd>
                    </div>
                  )}
                  {creative.utm_term && (
                    <div>
                      <dt className="text-xs text-gray-500">Term</dt>
                      <dd className="text-sm text-gray-900">{creative.utm_term}</dd>
                    </div>
                  )}
                </dl>
              </div>
            )}

            {/* Video metadata */}
            {creative.format === "VIDEO" && creative.video?.duration && (
              <div className="mt-4 pt-4 border-t border-gray-100">
                <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-3">
                  Video Details
                </h3>
                <dl className="grid grid-cols-2 gap-3">
                  <div>
                    <dt className="text-xs text-gray-500">Duration</dt>
                    <dd className="text-sm text-gray-900">{creative.video.duration}</dd>
                  </div>
                  {creative.video.video_url && (
                    <div>
                      <dt className="text-xs text-gray-500">Video URL</dt>
                      <dd className="text-sm text-gray-900 truncate">
                        <a
                          href={creative.video.video_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-primary-600 hover:text-primary-700"
                        >
                          View source
                          <ExternalLink className="inline ml-1 h-3 w-3" />
                        </a>
                      </dd>
                    </div>
                  )}
                </dl>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
