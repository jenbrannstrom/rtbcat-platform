# Phase 10.4: Thumbnail Generation + Waste Detection + Campaign Clustering

**Objective:** Build a complete campaign clustering system with visual drag-and-drop, where broken/wasteful creatives are clearly flagged to the user.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DATA FLOW                                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  1. THUMBNAIL GENERATION (CLI)                                          │
│     ├─→ Success: Save .jpg + record status='success'                    │
│     └─→ Failure: Record status='failed' + error_reason                  │
│                                                                          │
│  2. WASTE DETECTION (API)                                               │
│     └─→ If creative has impressions BUT thumbnail_status='failed'       │
│         → Flag as "broken_video_waste"                                  │
│                                                                          │
│  3. CARD DISPLAY (Frontend)                                             │
│     ├─→ Grey out: spend = 0 in timeframe                                │
│     ├─→ Warning badge: broken video with impressions                    │
│     └─→ Filter: only show if imps OR clicks OR spend > 0 in timeframe   │
│                                                                          │
│  4. CLUSTER VIEW (Frontend)                                             │
│     ├─→ Large first tile = highest spend                                │
│     ├─→ Drag & drop between clusters                                    │
│     └─→ Editable cluster names                                          │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Part 1: Database Schema Addition

**File:** `creative-intelligence/storage/sqlite_store.py`

Add a new table to track thumbnail generation status:

```sql
CREATE TABLE IF NOT EXISTS thumbnail_status (
    creative_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,           -- 'success', 'failed', 'pending'
    error_reason TEXT,              -- 'url_expired', 'no_url', 'timeout', 'network_error', 'invalid_format'
    video_url TEXT,                 -- The URL we attempted (for debugging)
    attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (creative_id) REFERENCES creatives(id) ON DELETE CASCADE
);
```

Add migration logic to create this table if it doesn't exist (similar to other migrations in the codebase).

---

## Part 2: Enhanced Thumbnail Generation CLI

**File:** `creative-intelligence/cli/qps_analyzer.py`

Modify the existing `generate-thumbnails` command to:

1. Record success/failure status in `thumbnail_status` table
2. Capture specific error reasons
3. Skip creatives that already have a status (unless --force)
4. Provide clear summary at the end

### Requirements:

```python
# Pseudocode for the enhanced command

@cli.command('generate-thumbnails')
@click.option('--limit', default=100)
@click.option('--force', is_flag=True, help='Retry failed thumbnails')
@click.option('--timeout', default=30)
def generate_thumbnails(limit, force, timeout):
    """
    Generate thumbnails and track status in database.
    
    Status values:
    - 'success': Thumbnail generated successfully
    - 'failed': Generation failed (see error_reason)
    
    Error reasons:
    - 'no_url': No video URL found in creative data
    - 'url_expired': URL returned 403/404/410
    - 'timeout': ffmpeg timed out
    - 'network_error': Connection failed
    - 'invalid_format': ffmpeg couldn't decode the video
    """
    
    # 1. Get video creatives that need processing
    #    - If not --force: exclude those with status='success' or status='failed'
    #    - If --force: only retry status='failed', still skip status='success'
    
    # 2. For each video:
    #    a. Extract video URL from raw_data (video.videoUrl or VAST MediaFile)
    #    b. If no URL found: record status='failed', error_reason='no_url'
    #    c. Attempt ffmpeg extraction
    #    d. On success: save .jpg, record status='success'
    #    e. On failure: record status='failed' with appropriate error_reason
    
    # 3. Print summary:
    #    - New successes
    #    - New failures (grouped by error_reason)
    #    - Total coverage: X of Y videos have thumbnails
```

### Error Detection Logic:

```python
def classify_ffmpeg_error(returncode: int, stderr: str, video_url: str) -> str:
    """Classify the ffmpeg error into a user-friendly reason."""
    stderr_lower = stderr.lower()
    
    if 'server returned 403' in stderr_lower or 'server returned 404' in stderr_lower:
        return 'url_expired'
    if 'server returned 410' in stderr_lower:
        return 'url_expired'
    if 'connection refused' in stderr_lower or 'network is unreachable' in stderr_lower:
        return 'network_error'
    if 'invalid data found' in stderr_lower or 'does not contain' in stderr_lower:
        return 'invalid_format'
    if returncode == -9 or 'timeout' in stderr_lower:
        return 'timeout'
    
    return 'unknown'
```

---

## Part 3: API Enhancements

**File:** `creative-intelligence/api/main.py`

### 3.1 Add thumbnail_status to creative responses

When returning creatives, include their thumbnail status:

```python
# In the creative serialization logic, add:
{
    "id": creative.id,
    "format": creative.format,
    # ... existing fields ...
    "thumbnail_status": {
        "status": "success" | "failed" | None,
        "error_reason": "url_expired" | "no_url" | ... | None,
        "has_thumbnail": bool  # True if file exists in ~/.catscan/thumbnails/
    }
}
```

### 3.2 Add waste detection to creative responses

```python
# Compute waste flags:
{
    "waste_flags": {
        "broken_video": bool,  # thumbnail_status='failed' AND impressions > 0
        "zero_engagement": bool,  # impressions > 1000 AND clicks = 0 (existing logic)
    }
}
```

### 3.3 Add timeframe filtering to campaigns endpoint

```python
# GET /campaigns?days=7
# Returns campaigns with aggregated performance data for the timeframe

# GET /campaigns/unclustered?days=7  
# Returns only creatives that have activity (imps OR clicks OR spend > 0) in timeframe
```

### 3.4 Update PATCH /campaigns/{id} for add/remove

Ensure the endpoint supports:
```python
class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    add_creative_ids: Optional[List[str]] = None
    remove_creative_ids: Optional[List[str]] = None
```

---

## Part 4: Frontend - Campaign Clustering Page

**File:** `dashboard/src/app/campaigns/page.tsx`

### 4.1 Page Layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│  CAMPAIGNS                                                              │
│                                                                         │
│  Timeframe: [Last 7 days ▼]        [Cluster by URL] [+ Country] [Reset]│
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ╭─────────────────────╮    ╭─────────────────────╮                   │
│   │  AliExpress US   ✎  │    │  Temu Summer     ✎  │                   │
│   │  ┌────────┬────┬────┤    │  ┌────┬────┬────┐  │                   │
│   │  │ $1.2K  │ 🖼 │ 🖼 │    │  │ 🖼 │ 🖼 │ ⚠️ │  │  ← Warning badge  │
│   │  │ (2x2)  ├────┼────┤    │  └────┴────┴────┘  │                   │
│   │  │        │ 🖼 │ ░░ │    │  5 cr · $1.8K      │                   │
│   │  └────────┴────┴────┘    ╰─────────────────────╯                   │
│   │  12 cr · $4.2K · ⚠️ 2    │                      ← "2 broken videos"│
│   ╰─────────────────────╯    ╭ ─ ─ ─ ─ ─ ─ ─ ─ ─ ╮                    │
│                                    + New                               │
│   ╭─────────────────────╮    │    Campaign       │                    │
│   │  Shein (no spend)   │    ╰ ─ ─ ─ ─ ─ ─ ─ ─ ─ ╯                    │
│   │  ┌────┬────┬────┐   │                                              │
│   │  │ ░░ │ ░░ │ ░░ │   │  ← Greyed out (0 spend)                     │
│   │  └────┴────┴────┘   │                                              │
│   │  3 cr · $0          │                                              │
│   ╰─────────────────────╯                                              │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│  UNCLUSTERED (47 with activity)                              [Expand]  │
│  ┌────┬────┬────┬────┬────┬────┬────┬────┐                             │
│  │ 🖼 │ 🖼 │ ⚠️ │ 🖼 │ ░░ │ 🖼 │ 🖼 │ 🖼 │  ← Mix of states           │
│  └────┴────┴────┴────┴────┴────┴────┴────┘                             │
└─────────────────────────────────────────────────────────────────────────┘

Legend:
  🖼  = Thumbnail present, has spend
  ░░  = Greyed out (0 spend in timeframe)
  ⚠️  = Warning: broken video with impressions (WASTE)
```

### 4.2 Timeframe Selector

Add a dropdown to filter by timeframe:
- Last 7 days (default)
- Last 14 days
- Last 30 days
- All time

This filters which creatives appear AND the performance data shown.

### 4.3 Card States

Each mini card in a cluster should show one of these states:

| State | Condition | Visual |
|-------|-----------|--------|
| **Normal** | Has thumbnail, has spend | Full color thumbnail |
| **Greyed** | Has thumbnail, 0 spend | Thumbnail with opacity-50 overlay |
| **Warning** | Broken video + has impressions | Red warning badge, placeholder thumbnail |
| **No thumbnail** | No thumbnail, has spend | Format icon placeholder |
| **Hidden** | No activity in timeframe | Not shown at all |

### 4.4 Warning Badge Logic

```typescript
interface WasteFlags {
  broken_video: boolean;  // From API
}

function getCardState(creative: Creative, timeframeDays: number): CardState {
  const perf = creative.performance;  // Already filtered by timeframe from API
  
  const hasActivity = (perf?.total_impressions || 0) > 0 
                   || (perf?.total_clicks || 0) > 0 
                   || (perf?.total_spend_micros || 0) > 0;
  
  if (!hasActivity) {
    return 'hidden';  // Don't render this card at all
  }
  
  if (creative.waste_flags?.broken_video) {
    return 'warning';  // Red badge, this is waste
  }
  
  if ((perf?.total_spend_micros || 0) === 0) {
    return 'greyed';  // Show but dimmed
  }
  
  return 'normal';
}
```

### 4.5 Cluster Summary Stats

Each cluster card should show:
- Creative count
- Total spend
- Warning count (if any broken videos)

```typescript
function ClusterStats({ creatives }: { creatives: Creative[] }) {
  const totalSpend = creatives.reduce((sum, c) => 
    sum + (c.performance?.total_spend_micros || 0), 0
  );
  const brokenCount = creatives.filter(c => c.waste_flags?.broken_video).length;
  
  return (
    <div className="text-sm text-gray-600 flex items-center gap-2">
      <span>{creatives.length} creatives</span>
      <span>·</span>
      <span>{formatSpend(totalSpend)}</span>
      {brokenCount > 0 && (
        <>
          <span>·</span>
          <span className="text-red-500 flex items-center gap-1">
            <AlertTriangle className="h-3 w-3" />
            {brokenCount} broken
          </span>
        </>
      )}
    </div>
  );
}
```

---

## Part 5: Frontend Components

### 5.1 File Structure

```
dashboard/src/app/campaigns/
  page.tsx                     # Main page with DndContext

dashboard/src/components/campaigns/
  cluster-card.tsx             # Individual cluster bubble
  creative-mini-card.tsx       # Draggable mini card with state handling
  unassigned-pool.tsx          # Unclustered creatives section
  timeframe-selector.tsx       # Dropdown for 7/14/30 days
```

### 5.2 CreativeMiniCard Component

```typescript
interface CreativeMiniCardProps {
  creative: Creative;
  clusterId: string;
  isLarge?: boolean;  // For highest-spend creative
}

function CreativeMiniCard({ creative, clusterId, isLarge }: CreativeMiniCardProps) {
  // Determine card state
  const state = getCardState(creative);
  
  // Get thumbnail URL
  const thumbnailUrl = getThumbnailUrl(creative);
  
  // dnd-kit sortable hook
  const { attributes, listeners, setNodeRef, transform, isDragging } = useSortable({
    id: creative.id,
    data: { clusterId, creative },
  });
  
  return (
    <div
      ref={setNodeRef}
      {...attributes}
      {...listeners}
      className={cn(
        "relative rounded-md overflow-hidden border cursor-grab",
        isLarge ? "col-span-2 row-span-2" : "",
        state === 'greyed' && "opacity-50",
        isDragging && "opacity-30 ring-2 ring-blue-500",
      )}
    >
      {/* Thumbnail or placeholder */}
      {thumbnailUrl ? (
        <img src={thumbnailUrl} className="w-full h-full object-cover" />
      ) : (
        <div className="w-full h-full bg-gray-200 flex items-center justify-center">
          <FileVideo className="h-6 w-6 text-gray-400" />
        </div>
      )}
      
      {/* Warning badge for broken videos */}
      {state === 'warning' && (
        <div className="absolute top-1 right-1 bg-red-500 text-white rounded-full p-0.5">
          <AlertTriangle className="h-3 w-3" />
        </div>
      )}
      
      {/* Spend badge */}
      {creative.performance?.total_spend_micros > 0 && (
        <div className="absolute bottom-0 inset-x-0 bg-black/70 text-white text-center text-[9px] py-0.5">
          {formatSpend(creative.performance.total_spend_micros)}
        </div>
      )}
    </div>
  );
}
```

### 5.3 Tooltip on Hover (for card details)

When hovering over a mini card, show a tooltip with:
- Creative ID
- Spend / Imps / Clicks / CTR
- Warning reason if broken
- Option to add a label (input field)

```typescript
function CardTooltip({ creative }: { creative: Creative }) {
  const [label, setLabel] = useState(creative.label || '');
  
  return (
    <div className="bg-gray-900 text-white text-xs rounded p-2 min-w-[150px]">
      <div className="font-medium">#{creative.id}</div>
      <div className="mt-1 space-y-0.5 text-gray-300">
        <div>Spend: {formatSpend(creative.performance?.total_spend_micros)}</div>
        <div>Imps: {formatNumber(creative.performance?.total_impressions)}</div>
        <div>CTR: {creative.performance?.ctr_percent?.toFixed(2)}%</div>
      </div>
      
      {creative.waste_flags?.broken_video && (
        <div className="mt-2 text-red-400 flex items-center gap-1">
          <AlertTriangle className="h-3 w-3" />
          Broken video - wasting impressions
        </div>
      )}
      
      <div className="mt-2 border-t border-gray-700 pt-2">
        <input
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          placeholder="Add label..."
          className="w-full bg-gray-800 border border-gray-700 rounded px-1.5 py-0.5 text-xs"
        />
      </div>
    </div>
  );
}
```

---

## Part 6: dnd-kit Implementation

### 6.1 Dependencies (already installed)

```
@dnd-kit/core
@dnd-kit/sortable
@dnd-kit/utilities
@dnd-kit/modifiers
```

### 6.2 DndContext Setup

```typescript
import {
  DndContext,
  DragOverlay,
  closestCenter,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import { createSnapModifier } from '@dnd-kit/modifiers';

// Press delay sensor (250ms hold to drag)
const sensors = useSensors(
  useSensor(PointerSensor, {
    activationConstraint: {
      delay: 250,
      tolerance: 5,
    },
  })
);

// Snap to 60px grid
const snapToGrid = createSnapModifier(60);

// In render:
<DndContext
  sensors={sensors}
  collisionDetection={closestCenter}
  modifiers={[snapToGrid]}
  onDragStart={handleDragStart}
  onDragEnd={handleDragEnd}
>
  {/* Clusters and Unclustered pool */}
  <DragOverlay>
    {activeCreative && <CreativeMiniCard creative={activeCreative} />}
  </DragOverlay>
</DndContext>
```

### 6.3 Drag End Handler

```typescript
async function handleDragEnd(event: DragEndEvent) {
  const { active, over } = event;
  if (!over) return;
  
  const creativeId = active.id as string;
  const sourceClusterId = active.data.current?.clusterId;
  const targetClusterId = over.id as string;
  
  if (sourceClusterId === targetClusterId) return;
  
  // API call to move creative
  if (sourceClusterId && sourceClusterId !== 'unassigned') {
    await fetch(`/api/campaigns/${sourceClusterId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ remove_creative_ids: [creativeId] }),
    });
  }
  
  if (targetClusterId !== 'unassigned') {
    await fetch(`/api/campaigns/${targetClusterId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ add_creative_ids: [creativeId] }),
    });
  }
  
  // Update local state...
}
```

---

## Part 7: Cluster Naming (Editable Labels)

### 7.1 Double-click to Edit Cluster Name

```typescript
function EditableClusterName({ campaign, onRename }: Props) {
  const [isEditing, setIsEditing] = useState(false);
  const [name, setName] = useState(campaign.name);
  const inputRef = useRef<HTMLInputElement>(null);
  
  useEffect(() => {
    if (isEditing) {
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }, [isEditing]);
  
  if (isEditing) {
    return (
      <input
        ref={inputRef}
        value={name}
        onChange={(e) => setName(e.target.value)}
        onBlur={() => {
          onRename(campaign.id, name);
          setIsEditing(false);
        }}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            onRename(campaign.id, name);
            setIsEditing(false);
          }
          if (e.key === 'Escape') {
            setName(campaign.name);
            setIsEditing(false);
          }
        }}
        className="text-lg font-semibold border-b-2 border-blue-500 outline-none bg-transparent"
      />
    );
  }
  
  return (
    <h3 
      onDoubleClick={() => setIsEditing(true)}
      className="text-lg font-semibold cursor-pointer hover:text-blue-600 group flex items-center gap-2"
    >
      {campaign.name}
      <Pencil className="h-4 w-4 opacity-0 group-hover:opacity-40" />
    </h3>
  );
}
```

---

## Implementation Order

### Step 1: Backend - Thumbnail Status Table (30 min)
1. Add `thumbnail_status` table to sqlite_store.py
2. Add migration to create table
3. Add methods: `record_thumbnail_status()`, `get_thumbnail_status()`

### Step 2: CLI - Enhanced Thumbnail Generation (1 hour)
1. Modify `generate-thumbnails` command
2. Record status and error_reason for each attempt
3. Test with `--limit 10`
4. Run full batch: `--limit 1000`

### Step 3: API - Add Status to Responses (1 hour)
1. Include `thumbnail_status` in creative responses
2. Compute `waste_flags.broken_video`
3. Add `days` parameter to `/campaigns` endpoints
4. Ensure PATCH supports add/remove creative_ids

### Step 4: Frontend - Card States (1.5 hours)
1. Create `getCardState()` helper
2. Update `CreativeMiniCard` with state-based styling
3. Add warning badge for broken videos
4. Add tooltip with details

### Step 5: Frontend - Timeframe Selector (30 min)
1. Create dropdown component
2. Wire up to API calls
3. Default to 7 days

### Step 6: Frontend - dnd-kit Integration (2 hours)
1. Set up DndContext with sensors and modifiers
2. Make clusters droppable
3. Make cards draggable
4. Handle drag end (API calls)
5. Add DragOverlay

### Step 7: Frontend - Editable Names (30 min)
1. Cluster name double-click editing
2. Creative label in tooltip

### Step 8: Testing (1 hour)
1. Generate thumbnails, verify status recorded
2. Check broken videos show warning
3. Test drag and drop
4. Test timeframe filtering
5. Test cluster renaming

---

## Testing Checklist

### Thumbnail Generation
- [ ] `generate-thumbnails --limit 5` works
- [ ] Status recorded in `thumbnail_status` table
- [ ] Error reasons are correct (url_expired, no_url, etc.)
- [ ] Running again skips already-processed videos
- [ ] `--force` retries failed ones

### API
- [ ] `/creatives` includes `thumbnail_status` and `waste_flags`
- [ ] `/campaigns?days=7` filters by timeframe
- [ ] `/campaigns/unclustered?days=7` only returns active creatives
- [ ] PATCH add/remove creative_ids works

### Frontend
- [ ] Timeframe selector works (7/14/30 days)
- [ ] Cards with 0 spend are greyed out
- [ ] Broken videos show red warning badge
- [ ] Tooltip shows details + label input
- [ ] Drag and drop works between clusters
- [ ] Drag to unassigned removes from cluster
- [ ] Press delay (250ms) before drag starts
- [ ] Snap to grid during drag
- [ ] Large first tile for highest spend
- [ ] Grid background on clusters
- [ ] Double-click to edit cluster name
- [ ] Delete cluster moves creatives to unassigned

---

## Report Back

After each step, provide:
1. What was implemented
2. Any deviations from spec and why
3. Any issues encountered
4. Confirmation of testing
5. Next step ready to begin
