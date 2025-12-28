# dnd-kit Implementation Report

**Date:** 2025-12-02
**Component:** Campaigns Page - Creative Drag & Drop
**Files Modified:**
- `dashboard/src/app/campaigns/page.tsx`
- `dashboard/src/components/campaigns/draggable-creative.tsx`
- `dashboard/src/components/campaigns/cluster-card.tsx`
- `dashboard/src/components/campaigns/unassigned-pool.tsx`

---

## Overview

The campaigns page allows users to organize creatives into campaign clusters using drag-and-drop. Users can:
- Drag creatives between clusters
- Drag creatives from clusters to an "unclustered" pool
- Drag creatives from unclustered to clusters
- Click creatives to view metadata

---

## dnd-kit Architecture

### Core Concepts Used

1. **DndContext** - Wraps the entire drag area, manages drag state
2. **useSortable** - Makes items draggable (used in DraggableCreative)
3. **useDroppable** - Makes areas accept drops (used in ClusterCard, UnassignedPool)
4. **DragOverlay** - Shows the item being dragged as a floating element
5. **SortableContext** - Groups sortable items together

### Component Hierarchy

```
DndContext (campaigns/page.tsx)
├── ClusterCard (droppable)
│   └── SortableContext
│       └── DraggableCreative (sortable)
├── UnassignedPool (droppable, id="unassigned")
│   └── SortableContext
│       └── DraggableCreative (sortable)
└── DragOverlay
    └── DraggableCreative (isDragOverlay=true)
```

---

## Issues Encountered & Fixes

### Issue 1: Click-to-Remove Bug (First Attempt)

**Symptom:** Clicking on a creative caused it to leave its cluster and move to "unclustered".

**Root Cause:** The `closestCenter` collision detection algorithm finds the closest droppable center even when the pointer isn't over any droppable. A slight mouse movement during a click could trigger a drag that "snapped" to a nearby target.

**Initial Fix Attempt:** Added distance activation constraint:

```typescript
const sensors = useSensors(
  useSensor(PointerSensor, {
    activationConstraint: {
      distance: 8,  // Must move 8px before drag activates
    },
  })
);
```

**Result:** Partially helped but didn't fully solve the issue.

---

### Issue 2: Click-to-Remove Bug (Final Fix)

**Better Solution:** Changed collision detection from `closestCenter` to `pointerWithin`:

```typescript
// Before (problematic)
import { closestCenter } from '@dnd-kit/core';
<DndContext collisionDetection={closestCenter} ... >

// After (fixed)
import { pointerWithin } from '@dnd-kit/core';
<DndContext collisionDetection={pointerWithin} ... >
```

**Why this works:**
- `closestCenter`: Always finds the nearest droppable, even if pointer is far away
- `pointerWithin`: Only detects a target if pointer is actually inside its bounds

**Additional validation in handleDragEnd:**

```typescript
async function handleDragEnd(event: DragEndEvent) {
  const { active, over } = event;
  setActiveId(null);

  // No target - drop cancelled
  if (!over) return;

  const creativeId = active.id as string;
  const sourceClusterId = active.data.current?.clusterId as string;
  const targetClusterId = over.id as string;

  // Same cluster - no action
  if (sourceClusterId === targetClusterId) return;
  if (active.id === over.id) return;

  // Only move if target is a valid cluster or "unassigned"
  const isValidTarget = targetClusterId === 'unassigned' ||
    campaigns.some(c => c.id === targetClusterId);
  if (!isValidTarget) return;

  // ... proceed with move
}
```

---

### Issue 3: All Creatives Greyed Out

**Symptom:** All creative thumbnails appeared with 50% opacity.

**Root Cause:** CSS class `!hasActivity && "opacity-50"` was applied, but no creatives had performance data loaded.

**Fix:** Removed the opacity effect entirely since it wasn't the desired behavior.

---

### Issue 4: Jerky Dragging

**Symptom:** Dragging felt janky and items would "snap" to positions.

**Root Cause:** A 60px snap-to-grid modifier was enabled:

```typescript
const snapToGrid = createSnapModifier(60);
<DndContext modifiers={[snapToGrid]} ... >
```

**Fix:** Removed the snap modifier for smoother dragging.

---

### Issue 5: ID Type Mismatches

**Symptom:** Creatives not appearing in clusters despite data existing.

**Root Cause:** IDs were sometimes numbers, sometimes strings. Map lookups failed due to type mismatch.

**Fix:** Consistently convert all IDs to strings:

```typescript
// In useSortable
id: String(creative.id)

// In SortableContext
items={creativeIds.map(id => String(id))}

// In Map lookups
creativesMap.get(String(id))
```

---

### Issue 6: Click vs Drag Interference

**Symptom:** After adding click-to-select for metadata tooltips, dragging stopped working entirely.

**Root Cause:** Custom `onPointerDown` and `onPointerMove` handlers overrode dnd-kit's listeners spread via `{...listeners}`.

**Problematic Code:**

```typescript
// These override dnd-kit's handlers
<div
  {...listeners}
  onPointerDown={handlePointerDown}  // OVERRIDES listeners
  onPointerMove={handlePointerMove}  // OVERRIDES listeners
  onClick={handleClick}
>
```

**Fix:** Use a ref to track drag state instead of custom pointer handlers:

```typescript
export function DraggableCreative({ ... }) {
  const wasDraggingRef = useRef(false);

  const { isDragging, ...rest } = useSortable({ ... });

  // Track when drag happens
  useEffect(() => {
    if (isDragging) {
      wasDraggingRef.current = true;
    }
  }, [isDragging]);

  const handleClick = (e: React.MouseEvent) => {
    // Skip if we just finished dragging
    if (wasDraggingRef.current) {
      wasDraggingRef.current = false;
      return;
    }
    onSelect?.(String(creative.id));
  };

  return (
    <div
      {...listeners}  // dnd-kit handlers preserved
      onClick={handleClick}  // Only onClick, no pointer handlers
    >
      ...
    </div>
  );
}
```

---

## Current Implementation Details

### Sensors Configuration

```typescript
const sensors = useSensors(
  useSensor(PointerSensor, {
    activationConstraint: {
      distance: 8,  // 8px movement required to start drag
    },
  })
);
```

### Collision Detection

```typescript
collisionDetection={pointerWithin}
```

### Event Handlers

```typescript
onDragStart={handleDragStart}   // Sets activeId, clears selection
onDragEnd={handleDragEnd}       // Validates target, calls API to move
onDragCancel={handleDragCancel} // Resets activeId
```

### DragOverlay Configuration

```typescript
<DragOverlay dropAnimation={null}>
  {activeCreative ? (
    <DraggableCreative
      creative={activeCreative}
      clusterId=""
      isDragOverlay  // Special styling, no drag handlers
    />
  ) : null}
</DragOverlay>
```

---

## Data Flow

### Drag Start
1. User presses on creative and moves 8+ pixels
2. `handleDragStart` called → sets `activeId`
3. `DragOverlay` shows floating preview
4. Original item gets `opacity-40`

### Drag End
1. User releases
2. `handleDragEnd` called with `active` and `over` objects
3. Validates: same cluster? valid target?
4. Calls API: `PATCH /api/campaigns/{id}` with `add_creative_ids` or `remove_creative_ids`
5. React Query invalidates cache → UI updates

### Click (Selection)
1. User clicks (no movement or <8px movement)
2. `onClick` handler fires
3. Checks `wasDraggingRef` - if true, ignores click
4. Calls `onSelect(creativeId)` → parent updates `selectedCreativeId`
5. Tooltip appears for selected creative

---

## Key Learnings

1. **Collision Detection Matters:** `closestCenter` is aggressive and can cause unwanted drops. Use `pointerWithin` for more precise control.

2. **Don't Override Listeners:** When spreading `{...listeners}` from useSortable, any same-named handlers you add will override them. Use alternative approaches like refs and effects.

3. **ID Types:** Be consistent with string vs number IDs throughout the application.

4. **Distance vs Delay:**
   - `distance: 8` - drag starts after 8px movement (better for distinguishing click vs drag)
   - `delay: 250` - drag starts after 250ms hold (can feel sluggish)

5. **DragOverlay:** Use a separate component instance with special props (`isDragOverlay`) rather than trying to move the actual element.

---

## Remaining Considerations

1. **Touch Support:** May need `TouchSensor` for mobile devices
2. **Keyboard Support:** Consider `KeyboardSensor` for accessibility
3. **Multi-select Drag:** Currently only single item drag supported
4. **Undo/Redo:** No undo functionality for moves yet

---

## References

- [dnd-kit Documentation](https://docs.dndkit.com/)
- [Collision Detection Algorithms](https://docs.dndkit.com/api-documentation/context-provider/collision-detection-algorithms)
- [Sensors](https://docs.dndkit.com/api-documentation/sensors)
