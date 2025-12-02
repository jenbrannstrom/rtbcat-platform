'use client';

import { useDroppable } from '@dnd-kit/core';
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable';
import { ListItem } from './list-item';
import { cn } from '@/lib/utils';

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
  };
}

interface ListClusterProps {
  id: string;
  name: string;
  creatives: Creative[];
  isUnclustered?: boolean;
  selectedIds?: Set<string>;
  onCreativeSelect?: (id: string, event?: { ctrlKey?: boolean; metaKey?: boolean; shiftKey?: boolean }) => void;
}

function formatSpend(micros?: number): string {
  if (!micros) return '$0';
  const dollars = micros / 1_000_000;
  if (dollars >= 1000) return `$${(dollars / 1000).toFixed(1)}K`;
  if (dollars >= 1) return `$${dollars.toFixed(0)}`;
  return `$${dollars.toFixed(2)}`;
}

export function ListCluster({
  id,
  name,
  creatives,
  isUnclustered = false,
  selectedIds = new Set(),
  onCreativeSelect,
}: ListClusterProps) {
  const { setNodeRef, isOver } = useDroppable({ id });

  // Calculate total spend
  const totalSpend = creatives.reduce(
    (sum, c) => sum + (c.performance?.total_spend_micros || 0),
    0
  );

  return (
    <div
      ref={setNodeRef}
      className={cn(
        "w-80 flex-shrink-0 rounded-lg border bg-white flex flex-col",
        isOver && "border-blue-500 bg-blue-50",
        isUnclustered && "bg-gray-50"
      )}
      style={{ maxHeight: '70vh' }}
    >
      {/* Header */}
      <div className="p-3 border-b bg-gray-50 rounded-t-lg flex-shrink-0">
        <div className="font-medium truncate">{name}</div>
        <div className="text-sm text-gray-500 flex gap-2">
          <span>{creatives.length} creative{creatives.length !== 1 ? 's' : ''}</span>
          {totalSpend > 0 && (
            <>
              <span>·</span>
              <span className="text-green-600">{formatSpend(totalSpend)}</span>
            </>
          )}
        </div>
      </div>

      {/* Scrollable list */}
      <div className="overflow-y-auto flex-1 p-2" style={{ maxHeight: 'calc(70vh - 70px)' }}>
        <SortableContext
          items={creatives.map(c => String(c.id))}
          strategy={verticalListSortingStrategy}
        >
          {creatives.map(creative => (
            <ListItem
              key={creative.id}
              creative={creative}
              clusterId={id}
              isSelected={selectedIds.has(String(creative.id))}
              onSelect={onCreativeSelect}
            />
          ))}
        </SortableContext>

        {creatives.length === 0 && (
          <div className="text-gray-400 text-sm py-8 text-center">
            {isUnclustered
              ? 'All creatives are clustered'
              : 'Drag creatives here'
            }
          </div>
        )}
      </div>
    </div>
  );
}
