# Campaign Page UX Fixes

**Issues to fix:**
1. Dragging a creative moves the entire cluster instead of the creative
2. No metadata visible (need hover/click tooltip)
3. Need text view alternative to image grid

---

## Issue 1: Drag Moves Clusters Instead of Creatives

**Symptom:** Dragging an image from Cluster A to Cluster B causes the entire cluster blocks to swap positions, and the dragged image ends up in unclustered.

**Root Cause:** The cluster containers themselves are probably wrapped in a SortableContext or have drag listeners attached. When you drag, you're dragging the cluster, not the creative inside it.

**Architecture Problem:**

```
Current (broken):
SortableContext (clusters) ← WRONG: makes clusters draggable
  ClusterCard (sortable) ← Cluster itself is draggable
    DraggableCreative

Correct:
ClusterCard (droppable only, NOT sortable)
  SortableContext (creatives in this cluster)
    DraggableCreative (sortable)
```

### Fix: Clusters Should Be Droppable, NOT Sortable

**In `page.tsx`:**

```typescript
// REMOVE any SortableContext that wraps ClusterCards
// Clusters should NOT be in a SortableContext

// WRONG:
<SortableContext items={campaigns.map(c => c.id)}>
  {campaigns.map(campaign => (
    <ClusterCard ... />
  ))}
</SortableContext>

// CORRECT:
// No SortableContext here - clusters are just droppable targets
{campaigns.map(campaign => (
  <ClusterCard ... />
))}
```

**In `cluster-card.tsx`:**

```typescript
// Use useDroppable, NOT useSortable
import { useDroppable } from '@dnd-kit/core';
import { SortableContext, rectSortingStrategy } from '@dnd-kit/sortable';

function ClusterCard({ campaign, creatives, ... }: Props) {
  // Cluster is a DROP TARGET only
  const { setNodeRef, isOver } = useDroppable({
    id: campaign.id,
  });

  return (
    <div
      ref={setNodeRef}  // Makes this a drop target
      className={cn(
        "rounded-xl border-2 p-4",
        isOver && "border-blue-500 bg-blue-50"
      )}
    >
      <h3>{campaign.name}</h3>
      
      {/* Creatives inside ARE sortable */}
      <SortableContext 
        items={creatives.map(c => String(c.id))}
        strategy={rectSortingStrategy}
      >
        <div className="grid gap-1" style={{ gridTemplateColumns: 'repeat(4, 56px)' }}>
          {creatives.map(creative => (
            <DraggableCreative
              key={creative.id}
              creative={creative}
              clusterId={campaign.id}  // Track which cluster this creative is in
            />
          ))}
        </div>
      </SortableContext>
    </div>
  );
}
```

**In `draggable-creative.tsx`:**

```typescript
// Creative uses useSortable (it's both draggable and a drop target for reordering)
import { useSortable } from '@dnd-kit/sortable';

function DraggableCreative({ creative, clusterId, ... }: Props) {
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
      clusterId,   // So handleDragEnd knows where it came from
      creative,
      type: 'creative',  // Distinguish from cluster
    },
  });

  return (
    <div
      ref={setNodeRef}
      style={{
        transform: CSS.Transform.toString(transform),
        transition,
      }}
      {...attributes}
      {...listeners}
      className={cn("w-14 h-14 cursor-grab", isDragging && "opacity-40")}
    >
      {/* thumbnail */}
    </div>
  );
}
```

**In `handleDragEnd`:**

```typescript
function handleDragEnd(event: DragEndEvent) {
  const { active, over } = event;
  setActiveId(null);
  
  if (!over) return;
  
  // Ensure we're dragging a creative, not a cluster
  if (active.data.current?.type !== 'creative') return;
  
  const creativeId = active.id as string;
  const sourceClusterId = active.data.current?.clusterId as string;
  const targetClusterId = over.id as string;
  
  // Don't move if dropped on itself or same cluster
  if (creativeId === targetClusterId) return;
  if (sourceClusterId === targetClusterId) return;
  
  console.log(`Moving creative ${creativeId} from ${sourceClusterId} to ${targetClusterId}`);
  
  // ... API calls to move creative
}
```

---

## Issue 2: No Metadata Visible

Need to show creative details on hover or click.

### Option A: Hover Tooltip (Recommended)

Use a tooltip that appears on hover with creative metadata:

```typescript
import { useState } from 'react';

function DraggableCreative({ creative, clusterId, ... }: Props) {
  const [showTooltip, setShowTooltip] = useState(false);
  
  return (
    <div
      ref={setNodeRef}
      {...attributes}
      {...listeners}
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
      className="relative"
    >
      {/* Thumbnail */}
      <img src={getThumbnailUrl(creative)} ... />
      
      {/* Tooltip */}
      {showTooltip && (
        <div className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 
                        bg-gray-900 text-white text-xs rounded-lg p-3 
                        min-w-[200px] shadow-xl pointer-events-none">
          <div className="font-medium text-sm mb-2">#{creative.id}</div>
          
          <div className="space-y-1 text-gray-300">
            <div className="flex justify-between">
              <span>Spend:</span>
              <span className="text-white">{formatSpend(creative.performance?.total_spend_micros)}</span>
            </div>
            <div className="flex justify-between">
              <span>Impressions:</span>
              <span className="text-white">{formatNumber(creative.performance?.total_impressions)}</span>
            </div>
            <div className="flex justify-between">
              <span>Clicks:</span>
              <span className="text-white">{formatNumber(creative.performance?.total_clicks)}</span>
            </div>
            <div className="flex justify-between">
              <span>CTR:</span>
              <span className="text-white">{creative.performance?.ctr_percent?.toFixed(2)}%</span>
            </div>
          </div>
          
          {creative.final_url && (
            <div className="mt-2 pt-2 border-t border-gray-700">
              <div className="text-gray-400 text-[10px]">Destination:</div>
              <div className="text-blue-300 truncate">{creative.final_url}</div>
            </div>
          )}
          
          {/* Arrow */}
          <div className="absolute top-full left-1/2 -translate-x-1/2 
                          border-8 border-transparent border-t-gray-900" />
        </div>
      )}
    </div>
  );
}
```

### Option B: Click to Select + Side Panel

For more detailed view, click selects the creative and shows details in a side panel:

```typescript
// In page.tsx
const [selectedCreativeId, setSelectedCreativeId] = useState<string | null>(null);
const selectedCreative = selectedCreativeId 
  ? creativesMap.get(selectedCreativeId) 
  : null;

// In render
<div className="flex gap-4">
  <div className="flex-1">
    {/* Clusters grid */}
  </div>
  
  {selectedCreative && (
    <div className="w-80 border-l p-4 bg-gray-50">
      <CreativeDetailPanel 
        creative={selectedCreative}
        onClose={() => setSelectedCreativeId(null)}
      />
    </div>
  )}
</div>
```

---

## Issue 3: Text View Alternative

Add a toggle between image grid and text list view.

### View Toggle UI

```typescript
type ViewMode = 'grid' | 'list';

function CampaignsPage() {
  const [viewMode, setViewMode] = useState<ViewMode>('grid');
  
  return (
    <div>
      {/* View Toggle */}
      <div className="flex gap-2 mb-4">
        <button
          onClick={() => setViewMode('grid')}
          className={cn(
            "px-3 py-1.5 rounded-md flex items-center gap-2",
            viewMode === 'grid' 
              ? "bg-blue-600 text-white" 
              : "bg-gray-100 text-gray-600 hover:bg-gray-200"
          )}
        >
          <Grid className="h-4 w-4" />
          Grid
        </button>
        <button
          onClick={() => setViewMode('list')}
          className={cn(
            "px-3 py-1.5 rounded-md flex items-center gap-2",
            viewMode === 'list' 
              ? "bg-blue-600 text-white" 
              : "bg-gray-100 text-gray-600 hover:bg-gray-200"
          )}
        >
          <List className="h-4 w-4" />
          List
        </button>
      </div>
      
      {/* Content based on view mode */}
      {viewMode === 'grid' ? (
        <GridView campaigns={campaigns} ... />
      ) : (
        <ListView campaigns={campaigns} ... />
      )}
    </div>
  );
}
```

### List View Component

Based on dnd-kit MultipleContainers pattern:

```typescript
function ListView({ campaigns, creativesMap, unclusteredIds, ... }: Props) {
  return (
    <DndContext sensors={sensors} collisionDetection={pointerWithin} ...>
      <div className="flex gap-4 overflow-x-auto pb-4">
        {/* Each campaign as a scrollable column */}
        {campaigns.map(campaign => (
          <ListCluster
            key={campaign.id}
            campaign={campaign}
            creatives={campaign.creative_ids.map(id => creativesMap.get(String(id))).filter(Boolean)}
          />
        ))}
        
        {/* Unclustered column */}
        <ListCluster
          campaign={{ id: 'unassigned', name: 'Unclustered' }}
          creatives={unclusteredIds.map(id => creativesMap.get(String(id))).filter(Boolean)}
        />
      </div>
    </DndContext>
  );
}

function ListCluster({ campaign, creatives }: Props) {
  const { setNodeRef, isOver } = useDroppable({ id: campaign.id });
  
  return (
    <div
      ref={setNodeRef}
      className={cn(
        "w-80 flex-shrink-0 rounded-lg border bg-white",
        isOver && "border-blue-500"
      )}
      style={{ maxHeight: '80vh' }}
    >
      {/* Header */}
      <div className="p-3 border-b bg-gray-50 font-medium">
        {campaign.name}
        <span className="text-gray-400 ml-2">({creatives.length})</span>
      </div>
      
      {/* Scrollable list */}
      <div className="overflow-y-auto p-2" style={{ maxHeight: 'calc(80vh - 50px)' }}>
        <SortableContext items={creatives.map(c => String(c.id))}>
          {creatives.map(creative => (
            <ListItem key={creative.id} creative={creative} clusterId={campaign.id} />
          ))}
        </SortableContext>
      </div>
    </div>
  );
}

function ListItem({ creative, clusterId }: Props) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({
    id: String(creative.id),
    data: { clusterId, creative, type: 'creative' },
  });
  
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };
  
  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      className={cn(
        "p-2 mb-1 rounded border bg-white cursor-grab hover:bg-gray-50",
        isDragging && "opacity-40"
      )}
    >
      <div className="flex items-center gap-2">
        {/* Small thumbnail */}
        <img 
          src={getThumbnailUrl(creative)} 
          className="w-10 h-10 rounded object-cover flex-shrink-0"
          draggable={false}
        />
        
        {/* Text info */}
        <div className="min-w-0 flex-1">
          <div className="font-medium text-sm truncate">
            #{creative.id}
          </div>
          <div className="text-xs text-gray-500 truncate">
            {creative.final_url ? new URL(creative.final_url).hostname : 'No URL'}
          </div>
        </div>
        
        {/* Spend */}
        <div className="text-sm font-medium text-green-600 flex-shrink-0">
          {formatSpend(creative.performance?.total_spend_micros)}
        </div>
      </div>
    </div>
  );
}
```

---

## Complete Page Structure

```typescript
'use client';

import { useState } from 'react';
import { DndContext, DragOverlay, pointerWithin } from '@dnd-kit/core';
import { Grid, List } from 'lucide-react';

type ViewMode = 'grid' | 'list';

export default function CampaignsPage() {
  const [viewMode, setViewMode] = useState<ViewMode>('grid');
  const [activeId, setActiveId] = useState<string | null>(null);
  
  // ... data fetching, handlers ...
  
  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Campaigns</h1>
        
        <div className="flex items-center gap-4">
          {/* View Toggle */}
          <div className="flex gap-1 bg-gray-100 p-1 rounded-lg">
            <button
              onClick={() => setViewMode('grid')}
              className={cn(
                "p-2 rounded",
                viewMode === 'grid' ? "bg-white shadow-sm" : "text-gray-500"
              )}
            >
              <Grid className="h-4 w-4" />
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={cn(
                "p-2 rounded",
                viewMode === 'list' ? "bg-white shadow-sm" : "text-gray-500"
              )}
            >
              <List className="h-4 w-4" />
            </button>
          </div>
          
          {/* Action buttons */}
          <button onClick={handleAutoCluster}>Cluster by URL</button>
          <button onClick={handleCreateCampaign}>New Campaign</button>
        </div>
      </div>
      
      {/* Content */}
      <DndContext
        sensors={sensors}
        collisionDetection={pointerWithin}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
        onDragCancel={handleDragCancel}
      >
        {viewMode === 'grid' ? (
          <GridView
            campaigns={campaigns}
            creativesMap={creativesMap}
            unclusteredIds={unclusteredIds}
            onRename={handleRename}
            onDelete={handleDelete}
          />
        ) : (
          <ListView
            campaigns={campaigns}
            creativesMap={creativesMap}
            unclusteredIds={unclusteredIds}
          />
        )}
        
        <DragOverlay dropAnimation={null}>
          {activeId && creativesMap.get(activeId) && (
            viewMode === 'grid' ? (
              <DraggableCreative
                creative={creativesMap.get(activeId)!}
                clusterId=""
                isDragOverlay
              />
            ) : (
              <ListItem
                creative={creativesMap.get(activeId)!}
                clusterId=""
                isDragOverlay
              />
            )
          )}
        </DragOverlay>
      </DndContext>
    </div>
  );
}
```

---

## File Structure After Changes

```
dashboard/src/app/campaigns/
  page.tsx                    # Main page with view toggle

dashboard/src/components/campaigns/
  grid-view.tsx               # Grid view container
  list-view.tsx               # List view container
  cluster-card.tsx            # Grid cluster (droppable only)
  list-cluster.tsx            # List cluster (droppable only)
  draggable-creative.tsx      # Grid item (with hover tooltip)
  list-item.tsx               # List item (text-based)
  creative-tooltip.tsx        # Reusable tooltip component
```

---

## Testing Checklist

### Drag & Drop
- [ ] Dragging a creative from Cluster A to Cluster B moves only that creative
- [ ] Cluster boxes do NOT move/swap
- [ ] Creative ends up in target cluster, not unclustered
- [ ] Dragging to unclustered removes from cluster
- [ ] Dragging from unclustered to cluster adds it

### Hover Tooltip
- [ ] Hovering shows tooltip with metadata
- [ ] Tooltip shows: ID, Spend, Impressions, Clicks, CTR
- [ ] Tooltip shows destination URL
- [ ] Tooltip disappears on mouse leave
- [ ] Tooltip doesn't interfere with dragging

### View Toggle
- [ ] Toggle button switches between grid and list
- [ ] Grid view shows thumbnails
- [ ] List view shows text with small thumbnail
- [ ] Drag and drop works in both views
- [ ] State persists when switching views

---

## Report Back

After implementing:
1. Does dragging now move creatives (not clusters)?
2. Does the hover tooltip appear with correct data?
3. Does the view toggle work?
4. Can you drag items in list view?
