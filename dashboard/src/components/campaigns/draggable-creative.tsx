'use client';

import { useState } from 'react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface Creative {
  id: string;
  format: string;
  video?: { thumbnail_url?: string };
  native?: { logo?: { url?: string }; image?: { url?: string } };
  performance?: { total_spend_micros?: number; total_impressions?: number };
  waste_flags?: { broken_video?: boolean; zero_engagement?: boolean };
}

interface DraggableCreativeProps {
  creative: Creative;
  clusterId: string;
  isLarge?: boolean;
  isDragOverlay?: boolean;
}

function getThumbnail(creative: Creative): string | null {
  if (creative.format === 'VIDEO') {
    return creative.video?.thumbnail_url || `/thumbnails/${creative.id}.jpg`;
  }
  if (creative.format === 'NATIVE') {
    return creative.native?.logo?.url || creative.native?.image?.url || null;
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
}: DraggableCreativeProps) {
  const [isPressing, setIsPressing] = useState(false);

  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({
    id: creative.id,
    data: { clusterId, creative },
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  const thumbnail = getThumbnail(creative);
  const spend = creative.performance?.total_spend_micros || 0;
  const hasActivity = spend > 0 || (creative.performance?.total_impressions || 0) > 0;
  const isBrokenVideo = creative.waste_flags?.broken_video;

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      onPointerDown={() => setIsPressing(true)}
      onPointerUp={() => setIsPressing(false)}
      onPointerCancel={() => setIsPressing(false)}
      className={cn(
        "relative rounded-md overflow-hidden border bg-gray-100 cursor-grab select-none",
        "transition-all duration-150",
        isLarge && "col-span-2 row-span-2",
        !hasActivity && "opacity-50",  // Grey out if no spend/impressions
        isPressing && !isDragging && "ring-2 ring-blue-400 scale-[1.02]",
        isDragging && "opacity-40",
        isDragOverlay && "ring-2 ring-blue-500 shadow-lg scale-105",
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
          {creative.format}
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
  );
}
