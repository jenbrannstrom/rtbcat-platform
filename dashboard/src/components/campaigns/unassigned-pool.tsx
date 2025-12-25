'use client';

import { useState } from 'react';
import { useDroppable } from '@dnd-kit/core';
import { SortableContext, rectSortingStrategy } from '@dnd-kit/sortable';
import { ChevronDown } from 'lucide-react';
import { DraggableCreative } from './draggable-creative';
import { cn } from '@/lib/utils';

interface Creative {
  id: string;
  format: string;
  performance?: { total_spend_micros?: number; total_impressions?: number };
  waste_flags?: { broken_video?: boolean; zero_engagement?: boolean };
}

interface UnassignedPoolProps {
  creativeIds: string[];
  creatives: Map<string, Creative>;
  selectedIds: Set<string>;
  onCreativeSelect: (id: string, event?: { ctrlKey?: boolean; metaKey?: boolean; shiftKey?: boolean }) => void;
}

export function UnassignedPool({ creativeIds, creatives, selectedIds, onCreativeSelect }: UnassignedPoolProps) {
  const [isExpanded, setIsExpanded] = useState(true);
  const [openPopupId, setOpenPopupId] = useState<string | null>(null);

  const { setNodeRef, isOver } = useDroppable({
    id: 'unassigned',
  });

  const handleTogglePopup = (creativeId: string | null) => {
    setOpenPopupId(creativeId);
  };

  const unassignedCreatives = creativeIds
    .map(id => creatives.get(id))
    .filter(Boolean) as Creative[];

  return (
    <div
      ref={setNodeRef}
      className={cn(
        "rounded-xl border-2 p-4 transition-colors",
        isOver ? "border-blue-500 bg-blue-50" : "border-gray-200 bg-gray-50"
      )}
    >
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between text-left"
      >
        <h3 className="text-lg font-semibold">
          Unclustered
          <span className="text-gray-400 font-normal ml-2">
            ({creativeIds.length} creatives)
          </span>
        </h3>
        <ChevronDown
          className={cn(
            "h-5 w-5 text-gray-400 transition-transform",
            isExpanded && "rotate-180"
          )}
        />
      </button>

      {/* Grid */}
      {isExpanded && (
        <SortableContext items={creativeIds.map(id => String(id))} strategy={rectSortingStrategy}>
          <div className="mt-4 flex flex-wrap gap-1 min-h-[60px]">
            {unassignedCreatives.map(creative => (
              <div key={creative.id} className="w-14 h-14">
                <DraggableCreative
                  creative={creative}
                  clusterId="unassigned"
                  isSelected={selectedIds.has(String(creative.id))}
                  isPopupOpen={openPopupId === String(creative.id)}
                  onSelect={onCreativeSelect}
                  onTogglePopup={handleTogglePopup}
                />
              </div>
            ))}

            {unassignedCreatives.length === 0 && (
              <div className="text-gray-400 text-sm py-4 w-full text-center">
                All creatives are clustered. Drag here to unassign.
              </div>
            )}
          </div>
        </SortableContext>
      )}
    </div>
  );
}
