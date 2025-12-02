# Step 4-7: Frontend Interactivity for Campaigns Page

**Current State:**
- ✅ Campaigns display with thumbnails
- ✅ "Cluster by URL" works
- ❌ "New Campaign" button doesn't work
- ❌ No drag and drop
- ❌ Cluster names not editable
- ❌ Cards show IDs only, no spend/state indicators

**Goal:** Full interactivity with dnd-kit

---

## Issue 1: New Campaign Button Not Working

**File:** `dashboard/src/app/campaigns/page.tsx`

The "New Campaign" button needs an onClick handler that:
1. Calls `POST /api/campaigns` with a default name
2. Adds the new campaign to local state
3. Optionally opens the name for editing immediately

```typescript
async function handleCreateCampaign() {
  try {
    const res = await fetch('/api/campaigns', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        name: 'New Campaign', 
        creative_ids: [] 
      }),
    });
    
    if (!res.ok) throw new Error('Failed to create campaign');
    
    const newCampaign = await res.json();
    setCampaigns(prev => [...prev, newCampaign]);
    
    // Optionally: set this campaign to "editing" mode for immediate rename
    setEditingCampaignId(newCampaign.id);
  } catch (error) {
    console.error('Failed to create campaign:', error);
  }
}
```

Make sure the button calls this:
```tsx
<button onClick={handleCreateCampaign}>
  New Campaign
</button>
```

---

## Issue 2: dnd-kit Not Wired Up

The dnd-kit packages are installed but need to be integrated into the page.

### 2.1 Import dnd-kit

```typescript
import {
  DndContext,
  DragOverlay,
  closestCenter,
  PointerSensor,
  useSensor,
  useSensors,
  DragStartEvent,
  DragEndEvent,
} from '@dnd-kit/core';
import { SortableContext, useSortable, rectSortingStrategy } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { createSnapModifier } from '@dnd-kit/modifiers';
```

### 2.2 Set Up Sensors (Press Delay)

```typescript
// At component level, not inside render
const sensors = useSensors(
  useSensor(PointerSensor, {
    activationConstraint: {
      delay: 250,  // 250ms hold before drag starts
      tolerance: 5, // 5px movement tolerance during delay
    },
  })
);

const snapToGrid = createSnapModifier(60);
```

### 2.3 Track Active Drag Item

```typescript
const [activeId, setActiveId] = useState<string | null>(null);
const [activeCreative, setActiveCreative] = useState<Creative | null>(null);

function handleDragStart(event: DragStartEvent) {
  const id = event.active.id as string;
  setActiveId(id);
  // Find the creative in our data
  const creative = allCreativesMap.get(id);
  setActiveCreative(creative || null);
}

function handleDragEnd(event: DragEndEvent) {
  setActiveId(null);
  setActiveCreative(null);
  
  const { active, over } = event;
  if (!over) return;
  
  const creativeId = active.id as string;
  const sourceClusterId = active.data.current?.clusterId as string;
  const targetClusterId = over.id as string;
  
  if (sourceClusterId === targetClusterId) return;
  
  // Call API to move creative
  moveCreative(creativeId, sourceClusterId, targetClusterId);
}
```

### 2.4 Move Creative Function

```typescript
async function moveCreative(creativeId: string, fromCluster: string, toCluster: string) {
  try {
    // Remove from source (if not unassigned)
    if (fromCluster && fromCluster !== 'unassigned') {
      await fetch(`/api/campaigns/${fromCluster}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ remove_creative_ids: [creativeId] }),
      });
    }
    
    // Add to target (if not unassigned)
    if (toCluster && toCluster !== 'unassigned') {
      await fetch(`/api/campaigns/${toCluster}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ add_creative_ids: [creativeId] }),
      });
    }
    
    // Update local state
    setCampaigns(prev => prev.map(c => {
      if (c.id === fromCluster) {
        return { ...c, creative_ids: c.creative_ids.filter(id => id !== creativeId) };
      }
      if (c.id === toCluster) {
        return { ...c, creative_ids: [...c.creative_ids, creativeId] };
      }
      return c;
    }));
    
    // Update unclustered list
    if (fromCluster === 'unassigned') {
      setUnclusteredIds(prev => prev.filter(id => id !== creativeId));
    }
    if (toCluster === 'unassigned') {
      setUnclusteredIds(prev => [...prev, creativeId]);
    }
    
  } catch (error) {
    console.error('Failed to move creative:', error);
    // Optionally: reload data to sync state
  }
}
```

### 2.5 Wrap Page in DndContext

```tsx
return (
  <DndContext
    sensors={sensors}
    collisionDetection={closestCenter}
    modifiers={[snapToGrid]}
    onDragStart={handleDragStart}
    onDragEnd={handleDragEnd}
  >
    {/* Page content: clusters, unclustered pool */}
    
    {/* Drag overlay - shows the item being dragged */}
    <DragOverlay>
      {activeCreative && (
        <div className="w-14 h-14 rounded-md overflow-hidden border-2 border-blue-500 shadow-lg">
          <img 
            src={getThumbnailUrl(activeCreative)} 
            className="w-full h-full object-cover"
          />
        </div>
      )}
    </DragOverlay>
  </DndContext>
);
```

### 2.6 Make Clusters Droppable

Each cluster card needs to be a drop target:

```typescript
import { useDroppable } from '@dnd-kit/core';

function ClusterCard({ campaign, creatives, ... }: Props) {
  const { setNodeRef, isOver } = useDroppable({
    id: campaign.id,
  });
  
  return (
    <div 
      ref={setNodeRef}
      className={cn(
        "rounded-xl border-2 p-4",
        isOver ? "border-blue-500 bg-blue-50" : "border-gray-200"
      )}
    >
      {/* Cluster content */}
    </div>
  );
}
```

### 2.7 Make Creatives Draggable

Each creative thumbnail needs to be draggable:

```typescript
function DraggableCreative({ creative, clusterId }: Props) {
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
  
  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      className={cn(
        "w-14 h-14 rounded-md overflow-hidden border cursor-grab",
        isDragging && "opacity-30"
      )}
    >
      <img src={getThumbnailUrl(creative)} className="w-full h-full object-cover" />
      {/* Spend badge if applicable */}
    </div>
  );
}
```

### 2.8 Unassigned Pool as Drop Target

```typescript
function UnassignedPool({ creativeIds, creativesMap }: Props) {
  const { setNodeRef, isOver } = useDroppable({
    id: 'unassigned',
  });
  
  return (
    <div
      ref={setNodeRef}
      className={cn(
        "rounded-xl border-2 p-4",
        isOver ? "border-blue-500 bg-blue-50" : "border-gray-200"
      )}
    >
      <SortableContext items={creativeIds} strategy={rectSortingStrategy}>
        <div className="flex flex-wrap gap-1">
          {creativeIds.map(id => {
            const creative = creativesMap.get(id);
            if (!creative) return null;
            return (
              <DraggableCreative 
                key={id} 
                creative={creative} 
                clusterId="unassigned" 
              />
            );
          })}
        </div>
      </SortableContext>
    </div>
  );
}
```

---

## Issue 3: Editable Cluster Names

Each cluster needs double-click to edit name:

```typescript
function EditableClusterName({ campaign, onRename }: Props) {
  const [isEditing, setIsEditing] = useState(false);
  const [name, setName] = useState(campaign.name);
  const inputRef = useRef<HTMLInputElement>(null);
  
  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);
  
  const handleSave = async () => {
    if (name.trim() && name !== campaign.name) {
      await onRename(campaign.id, name.trim());
    } else {
      setName(campaign.name);
    }
    setIsEditing(false);
  };
  
  if (isEditing) {
    return (
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
        className="text-lg font-semibold border-b-2 border-blue-500 outline-none bg-transparent w-full"
      />
    );
  }
  
  return (
    <h3 
      onDoubleClick={() => setIsEditing(true)}
      className="text-lg font-semibold cursor-pointer hover:text-blue-600 flex items-center gap-2 group"
    >
      {campaign.name}
      <Pencil className="h-4 w-4 opacity-0 group-hover:opacity-40 transition-opacity" />
    </h3>
  );
}
```

Rename API call:

```typescript
async function handleRenameCampaign(campaignId: string, newName: string) {
  try {
    await fetch(`/api/campaigns/${campaignId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: newName }),
    });
    
    setCampaigns(prev => prev.map(c => 
      c.id === campaignId ? { ...c, name: newName } : c
    ));
  } catch (error) {
    console.error('Failed to rename campaign:', error);
  }
}
```

---

## Issue 4: Card Visual States

Cards should show:
- Thumbnail (already working)
- Spend badge at bottom
- Greyed out if 0 spend
- Warning badge if broken video

```typescript
function DraggableCreative({ creative, clusterId, isLarge }: Props) {
  const spend = creative.performance?.total_spend_micros || 0;
  const isBrokenVideo = creative.waste_flags?.broken_video;
  const hasActivity = spend > 0 || 
    (creative.performance?.total_impressions || 0) > 0;
  
  // ... useSortable hook ...
  
  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      className={cn(
        "relative rounded-md overflow-hidden border cursor-grab",
        isLarge ? "col-span-2 row-span-2" : "w-14 h-14",
        spend === 0 && "opacity-50",  // Grey out if no spend
        isDragging && "opacity-30",
      )}
    >
      {/* Thumbnail */}
      <img 
        src={getThumbnailUrl(creative)} 
        className="w-full h-full object-cover"
        draggable={false}
      />
      
      {/* Warning badge for broken videos */}
      {isBrokenVideo && (
        <div className="absolute top-0.5 right-0.5 bg-red-500 text-white rounded-full p-0.5">
          <AlertTriangle className="h-2.5 w-2.5" />
        </div>
      )}
      
      {/* Spend badge */}
      {spend > 0 && (
        <div className="absolute bottom-0 inset-x-0 bg-black/70 text-white text-center text-[9px] py-0.5">
          {formatSpend(spend)}
        </div>
      )}
    </div>
  );
}

function formatSpend(micros: number): string {
  const dollars = micros / 1_000_000;
  if (dollars >= 1000) return `$${(dollars / 1000).toFixed(1)}K`;
  if (dollars >= 1) return `$${dollars.toFixed(0)}`;
  return `$${dollars.toFixed(2)}`;
}

function getThumbnailUrl(creative: Creative): string {
  if (creative.format === 'VIDEO') {
    return creative.video?.thumbnail_url || `/api/thumbnails/${creative.id}.jpg`;
  }
  if (creative.format === 'NATIVE') {
    return creative.native?.logo || creative.native?.image || '/placeholder.svg';
  }
  return '/placeholder.svg';
}
```

---

## Issue 5: Large First Tile

In each cluster, the highest-spend creative should be 2x2:

```typescript
function ClusterGrid({ creatives }: { creatives: Creative[] }) {
  // Sort by spend descending
  const sorted = [...creatives].sort((a, b) => {
    const spendA = a.performance?.total_spend_micros || 0;
    const spendB = b.performance?.total_spend_micros || 0;
    return spendB - spendA;
  });
  
  return (
    <div 
      className="grid gap-1"
      style={{
        gridTemplateColumns: 'repeat(4, 56px)',
        gridAutoRows: '56px',
      }}
    >
      {sorted.map((creative, index) => (
        <DraggableCreative
          key={creative.id}
          creative={creative}
          clusterId={campaign.id}
          isLarge={index === 0 && sorted.length > 1}  // First is large if multiple
        />
      ))}
    </div>
  );
}
```

---

## Testing Checklist

After implementation, verify:

1. [ ] "New Campaign" button creates empty campaign
2. [ ] New campaign appears in UI immediately
3. [ ] Can drag creative from unclustered to cluster
4. [ ] Can drag creative from cluster to cluster
5. [ ] Can drag creative from cluster to unclustered
6. [ ] 250ms press delay before drag starts
7. [ ] Visual feedback during drag (opacity, shadow)
8. [ ] Drop zones highlight when dragging over
9. [ ] Double-click cluster name to edit
10. [ ] Enter saves name, Escape cancels
11. [ ] Pencil icon appears on hover
12. [ ] Cards show spend badge
13. [ ] Cards with 0 spend are greyed out
14. [ ] Broken video cards show warning badge
15. [ ] Largest spend creative is 2x2 in cluster

---

## Debugging Tips

If drag and drop isn't working:

1. **Check DndContext wraps everything:** Both clusters and unclustered pool must be inside DndContext

2. **Check ref is attached:** Make sure `setNodeRef` from useDroppable/useSortable is passed to the element

3. **Check IDs match:** The `id` passed to useSortable must match what's in the items array

4. **Check data is passed:** `data: { clusterId, creative }` must be passed to useSortable for handleDragEnd to know the source

5. **Check sensors:** Make sure useSensors is called at component level (not inside render)

6. **Console log events:**
   ```typescript
   function handleDragEnd(event: DragEndEvent) {
     console.log('Drag end:', {
       activeId: event.active.id,
       overId: event.over?.id,
       sourceCluster: event.active.data.current?.clusterId,
     });
   }
   ```

---

## Report Back

After implementation, confirm:
1. All checkboxes above pass
2. Screenshot of drag in progress
3. Any issues encountered
4. API calls working (check Network tab)
