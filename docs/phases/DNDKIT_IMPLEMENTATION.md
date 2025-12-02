# Campaign Clustering: dnd-kit Implementation

**Goal:** Enhance the /campaigns page with full drag-and-drop using dnd-kit, featuring grid layout with large first tile, removable items, snap-to-grid, press delay, and editable labels.

---

## Install Dependencies

```bash
cd /home/jen/Documents/rtbcat-platform/dashboard
npm install @dnd-kit/core @dnd-kit/sortable @dnd-kit/utilities @dnd-kit/modifiers
```

---

## Feature Specifications

### 1. Grid Layout with "Large First Tile"

Each cluster displays creatives in a grid where the **highest-spend creative is 2x2** (large), others are 1x1.

```
╭────────────────────────────────╮
│  Campaign: AliExpress US   ✎  │
├────────────────────────────────┤
│  ┌──────────────┬──────┬──────┐│
│  │              │  🖼  │  🖼  ││
│  │   🖼 $1.2K   ├──────┼──────┤│  ← Large tile = highest spend
│  │   (large)   │  🖼  │  🖼  ││
│  └──────────────┴──────┴──────┘│
│  8 creatives · $4.2K total     │
╰────────────────────────────────╯
```

**CSS Grid Setup:**
```css
.cluster-grid {
  display: grid;
  grid-template-columns: repeat(4, 56px);
  grid-template-rows: repeat(auto-fill, 56px);
  gap: 4px;
  background-image: 
    linear-gradient(to right, #e5e7eb 1px, transparent 1px),
    linear-gradient(to bottom, #e5e7eb 1px, transparent 1px);
  background-size: 60px 60px;  /* Grid lines */
  padding: 8px;
}

.large-tile {
  grid-column: span 2;
  grid-row: span 2;
}
```

### 2. Grid Background

Each cluster has a subtle grid background to reinforce the "snap" feel:

```tsx
<div 
  className="rounded-xl border-2 border-gray-200 bg-white p-4"
  style={{
    backgroundImage: `
      linear-gradient(to right, #f3f4f6 1px, transparent 1px),
      linear-gradient(to bottom, #f3f4f6 1px, transparent 1px)
    `,
    backgroundSize: '60px 60px',
  }}
>
  {/* Cluster content */}
</div>
```

### 3. Removable Items → Unassigned Grid

When a creative is removed from a cluster (dragged out or X button), it goes to the "Unassigned" section.

```tsx
// Handle drop outside any cluster = move to unassigned
function handleDragEnd(event: DragEndEvent) {
  const { active, over } = event;
  
  if (!over) {
    // Dropped outside - do nothing or show toast
    return;
  }
  
  if (over.id === 'unassigned') {
    // Remove from current cluster, add to unassigned
    await removeFromCluster(active.id);
  } else if (over.id !== active.data.current?.clusterId) {
    // Move to different cluster
    await moveToCluster(active.id, over.id);
  }
}
```

### 4. Snap to Grid

Use `@dnd-kit/modifiers` for snap-to-grid behavior:

```tsx
import { snapCenterToCursor, createSnapModifier } from '@dnd-kit/modifiers';

// Create 60px snap grid
const snapToGrid = createSnapModifier(60);

// In DndContext
<DndContext
  modifiers={[snapToGrid]}
  // ...
>
```

### 5. Press Delay with Visual Cue

Prevent accidental drags with a 250ms hold requirement + visual feedback:

```tsx
import { MouseSensor, TouchSensor, useSensor, useSensors } from '@dnd-kit/core';

const mouseSensor = useSensor(MouseSensor, {
  activationConstraint: {
    delay: 250,        // 250ms hold to start drag
    tolerance: 5,      // 5px movement allowed during delay
  },
});

const touchSensor = useSensor(TouchSensor, {
  activationConstraint: {
    delay: 250,
    tolerance: 5,
  },
});

const sensors = useSensors(mouseSensor, touchSensor);

// In DndContext
<DndContext sensors={sensors} ...>
```

**Visual cue during delay:**

```tsx
// In the draggable item
function DraggableCreative({ creative, clusterId }: Props) {
  const { 
    attributes, 
    listeners, 
    setNodeRef, 
    transform,
    isDragging,
    active,  // The currently active (being dragged) item
  } = useSortable({ 
    id: creative.id,
    data: { clusterId, creative },
  });
  
  // Detect "pressing" state (holding but not yet dragging)
  const [isPressing, setIsPressing] = useState(false);
  
  const handlePointerDown = () => {
    setIsPressing(true);
    // Visual cue: scale up slightly, add ring
  };
  
  const handlePointerUp = () => {
    setIsPressing(false);
  };
  
  return (
    <div
      ref={setNodeRef}
      {...attributes}
      {...listeners}
      onPointerDown={handlePointerDown}
      onPointerUp={handlePointerUp}
      onPointerCancel={handlePointerUp}
      className={cn(
        "relative rounded-md overflow-hidden border cursor-grab transition-all duration-150",
        isPressing && !isDragging && "ring-2 ring-blue-400 scale-105",  // Press cue
        isDragging && "opacity-50 ring-2 ring-blue-500 scale-110",      // Dragging
      )}
      style={{
        transform: transform ? `translate(${transform.x}px, ${transform.y}px)` : undefined,
      }}
    >
      {/* Thumbnail content */}
    </div>
  );
}
```

### 6. Editable Labels (Cluster Names + Creative Notes)

**Cluster name editing (double-click):**

```tsx
function ClusterCard({ campaign, onRename }: Props) {
  const [isEditing, setIsEditing] = useState(false);
  const [name, setName] = useState(campaign.name);
  const inputRef = useRef<HTMLInputElement>(null);
  
  useEffect(() => {
    if (isEditing) {
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }, [isEditing]);
  
  const handleSave = () => {
    if (name.trim() && name !== campaign.name) {
      onRename(campaign.id, name.trim());
    }
    setIsEditing(false);
  };
  
  return (
    <div className="...">
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
          <Pencil className="h-4 w-4 opacity-0 group-hover:opacity-50" />
        </h3>
      )}
    </div>
  );
}
```

**Creative label (tooltip or small input):**

For individual creatives, you might want a small label/note. Since space is limited on mini tiles, use a tooltip on hover or a modal on click:

```tsx
function DraggableCreative({ creative, onUpdateLabel }: Props) {
  const [showTooltip, setShowTooltip] = useState(false);
  const [label, setLabel] = useState(creative.label || '');
  
  return (
    <div 
      className="relative"
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      {/* Thumbnail */}
      <div className="w-14 h-14 ...">
        <img src={getThumbnail(creative)} ... />
      </div>
      
      {/* Tooltip with editable label */}
      {showTooltip && (
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 bg-gray-900 text-white text-xs rounded px-2 py-1 whitespace-nowrap z-50">
          <div>#{creative.id}</div>
          <div>{formatSpend(creative.performance?.total_spend_micros)}</div>
          <input 
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            onBlur={() => onUpdateLabel(creative.id, label)}
            placeholder="Add label..."
            className="bg-gray-800 border border-gray-700 rounded px-1 mt-1 w-24"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </div>
  );
}
```

---

## Complete Component Structure

```
dashboard/src/app/campaigns/
  page.tsx                    # Main page with DndContext

dashboard/src/components/campaigns/
  cluster-card.tsx            # Individual cluster with grid
  draggable-creative.tsx      # Draggable mini thumbnail
  unassigned-pool.tsx         # Unassigned creatives section  
  new-cluster-button.tsx      # "+ New Campaign" dashed button
  cluster-grid.tsx            # The grid layout within a cluster
```

---

## Full Implementation: page.tsx

```tsx
'use client';

import { useState, useEffect } from 'react';
import {
  DndContext,
  DragOverlay,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragStartEvent,
  DragEndEvent,
} from '@dnd-kit/core';
import { createSnapModifier } from '@dnd-kit/modifiers';
import { arrayMove } from '@dnd-kit/sortable';
import { ClusterCard } from '@/components/campaigns/cluster-card';
import { UnassignedPool } from '@/components/campaigns/unassigned-pool';
import { DraggableCreative } from '@/components/campaigns/draggable-creative';

interface Campaign {
  id: string;
  name: string;
  creative_ids: string[];
}

interface Creative {
  id: string;
  format: string;
  // ... other fields
}

export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [creatives, setCreatives] = useState<Map<string, Creative>>(new Map());
  const [unassignedIds, setUnassignedIds] = useState<string[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Sensors with press delay
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        delay: 250,
        tolerance: 5,
      },
    }),
    useSensor(KeyboardSensor)
  );

  // Snap to 60px grid
  const snapToGrid = createSnapModifier(60);

  // Load data
  useEffect(() => {
    async function loadData() {
      const [campaignsRes, creativesRes, unassignedRes] = await Promise.all([
        fetch('/api/campaigns'),
        fetch('/api/creatives?limit=1000'),
        fetch('/api/campaigns/unclustered'),
      ]);
      
      const campaignsData = await campaignsRes.json();
      const creativesData = await creativesRes.json();
      const unassignedData = await unassignedRes.json();
      
      setCampaigns(campaignsData);
      setUnassignedIds(unassignedData.creative_ids || []);
      
      // Build creative map for quick lookup
      const map = new Map();
      creativesData.creatives?.forEach((c: Creative) => map.set(c.id, c));
      setCreatives(map);
      
      setIsLoading(false);
    }
    loadData();
  }, []);

  // Drag handlers
  function handleDragStart(event: DragStartEvent) {
    setActiveId(event.active.id as string);
  }

  async function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    setActiveId(null);

    if (!over) return;

    const creativeId = active.id as string;
    const sourceClusterId = active.data.current?.clusterId;
    const targetClusterId = over.id as string;

    // No change
    if (sourceClusterId === targetClusterId) return;

    // Move to unassigned
    if (targetClusterId === 'unassigned') {
      await fetch(`/api/campaigns/${sourceClusterId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          remove_creative_ids: [creativeId],
        }),
      });
      
      // Update local state
      setCampaigns(prev => prev.map(c => 
        c.id === sourceClusterId 
          ? { ...c, creative_ids: c.creative_ids.filter(id => id !== creativeId) }
          : c
      ));
      setUnassignedIds(prev => [...prev, creativeId]);
      return;
    }

    // Move from unassigned to cluster
    if (sourceClusterId === 'unassigned') {
      await fetch(`/api/campaigns/${targetClusterId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          add_creative_ids: [creativeId],
        }),
      });
      
      setCampaigns(prev => prev.map(c =>
        c.id === targetClusterId
          ? { ...c, creative_ids: [...c.creative_ids, creativeId] }
          : c
      ));
      setUnassignedIds(prev => prev.filter(id => id !== creativeId));
      return;
    }

    // Move between clusters
    await fetch(`/api/campaigns/${sourceClusterId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        remove_creative_ids: [creativeId],
      }),
    });
    
    await fetch(`/api/campaigns/${targetClusterId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        add_creative_ids: [creativeId],
      }),
    });

    setCampaigns(prev => prev.map(c => {
      if (c.id === sourceClusterId) {
        return { ...c, creative_ids: c.creative_ids.filter(id => id !== creativeId) };
      }
      if (c.id === targetClusterId) {
        return { ...c, creative_ids: [...c.creative_ids, creativeId] };
      }
      return c;
    }));
  }

  // Rename cluster
  async function handleRename(campaignId: string, newName: string) {
    await fetch(`/api/campaigns/${campaignId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: newName }),
    });
    
    setCampaigns(prev => prev.map(c =>
      c.id === campaignId ? { ...c, name: newName } : c
    ));
  }

  // Create new cluster
  async function handleCreateCluster() {
    const res = await fetch('/api/campaigns', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: 'New Campaign', creative_ids: [] }),
    });
    const newCampaign = await res.json();
    setCampaigns(prev => [...prev, newCampaign]);
  }

  // Delete cluster
  async function handleDeleteCluster(campaignId: string) {
    const campaign = campaigns.find(c => c.id === campaignId);
    if (!campaign) return;
    
    await fetch(`/api/campaigns/${campaignId}`, { method: 'DELETE' });
    
    // Move creatives back to unassigned
    setUnassignedIds(prev => [...prev, ...campaign.creative_ids]);
    setCampaigns(prev => prev.filter(c => c.id !== campaignId));
  }

  // Auto-cluster by URL
  async function handleAutoCluster() {
    const res = await fetch('/api/campaigns/auto-cluster', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ by_url: true }),
    });
    const suggestions = await res.json();
    // Show suggestions UI or auto-apply
    // For now, reload campaigns
    window.location.reload();
  }

  // Get the creative being dragged (for DragOverlay)
  const activeCreative = activeId ? creatives.get(activeId) : null;

  if (isLoading) {
    return <div className="p-8">Loading campaigns...</div>;
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Campaigns</h1>
        <div className="flex gap-2">
          <button
            onClick={handleAutoCluster}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Cluster by URL
          </button>
          <button
            onClick={handleCreateCluster}
            className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
          >
            + New Campaign
          </button>
        </div>
      </div>

      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        modifiers={[snapToGrid]}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
      >
        {/* Clusters Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
          {campaigns.map(campaign => (
            <ClusterCard
              key={campaign.id}
              campaign={campaign}
              creatives={campaign.creative_ids.map(id => creatives.get(id)).filter(Boolean) as Creative[]}
              onRename={handleRename}
              onDelete={handleDeleteCluster}
            />
          ))}
          
          {/* New Campaign Button */}
          <button
            onClick={handleCreateCluster}
            className="min-h-[200px] rounded-xl border-2 border-dashed border-gray-300 flex flex-col items-center justify-center gap-2 text-gray-400 hover:border-blue-400 hover:text-blue-500 transition-colors"
          >
            <span className="text-4xl">+</span>
            <span>New Campaign</span>
          </button>
        </div>

        {/* Unassigned Pool */}
        <UnassignedPool
          creativeIds={unassignedIds}
          creatives={creatives}
        />

        {/* Drag Overlay */}
        <DragOverlay>
          {activeCreative ? (
            <DraggableCreative
              creative={activeCreative}
              clusterId=""
              isDragOverlay
            />
          ) : null}
        </DragOverlay>
      </DndContext>
    </div>
  );
}
```

---

## ClusterCard Component

```tsx
// components/campaigns/cluster-card.tsx
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
              isLarge={index === 0 && sortedCreatives.length > 1}  // First = large if multiple
            />
          ))}
        </div>
      </SortableContext>

      {/* Stats */}
      <div className="mt-3 text-sm text-gray-600 flex items-center gap-3">
        <span>{creatives.length} creative{creatives.length !== 1 ? 's' : ''}</span>
        <span>·</span>
        <span>${(totalSpend / 1_000_000).toFixed(totalSpend > 1_000_000 ? 1 : 2)}K</span>
      </div>
    </div>
  );
}
```

---

## DraggableCreative Component

```tsx
// components/campaigns/draggable-creative.tsx
'use client';

import { useState } from 'react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { cn } from '@/lib/utils';

interface Creative {
  id: string;
  format: string;
  video?: { thumbnail_url?: string };
  native?: { logo?: string; image?: string };
  performance?: { total_spend_micros?: number };
}

interface DraggableCreativeProps {
  creative: Creative;
  clusterId: string;
  isLarge?: boolean;
  isDragOverlay?: boolean;
}

function getThumbnail(creative: Creative): string | null {
  if (creative.format === 'VIDEO') {
    return creative.video?.thumbnail_url || `/api/thumbnails/${creative.id}.jpg`;
  }
  if (creative.format === 'NATIVE') {
    return creative.native?.logo || creative.native?.image || null;
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
        />
      ) : (
        <div className="w-full h-full flex items-center justify-center text-gray-400 text-xs">
          {creative.format}
        </div>
      )}
      
      {/* Spend badge */}
      {creative.performance?.total_spend_micros && (
        <div className={cn(
          "absolute bottom-0 inset-x-0 bg-black/70 text-white text-center",
          isLarge ? "text-xs py-1" : "text-[9px] py-0.5"
        )}>
          {formatSpend(creative.performance.total_spend_micros)}
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
```

---

## UnassignedPool Component

```tsx
// components/campaigns/unassigned-pool.tsx
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
}

interface UnassignedPoolProps {
  creativeIds: string[];
  creatives: Map<string, Creative>;
}

export function UnassignedPool({ creativeIds, creatives }: UnassignedPoolProps) {
  const [isExpanded, setIsExpanded] = useState(true);
  
  const { setNodeRef, isOver } = useDroppable({
    id: 'unassigned',
  });

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
        <SortableContext items={creativeIds} strategy={rectSortingStrategy}>
          <div
            className="mt-4 flex flex-wrap gap-1 min-h-[60px]"
          >
            {unassignedCreatives.map(creative => (
              <DraggableCreative
                key={creative.id}
                creative={creative}
                clusterId="unassigned"
              />
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
```

---

## Backend Updates Needed

### PATCH /campaigns/:id should support add/remove:

```python
# In api/main.py

class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    creative_ids: Optional[List[str]] = None  # Replace all
    add_creative_ids: Optional[List[str]] = None  # Add to existing
    remove_creative_ids: Optional[List[str]] = None  # Remove from existing

@app.patch("/campaigns/{campaign_id}")
async def update_campaign(campaign_id: str, update: CampaignUpdate):
    campaign = await store.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    
    current_ids = set(campaign.get('creative_ids', []))
    
    if update.creative_ids is not None:
        # Replace all
        current_ids = set(update.creative_ids)
    else:
        # Add/remove
        if update.add_creative_ids:
            current_ids.update(update.add_creative_ids)
        if update.remove_creative_ids:
            current_ids -= set(update.remove_creative_ids)
    
    new_name = update.name if update.name else campaign['name']
    
    await store.update_campaign(campaign_id, new_name, list(current_ids))
    return await store.get_campaign(campaign_id)
```

---

## Testing Checklist

1. [ ] dnd-kit packages installed
2. [ ] Clusters display with grid background
3. [ ] Highest-spend creative is large (2x2) in each cluster
4. [ ] Can drag creative from cluster to cluster
5. [ ] Can drag creative to unassigned pool
6. [ ] Can drag creative from unassigned to cluster
7. [ ] Press delay works (250ms hold to start drag)
8. [ ] Visual cue appears during press (ring + scale)
9. [ ] Snap to grid works during drag
10. [ ] Double-click cluster name to edit
11. [ ] Rename saves to backend
12. [ ] Delete cluster moves creatives to unassigned
13. [ ] "+ New Campaign" creates empty cluster
14. [ ] "Cluster by URL" button works

---

## Report Back

After implementation, provide:
1. npm install output (any peer dependency issues?)
2. Screenshot of clusters with thumbnails
3. Does press delay feel right? (250ms might need tuning)
4. Any TypeScript errors?
5. Backend PATCH endpoint working for add/remove?
