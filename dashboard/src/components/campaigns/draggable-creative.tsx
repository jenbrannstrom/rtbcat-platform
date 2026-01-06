'use client';

import { useRef, useEffect, useState, useCallback } from 'react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { AlertTriangle, Copy, Check } from 'lucide-react';
import { cn, getFormatLabel } from '@/lib/utils';

/**
 * Parse app info from destination URL
 * Returns { appId, appName } or null if not a recognized app store URL
 */
function parseAppFromUrl(url: string | undefined): { appId: string; appName: string } | null {
  if (!url) return null;

  try {
    const decoded = decodeURIComponent(url);

    // Play Store: https://play.google.com/store/apps/details?id=com.zhiliaoapp.musically
    const playStoreMatch = decoded.match(/play\.google\.com\/store\/apps\/details\?id=([a-zA-Z0-9._-]+)/);
    if (playStoreMatch) {
      const appId = playStoreMatch[1];
      // Format bundle ID: com.zhiliaoapp.musically -> "Zhiliaoapp Musically"
      const parts = appId.split('.');
      const relevantParts = parts.length > 2 ? parts.slice(-2) : parts.slice(-1);
      const appName = relevantParts
        .map(part =>
          part
            .replace(/([a-z])([A-Z])/g, '$1 $2')
            .replace(/[_-]/g, ' ')
            .replace(/\b\w/g, c => c.toUpperCase())
        )
        .join(' ');
      return { appId, appName };
    }

    // App Store: https://apps.apple.com/app/app-name/id123456789
    const appStoreMatch = decoded.match(/apps\.apple\.com\/[^/]+\/app\/([^/]+)\/id(\d+)/);
    if (appStoreMatch) {
      const appName = appStoreMatch[1].replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
      const appId = `id${appStoreMatch[2]}`;
      return { appId, appName };
    }

    // AppsFlyer: https://app.appsflyer.com/com.example.app?...
    const appsFlyerMatch = decoded.match(/app\.appsflyer\.com\/([a-zA-Z0-9._-]+)/);
    if (appsFlyerMatch) {
      const appId = appsFlyerMatch[1];
      const parts = appId.split('.');
      const relevantParts = parts.length > 2 ? parts.slice(-2) : parts.slice(-1);
      const appName = relevantParts
        .map(part =>
          part
            .replace(/([a-z])([A-Z])/g, '$1 $2')
            .replace(/[_-]/g, ' ')
            .replace(/\b\w/g, c => c.toUpperCase())
        )
        .join(' ');
      return { appId, appName };
    }

    return null;
  } catch {
    return null;
  }
}

interface Creative {
  id: string;
  format: string;
  final_url?: string;
  video?: { thumbnail_url?: string };
  native?: { logo?: { url?: string }; image?: { url?: string } };
  performance?: {
    total_spend_micros?: number;
    total_impressions?: number;
    total_clicks?: number;
    countries?: string[];
    date_range?: { start: string; end: string };
  };
  waste_flags?: { broken_video?: boolean; zero_engagement?: boolean };
}

interface DraggableCreativeProps {
  creative: Creative;
  clusterId: string;
  isLarge?: boolean;
  isDragOverlay?: boolean;
  isSelected?: boolean;
  isPopupOpen?: boolean;
  onSelect?: (id: string, event?: { ctrlKey?: boolean; metaKey?: boolean; shiftKey?: boolean }) => void;
  onTogglePopup?: (id: string | null) => void;
  onOpenPreview?: (id: string) => void;
}

function getThumbnail(creative: Creative): string | null {
  if (creative.format === 'VIDEO') {
    return creative.video?.thumbnail_url || `/thumbnails/${creative.id}.jpg`;
  }
  if (creative.format === 'NATIVE') {
    // Try image first (main asset), then logo
    return creative.native?.image?.url || creative.native?.logo?.url || null;
  }
  return null;
}

function formatSpend(micros?: number): string {
  if (!micros) return '$0';
  const dollars = micros / 1_000_000;
  if (dollars >= 1000) return `$${(dollars / 1000).toFixed(1)}K`;
  if (dollars >= 1) return `$${dollars.toFixed(0)}`;
  return `$${dollars.toFixed(2)}`;
}

export function DraggableCreative({
  creative,
  clusterId,
  isLarge = false,
  isDragOverlay = false,
  isSelected = false,
  isPopupOpen = false,
  onSelect,
  onTogglePopup,
  onOpenPreview,
}: DraggableCreativeProps) {
  const wasDraggingRef = useRef(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const [isHovered, setIsHovered] = useState(false);
  const [copied, setCopied] = useState(false);
  const [tooltipAlign, setTooltipAlign] = useState<'left' | 'center' | 'right'>('center');

  // Calculate tooltip alignment based on element position
  const updateTooltipPosition = useCallback(() => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const tooltipWidth = 280; // matches w-[280px]
    const halfTooltip = tooltipWidth / 2;

    // Check if tooltip would overflow left edge
    if (rect.left + rect.width / 2 < halfTooltip + 8) {
      setTooltipAlign('left');
    }
    // Check if tooltip would overflow right edge
    else if (window.innerWidth - (rect.left + rect.width / 2) < halfTooltip + 8) {
      setTooltipAlign('right');
    }
    else {
      setTooltipAlign('center');
    }
  }, []);

  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({
    id: String(creative.id),
    data: {
      clusterId,
      creative,
      type: 'creative',
    },
    disabled: isDragOverlay,
  });

  useEffect(() => {
    if (isDragging) {
      wasDraggingRef.current = true;
    }
  }, [isDragging]);

  const handleClick = (e: React.MouseEvent) => {
    if (wasDraggingRef.current) {
      wasDraggingRef.current = false;
      return;
    }

    // If ctrl/shift held, do multi-select
    if (e.ctrlKey || e.metaKey || e.shiftKey) {
      onSelect?.(String(creative.id), {
        ctrlKey: e.ctrlKey,
        metaKey: e.metaKey,
        shiftKey: e.shiftKey,
      });
      return;
    }

    // Plain click opens preview modal
    onOpenPreview?.(String(creative.id));
  };

  const handleCopyId = async (e: React.MouseEvent) => {
    e.stopPropagation();
    await navigator.clipboard.writeText(String(creative.id));
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const style = isDragOverlay ? undefined : {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  const thumbnail = getThumbnail(creative);
  const perf = creative.performance;
  const spend = perf?.total_spend_micros || 0;
  const impressions = perf?.total_impressions || 0;
  const clicks = perf?.total_clicks || 0;
  const ctr = impressions > 0 ? (clicks / impressions) * 100 : 0;
  const countries = perf?.countries || [];
  const isBrokenVideo = creative.waste_flags?.broken_video;

  // Show popup on click (persistent) or on hover (transient)
  const showTooltip = (isPopupOpen || isHovered) && !isDragging && !isDragOverlay;

  // Size classes for grid positioning
  const gridClass = isDragOverlay
    ? ""
    : isLarge
    ? "col-span-2 row-span-2"
    : "";

  // Parse app info from URL
  const appInfo = parseAppFromUrl(creative.final_url);

  return (
    <div
      ref={containerRef}
      className={cn(
        "relative",
        gridClass,
        isDragOverlay ? "w-14 h-14" : "w-full h-full"
      )}
      onMouseEnter={() => {
        if (!isDragOverlay) {
          updateTooltipPosition();
          setIsHovered(true);
        }
      }}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Popup - shows on hover or click */}
      {showTooltip && (
        <div
          className={cn(
            "absolute z-50 bottom-full mb-2 w-[280px] bg-gray-900 text-white text-xs rounded-lg p-3 shadow-xl",
            tooltipAlign === 'left' && "left-0",
            tooltipAlign === 'center' && "left-1/2 -translate-x-1/2",
            tooltipAlign === 'right' && "right-0"
          )}
          onClick={(e) => e.stopPropagation()}
        >
          {/* Creative ID with copy button */}
          <div className="flex items-center justify-between gap-2 mb-2">
            <span className="font-medium text-sm select-all truncate flex-1 min-w-0">#{creative.id}</span>
            <button
              onClick={handleCopyId}
              className="p-1 hover:bg-gray-700 rounded transition-colors"
              title="Copy ID"
            >
              {copied ? (
                <Check className="h-3.5 w-3.5 text-green-400" />
              ) : (
                <Copy className="h-3.5 w-3.5 text-gray-400" />
              )}
            </button>
          </div>

          {/* App info - shown prominently if detected */}
          {appInfo && (
            <div className="mb-2 pb-2 border-b border-gray-700">
              <div className="flex justify-between items-start">
                <span className="text-gray-400">App:</span>
                <div className="text-right flex-1 ml-2 min-w-0">
                  <div className="text-white font-medium">{appInfo.appName}</div>
                  <div className="text-gray-400 text-[10px] font-mono truncate select-all">{appInfo.appId}</div>
                </div>
              </div>
            </div>
          )}

          <div className="space-y-1 text-gray-300">
            <div className="flex justify-between">
              <span>Spend:</span>
              <span className="text-white font-medium">{formatSpend(spend)}</span>
            </div>
            <div className="flex justify-between">
              <span>Impressions:</span>
              <span className="text-white">{impressions.toLocaleString()}</span>
            </div>
            <div className="flex justify-between">
              <span>Clicks:</span>
              <span className="text-white">{clicks.toLocaleString()}</span>
            </div>
            <div className="flex justify-between">
              <span>CTR:</span>
              <span className="text-white">{ctr.toFixed(2)}%</span>
            </div>
            {countries.length > 0 && (
              <div className="flex justify-between">
                <span>Countries:</span>
                <span className="text-white">{countries.join(', ')}</span>
              </div>
            )}
          </div>

          {creative.final_url && (
            <div className="mt-2 pt-2 border-t border-gray-700">
              <div className="text-gray-400 text-[10px] mb-0.5">Destination:</div>
              <div className="text-blue-300 text-[11px] select-all break-all">{creative.final_url}</div>
            </div>
          )}

          {/* Arrow - positioned based on alignment */}
          <div className={cn(
            "absolute top-full border-8 border-transparent border-t-gray-900",
            tooltipAlign === 'left' && "left-4",
            tooltipAlign === 'center' && "left-1/2 -translate-x-1/2",
            tooltipAlign === 'right' && "right-4"
          )} />
        </div>
      )}

      {/* Inner draggable container with overflow-hidden */}
      <div
        ref={isDragOverlay ? undefined : setNodeRef}
        style={style}
        {...(isDragOverlay ? {} : attributes)}
        {...(isDragOverlay ? {} : listeners)}
        onClick={handleClick}
        className={cn(
          "relative w-full h-full rounded-md overflow-hidden border bg-gray-100 cursor-pointer select-none group",
          isDragging && "opacity-40",
          isDragOverlay && "ring-2 ring-blue-500 shadow-lg",
          isSelected && !isDragOverlay && "ring-2 ring-blue-500",
          isPopupOpen && !isDragOverlay && "ring-2 ring-blue-400",
        )}
      >
        {/* Thumbnail */}
        {thumbnail ? (
          <img
            src={thumbnail}
            alt=""
            className="w-full h-full object-cover"
            draggable={false}
            onError={(e) => {
              (e.target as HTMLImageElement).style.display = 'none';
            }}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-gray-400 text-xs">
            {getFormatLabel(creative.format)}
          </div>
        )}

        {/* Warning badge for broken videos */}
        {isBrokenVideo && (
          <div className="absolute top-0.5 right-0.5 bg-red-500 text-white rounded-full p-0.5">
            <AlertTriangle className="h-2.5 w-2.5" />
          </div>
        )}

        {/* Spend badge */}
        {spend > 0 && (
          <div className={cn(
            "absolute bottom-0 inset-x-0 bg-black/70 text-white text-center",
            isLarge ? "text-xs py-1" : "text-[9px] py-0.5"
          )}>
            {formatSpend(spend)}
          </div>
        )}

        {/* ID badge (large only) */}
        {isLarge && (
          <div className="absolute top-1 left-1 bg-black/50 text-white text-[10px] px-1 rounded">
            #{creative.id}
          </div>
        )}
      </div>
    </div>
  );
}
