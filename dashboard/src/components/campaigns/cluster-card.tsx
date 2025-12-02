'use client';

import { useState, useRef, useEffect } from 'react';
import { useDroppable } from '@dnd-kit/core';
import { SortableContext, rectSortingStrategy } from '@dnd-kit/sortable';
import { Pencil, Trash2 } from 'lucide-react';
import { DraggableCreative } from './draggable-creative';
import { cn } from '@/lib/utils';

interface Campaign {
  id: string;
  name: string;
  creative_ids: string[];
}

interface Creative {
  id: string;
  format: string;
  performance?: {
    total_spend_micros?: number;
    total_impressions?: number;
  };
  waste_flags?: {
    broken_video?: boolean;
    zero_engagement?: boolean;
  };
}

interface ClusterCardProps {
  campaign: Campaign;
  creatives: Creative[];
  onRename: (id: string, name: string) => void;
  onDelete: (id: string) => void;
}

export function ClusterCard({ campaign, creatives, onRename, onDelete }: ClusterCardProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [name, setName] = useState(campaign.name);
  const inputRef = useRef<HTMLInputElement>(null);

  const { setNodeRef, isOver } = useDroppable({
    id: campaign.id,
  });

  useEffect(() => {
    if (isEditing) {
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }, [isEditing]);

  useEffect(() => {
    setName(campaign.name);
  }, [campaign.name]);

  const handleSave = () => {
    if (name.trim() && name !== campaign.name) {
      onRename(campaign.id, name.trim());
    } else {
      setName(campaign.name);
    }
    setIsEditing(false);
  };

  // Sort creatives by spend (highest first)
  const sortedCreatives = [...creatives].sort((a, b) => {
    const spendA = a.performance?.total_spend_micros || 0;
    const spendB = b.performance?.total_spend_micros || 0;
    return spendB - spendA;
  });

  // Calculate total spend
  const totalSpend = creatives.reduce(
    (sum, c) => sum + (c.performance?.total_spend_micros || 0),
    0
  );

  const formatTotalSpend = (micros: number): string => {
    const dollars = micros / 1_000_000;
    if (dollars >= 1000) return `$${(dollars / 1000).toFixed(1)}K`;
    if (dollars >= 1) return `$${dollars.toFixed(0)}`;
    return `$${dollars.toFixed(2)}`;
  };

  return (
    <div
      ref={setNodeRef}
      className={cn(
        "rounded-xl border-2 p-4 transition-colors",
        isOver ? "border-blue-500 bg-blue-50" : "border-gray-200 bg-white"
      )}
      style={{
        backgroundImage: `
          linear-gradient(to right, #f9fafb 1px, transparent 1px),
          linear-gradient(to bottom, #f9fafb 1px, transparent 1px)
        `,
        backgroundSize: '60px 60px',
      }}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        {isEditing ? (
          <input
            ref={inputRef}
            value={name}
            onChange={(e) => setName(e.target.value)}
            onBlur={handleSave}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSave();
              if (e.key === 'Escape') {
                setName(campaign.name);
                setIsEditing(false);
              }
            }}
            className="text-lg font-semibold w-full border-b-2 border-blue-500 outline-none bg-transparent"
          />
        ) : (
          <h3
            className="text-lg font-semibold flex items-center gap-2 cursor-pointer hover:text-blue-600 group"
            onDoubleClick={() => setIsEditing(true)}
          >
            {campaign.name}
            <Pencil className="h-4 w-4 opacity-0 group-hover:opacity-50 transition-opacity" />
          </h3>
        )}

        <button
          onClick={() => onDelete(campaign.id)}
          className="p-1 text-gray-400 hover:text-red-500 transition-colors"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </div>

      {/* Creative Grid */}
      <SortableContext items={sortedCreatives.map(c => c.id)} strategy={rectSortingStrategy}>
        <div
          className="grid gap-1 min-h-[120px]"
          style={{
            gridTemplateColumns: 'repeat(4, 56px)',
            gridAutoRows: '56px',
          }}
        >
          {sortedCreatives.map((creative, index) => (
            <DraggableCreative
              key={creative.id}
              creative={creative}
              clusterId={campaign.id}
              isLarge={index === 0 && sortedCreatives.length > 1}
            />
          ))}
        </div>
      </SortableContext>

      {/* Stats */}
      <div className="mt-3 text-sm text-gray-600 flex items-center gap-3">
        <span>{creatives.length} creative{creatives.length !== 1 ? 's' : ''}</span>
        {totalSpend > 0 && (
          <>
            <span>·</span>
            <span>{formatTotalSpend(totalSpend)}</span>
          </>
        )}
      </div>
    </div>
  );
}
