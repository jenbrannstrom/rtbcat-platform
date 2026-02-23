# UX Plan: Publisher Block History & Rollback

**Date:** 2026-02-22
**Branch:** `ui/ux-fixes`
**Scope:** Frontend only (no backend changes)
**Depends on:** `ux-plan-home-publisher-controls.md` (blocking features)

---

## 1. Audit: What Exists Today

### Backend (fully built, ready to use)

| Capability | API Endpoint | Status |
|------------|-------------|--------|
| Change history log | `GET /settings/pretargeting/history?billing_id=&days=` | WORKING |
| Snapshots (create) | `POST /settings/pretargeting/snapshot` | WORKING |
| Snapshots (list) | `GET /settings/pretargeting/snapshots?billing_id=` | WORKING |
| Rollback (dry run) | `POST /settings/pretargeting/{billing_id}/rollback` (dry_run=true) | WORKING |
| Rollback (execute) | `POST /settings/pretargeting/{billing_id}/rollback` (dry_run=false) | WORKING |
| Auto-snapshot before apply-all | Inside `actions_service.py` | WORKING |
| Comparisons (A/B) | `POST/GET /settings/pretargeting/comparison(s)` | WORKING |

### Frontend API Client (fully built)

| Function | File | Status |
|----------|------|--------|
| `getPretargetingHistory()` | `lib/api/uploads.ts` | WORKING |
| `getSnapshots()` | `lib/api/snapshots.ts` | WORKING |
| `createSnapshot()` | `lib/api/snapshots.ts` | WORKING |
| `rollbackSnapshot()` | `lib/api/snapshots.ts` | WORKING |
| `rollbackPretargeting()` | `lib/api/settings.ts` | WORKING (duplicate of above) |

### Frontend UI (partially built, disconnected)

| Component | File | State |
|-----------|------|-------|
| History page | `app/history/page.tsx` | EXISTS but rollback is a TODO placeholder |
| Rollback modal | `app/history/page.tsx` | EXISTS but mutation is a no-op stub |
| Snapshot comparison panel | `components/rtb/snapshot-comparison-panel.tsx` | EXISTS but no rollback action |
| Snapshot cards | `components/rtb/snapshot-comparison-panel.tsx` | EXISTS, show metrics only |
| Config card history button | `components/rtb/pretargeting-config-card.tsx` | EXISTS, opens snapshot panel |

### The Gaps

```
BACKEND (fully built)          FRONTEND (disconnected)

  history API ──────────────── history page (shows data but
  snapshots API ────────────── snapshot panel (shows data but
  rollback API ──X──────────── rollback modal (STUB, no-op)
  auto-snapshot ──X──────────── (not surfaced in UI)

  What's missing:
  1. Rollback wired to real API (not the stub)
  2. History not accessible from Home page
  3. Snapshots have no rollback button
  4. No publisher-specific history filtering
  5. No "last pushed" indicator on Home
```

| # | Gap | Impact |
|---|-----|--------|
| 1 | **Rollback modal calls a stub, not the real API** | CRITICAL -- rollback doesn't work |
| 2 | **No history access from Home page** | HIGH -- must navigate to /history |
| 3 | **Snapshots show metrics but no rollback button** | HIGH -- user sees snapshots, can't restore |
| 4 | **No publisher-specific history filter** | MEDIUM -- all change types mixed together |
| 5 | **No "last pushed" indicator** | LOW -- user doesn't know when last push happened |
| 6 | **Auto-snapshot on push not communicated to user** | LOW -- happens silently |

---

## 2. Design Principle

**See what you changed, undo what went wrong.**

The operator's rollback workflow is:

1. Push publisher blocks to Google
2. Realize something went wrong (blocked the wrong publisher, or performance tanked)
3. See exactly what was changed and when
4. Roll back to the state before the bad push
5. Confirm the rollback pushed to Google

This must be reachable from the Home page without navigating away.

---

## 3. Proposed Features

### 3.1 Wire Rollback to Real API (Fix the Stub)

The history page's `RollbackModal` currently has:

```typescript
// history/page.tsx line 270-278
const rollbackMutation = useMutation({
  mutationFn: async ({ changeId: _changeId, reason: _reason }) => {
    // TODO: Implement rollback endpoint
    return { success: true };
  },
```

This needs to call the real `rollbackSnapshot()` API. But there's a design
mismatch: the history page shows individual change entries, not snapshots.
Rollback works on **snapshots**, not individual history entries.

**Two rollback paths are needed:**

| Path | Trigger | Mechanism |
|------|---------|-----------|
| **Snapshot rollback** | "Restore to this snapshot" | `rollbackSnapshot(billing_id, snapshot_id)` -- already built in backend |
| **Undo last push** | "Undo last push" | Find most recent auto-snapshot before the push, then rollback to it |

Both use the same API endpoint. The difference is how the user selects which
snapshot to restore.

### 3.2 History Panel on Home (Inline, Per-Config)

Add a collapsible history panel inside the config breakdown on the Home page,
accessible via a [History] button in the publisher tab toolbar.

**Publisher tab toolbar (updated from blocking plan):**

```
┌──────────────────────────────────────────────────────────────────────┐
│ Mode: Blacklist    [Filter:________]    [History]    [Full Editor >] │
└──────────────────────────────────────────────────────────────────────┘
```

**Clicking [History] expands an inline panel below the block input:**

```
┌══════════════════════════════════════════════════════════════════════┐
║  [By Creative] [By Size] [By Geo] [*By Publisher*]                   ║
║                                                                      ║
║  Mode: Blacklist    [Filter:________]    [*History*]  [Full Editor>]  ║
║                                                                      ║
║  Publisher table...                                                  ║
║  Block: [____________________] [Block]                               ║
║                                                                      ║
║  ┌────────────────────────────────────────────────────────────────┐  ║
║  │ PUBLISHER HISTORY                                              │  ║
║  │ Config: US Mobile Display            [Last 30 days v] [Close]  │  ║
║  │                                                                │  ║
║  │ ┌──────────────────────────────────────────────────────────┐   │  ║
║  │ │ Feb 22, 14:34  ·  PUSH  ·  3 changes                   │   │  ║
║  │ │                                                          │   │  ║
║  │ │   BLOCK   com.fakegame.slots                             │   │  ║
║  │ │   BLOCK   clickbait-news.com                             │   │  ║
║  │ │   BLOCK   com.vpn.scam                                   │   │  ║
║  │ │                                                          │   │  ║
║  │ │   Snapshot: auto-before-push-2026-02-22T14:34            │   │  ║
║  │ │                                              [Undo Push] │   │  ║
║  │ └──────────────────────────────────────────────────────────┘   │  ║
║  │                                                                │  ║
║  │ ┌──────────────────────────────────────────────────────────┐   │  ║
║  │ │ Feb 20, 09:15  ·  PUSH  ·  1 change                    │   │  ║
║  │ │                                                          │   │  ║
║  │ │   UNBLOCK  legitimate-app.com                            │   │  ║
║  │ │                                                          │   │  ║
║  │ │   Snapshot: auto-before-push-2026-02-20T09:15            │   │  ║
║  │ │                                              [Undo Push] │   │  ║
║  │ └──────────────────────────────────────────────────────────┘   │  ║
║  │                                                                │  ║
║  │ ┌──────────────────────────────────────────────────────────┐   │  ║
║  │ │ Feb 18, 17:02  ·  SYNC  ·  api_sync                    │   │  ║
║  │ │                                                          │   │  ║
║  │ │   Config synced from Google                              │   │  ║
║  │ │   (No rollback available for syncs)                      │   │  ║
║  │ └──────────────────────────────────────────────────────────┘   │  ║
║  │                                                                │  ║
║  │ Showing 3 events (last 30 days)              [View all ->]     │  ║
║  └────────────────────────────────────────────────────────────────┘  ║
║                                                                      ║
║  Pending Changes (0)                                                 ║
╘══════════════════════════════════════════════════════════════════════╛
```

**Key behaviors:**

- History entries are grouped by push event (all changes in one `applyAll` call = one group)
- Each push group shows the auto-snapshot that was created before it
- [Undo Push] triggers the rollback flow (see 3.3)
- Syncs from Google API show as informational entries (no rollback)
- Filter defaults to publisher changes only (not size/geo/format changes)
- [View all ->] links to `/history?billing_id=${billing_id}`
- [Close] collapses the history panel

### 3.3 Undo Push Flow (Rollback via Auto-Snapshot)

When the user clicks [Undo Push], a two-step flow begins:

**Step 1: Dry Run Preview**

The system calls `rollbackSnapshot(billing_id, snapshot_id, dry_run=true)` to
show what would change.

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│  Undo Push?                                               [X]   │
│                                                                  │
│  Config: US Mobile Display                                       │
│  Restoring to state before push on Feb 22 at 14:34               │
│                                                                  │
│  This will reverse these changes:                                │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  UNBLOCK  com.fakegame.slots     (was blocked in push)     │  │
│  │  UNBLOCK  clickbait-news.com     (was blocked in push)     │  │
│  │  UNBLOCK  com.vpn.scam           (was blocked in push)     │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  (!) This will push changes to Google immediately.               │
│      The undo itself will be recorded in history.                │
│                                                                  │
│  Reason (required):                                              │
│  [Blocked wrong publishers, need to review first_____]           │
│                                                                  │
│                         [Cancel]     [Undo Push]                 │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

**Step 2: Execute**

On confirm, calls `rollbackSnapshot(billing_id, snapshot_id, dry_run=false)`.

**Step 3: Success**

```
┌─────────────────────────────────────────────────────────────────┐
│ (ok) Push undone. Config restored to Feb 22 pre-push state.     │
│     3 publishers unblocked on Google.                [Dismiss]   │
└─────────────────────────────────────────────────────────────────┘
```

**Step 3 (alt): Error**

```
┌─────────────────────────────────────────────────────────────────┐
│ (X) Undo failed                                      [Dismiss]  │
│     Google API: PERMISSION_DENIED                                │
│     Config was not changed.                          [Retry]     │
└─────────────────────────────────────────────────────────────────┘
```

### 3.4 Snapshot Rollback in Snapshot Panel

The existing `snapshot-comparison-panel.tsx` shows snapshots but has no rollback
button. Add a [Restore] button to each snapshot card.

**Current snapshot card:**
```
┌──────────────────────────────────────────────────────┐
│ Snapshot #4: "Before geo expansion"       ACTIVE     │
│ Feb 20                                               │
│                                                      │
│  Impressions    Spend        CTR                     │
│  1.2M           $4.5K        0.38%                   │
│                                                      │
│  Notes: Before adding DE and FR geos                 │
└──────────────────────────────────────────────────────┘
```

**Proposed snapshot card (with rollback):**
```
┌──────────────────────────────────────────────────────┐
│ Snapshot #4: "Before geo expansion"       ACTIVE     │
│ Feb 20                                               │
│                                                      │
│  Impressions    Spend        CTR                     │
│  1.2M           $4.5K        0.38%                   │
│                                                      │
│  Notes: Before adding DE and FR geos                 │
│                                                      │
│  Publisher list: 12 blocked (Blacklist mode)          │
│  Sizes: 300x250, 320x50, 728x90 + 4 more            │
│  Geos: US, GB, DE                                    │
│                                                      │
│                          [Preview Restore] [Restore] │
└──────────────────────────────────────────────────────┘
```

- [Preview Restore] calls `rollbackSnapshot(dry_run=true)` and shows the diff
- [Restore] opens the confirmation modal (same as Undo Push flow, step 1)
- Added config summary (publisher count, sizes, geos) so user knows what they're restoring to

### 3.5 "Last Pushed" Indicator

Add a small indicator in the publisher tab showing when the last push happened.

```
┌──────────────────────────────────────────────────────────────────────┐
│ Mode: Blacklist    [Filter:________]    [History]    [Full Editor >] │
│ Last pushed: Feb 22 at 14:34 (3 blocks)                             │
└──────────────────────────────────────────────────────────────────────┘
```

- Derived from the most recent `api_write` history entry for this billing_id
- Shows timestamp and summary count
- If no push history exists: "Never pushed" or hidden entirely

---

## 4. Full Layout: Publisher Tab with History Open

```
╔══════════════════════════════════════════════════════════════════════════╗
║  Config: "US Mobile Display"  ACTIVE                             [v]   ║
╠════════════════════════════════════════════════════════════════════════╣
║                                                                        ║
║  [By Creative] [By Size] [By Geo] [*By Publisher*]                     ║
║                                                                        ║
║  ┌──────────────────────────────────────────────────────────────────┐  ║
║  │ Mode: Blacklist    [Filter:______]      [*History*] [Full Edt>] │  ║
║  │ Last pushed: Feb 22 at 14:34 (3 blocks)                        │  ║
║  └──────────────────────────────────────────────────────────────────┘  ║
║                                                                        ║
║  ┌──────────────────────────────────────────────────────────────────┐  ║
║  │ Publisher          │ Spend │ Reachd│ Imps │ WR  │ Stat  │ Act  │  ║
║  │ ───────────────────┼───────┼───────┼──────┼─────┼───────┼───── │  ║
║  │ com.fake.slots     │ $120  │ 450K  │  12K │2.7% │ Blkd  │Unbl  │  ║
║  │ premium-news.com   │ $890  │ 1.2M  │  98K │8.1% │ Alwd  │Blck  │  ║
║  │ com.ok.game        │ $340  │ 800K  │  45K │5.6% │ Alwd  │Blck  │  ║
║  └──────────────────────────────────────────────────────────────────┘  ║
║                                                                        ║
║  Block: [____________________] [Block]                                 ║
║                                                                        ║
║  ┌────────────────────────────────────────────────────────────────────┐║
║  │ PUBLISHER HISTORY                          [Last 30d v]  [Close] │║
║  │                                                                    │║
║  │ ┌────────────────────────────────────────────────────────────────┐│║
║  │ │ Feb 22, 14:34  ·  PUSH  ·  3 publisher changes               ││║
║  │ │                                                                ││║
║  │ │   BLOCK   com.fakegame.slots                                   ││║
║  │ │   BLOCK   clickbait-news.com                                   ││║
║  │ │   BLOCK   com.vpn.scam                                         ││║
║  │ │                                                                ││║
║  │ │   Snapshot saved: auto-before-push-2026-02-22T14:34            ││║
║  │ │                                                    [Undo Push] ││║
║  │ └────────────────────────────────────────────────────────────────┘│║
║  │                                                                    │║
║  │ ┌────────────────────────────────────────────────────────────────┐│║
║  │ │ Feb 20, 09:15  ·  PUSH  ·  1 publisher change                ││║
║  │ │                                                                ││║
║  │ │   UNBLOCK  legitimate-app.com                                  ││║
║  │ │                                                                ││║
║  │ │   Snapshot saved: auto-before-push-2026-02-20T09:15            ││║
║  │ │                                                    [Undo Push] ││║
║  │ └────────────────────────────────────────────────────────────────┘│║
║  │                                                                    │║
║  │ ┌────────────────────────────────────────────────────────────────┐│║
║  │ │ Feb 18, 17:02  ·  SYNC  ·  api_sync                          ││║
║  │ │   Config synced from Google. No rollback for syncs.            ││║
║  │ └────────────────────────────────────────────────────────────────┘│║
║  │                                                                    │║
║  │ 3 events (last 30 days)                          [View all ->]   │║
║  └────────────────────────────────────────────────────────────────────┘║
║                                                                        ║
║  Pending Changes (0) -- no pending changes                             ║
║                                                                        ║
╚════════════════════════════════════════════════════════════════════════╝
```

---

## 5. Rollback Flow Sequence

```
User sees bad results after pushing blocks
       │
       v
Clicks [History] on publisher tab
       │
       v
Sees grouped push events with timestamps
       │
       v
Clicks [Undo Push] on the bad push
       │
       v
System calls rollbackSnapshot(dry_run=true)
       │
       ├──── API returns changes_made[]
       │     (list of what will be reversed)
       v
Undo confirmation modal appears:
  - Shows what will be reversed
  - Shows this pushes to Google immediately
  - Requires a reason (text input)
       │
       ├──── [Cancel] -> close modal, no changes
       │
       v
User enters reason, clicks [Undo Push]
       │
       v
System calls rollbackSnapshot(dry_run=false)
       │
       ├──── Success:
       │       - Success banner shown
       │       - History refreshed (new "rollback" entry appears)
       │       - Publisher table refreshed
       │       - Snapshot panel updated
       │
       ├──── Error:
       │       - Error banner shown
       │       - Config unchanged
       │       - [Retry] button available
       │
       v
New history entry appears:
  "Feb 22, 15:01 · ROLLBACK · Restored to pre-push state"
  "Reason: Blocked wrong publishers, need to review first"
```

---

## 6. History Entry Types & Display

History entries from the API have `change_type` values. Here's how to display
each type in the publisher history panel:

```
┌───────────────┬─────────────────────────────────────────────────────┐
│ change_type   │ Display                                             │
├───────────────┼─────────────────────────────────────────────────────┤
│ api_write     │ PUSH  ·  N publisher changes                        │
│               │   Lists each publisher change                       │
│               │   Shows auto-snapshot reference                     │
│               │   [Undo Push] button                                │
├───────────────┼─────────────────────────────────────────────────────┤
│ api_sync      │ SYNC  ·  Config synced from Google                  │
│               │   Informational only                                │
│               │   No rollback button                                │
├───────────────┼─────────────────────────────────────────────────────┤
│ rollback      │ ROLLBACK  ·  Restored to {snapshot_name}            │
│               │   Shows what was reversed                           │
│               │   Shows reason provided by user                     │
│               │   Orange background (visual distinction)            │
│               │   No rollback-of-rollback (use snapshots instead)   │
├───────────────┼─────────────────────────────────────────────────────┤
│ state_change  │ STATE  ·  Config {activated/suspended}              │
│               │   Informational                                     │
│               │   No rollback from history (use config controls)    │
├───────────────┼─────────────────────────────────────────────────────┤
│ pending_change│ (filtered out -- not shown in history panel)        │
│               │   Pending changes are shown in the pending panel    │
│               │   Only PUSHED changes appear in history             │
└───────────────┴─────────────────────────────────────────────────────┘
```

### Grouping Logic

Multiple history entries from the same `applyAll` push share the same timestamp
(within a few seconds). Group entries by `changed_at` rounded to the nearest
minute + same `change_source`.

```
Entries from API:
  { change_type: "api_write", field_changed: "publisher_targeting",
    new_value: "com.fakegame.slots", changed_at: "2026-02-22T14:34:02" }
  { change_type: "api_write", field_changed: "publisher_targeting",
    new_value: "clickbait-news.com", changed_at: "2026-02-22T14:34:02" }
  { change_type: "api_write", field_changed: "publisher_targeting",
    new_value: "com.vpn.scam", changed_at: "2026-02-22T14:34:03" }

Grouped for display:
  Feb 22, 14:34  ·  PUSH  ·  3 publisher changes
    BLOCK  com.fakegame.slots
    BLOCK  clickbait-news.com
    BLOCK  com.vpn.scam
```

### Publisher-Only Filter

The history panel on the Home publisher tab should filter to publisher-related
entries only:

```typescript
const publisherHistory = history.filter(entry =>
  entry.field_changed === 'publisher_targeting' ||
  entry.change_type === 'rollback' ||
  entry.change_type === 'api_sync'  // show syncs for context
);
```

Size, geo, and format changes are excluded from this view. They appear on the
global `/history` page.

---

## 7. Snapshot-to-History Association

To show "Snapshot saved: auto-before-push-..." on each push entry, we need to
associate snapshots with push events.

**Current state:** Auto-snapshots are created by `actions_service.apply_all_pending_changes()`
before the push, with `snapshot_type = 'before_change'`. The snapshot's `created_at`
is within seconds of the history entry's `changed_at`.

**Association strategy (frontend-only, no backend change):**

```typescript
// For each push group, find the nearest auto-snapshot
function findAssociatedSnapshot(
  pushTimestamp: string,
  snapshots: PretargetingSnapshot[]
): PretargetingSnapshot | null {
  const pushTime = new Date(pushTimestamp).getTime();
  return snapshots.find(snap => {
    const snapTime = new Date(snap.created_at).getTime();
    const diff = pushTime - snapTime;
    // Snapshot should be within 30 seconds BEFORE the push
    return diff >= 0 && diff < 30_000 && snap.snapshot_type === 'before_change';
  }) || null;
}
```

If no associated snapshot is found (e.g., old pushes before auto-snapshot was
added), the [Undo Push] button is disabled with tooltip: "No snapshot available
for this push."

---

## 8. Undo Confirmation Modal (Detailed)

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│  Undo Push to Google?                                     [X]    │
│                                                                  │
│  Config: US Mobile Display                                       │
│  Restoring to: Feb 22 at 14:33 (before push)                    │
│                                                                  │
│  These changes will be reversed on Google:                       │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  UNBLOCK  com.fakegame.slots                               │  │
│  │  UNBLOCK  clickbait-news.com                               │  │
│  │  UNBLOCK  com.vpn.scam                                     │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  (!) This pushes to Google immediately.                    │  │
│  │      A new history entry "ROLLBACK" will be recorded.      │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  Why are you undoing this push?                                  │
│  [____________________________________________]                  │
│   (required)                                                     │
│                                                                  │
│                          [Cancel]     [Undo Push]                │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

**Loading state (while dry_run executes):**
```
│                          [Cancel]     [Loading...]                │
```

**If dry_run returns no changes:**
```
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  (i) No differences found between current config and       │  │
│  │      snapshot. Config may have been modified since then.    │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│                                              [Close]             │
```

---

## 9. Edge Cases

### No History Entries

```
┌────────────────────────────────────────────────────┐
│ PUBLISHER HISTORY                           [Close] │
│                                                     │
│  No publisher changes recorded for this config.     │
│  Changes will appear here after your first push.    │
└────────────────────────────────────────────────────┘
```

### No Snapshot for Old Push

```
│ Feb 15, 10:22  ·  PUSH  ·  2 publisher changes      │
│                                                       │
│   BLOCK   old-publisher.com                           │
│   BLOCK   another-old.com                             │
│                                                       │
│   No snapshot available    (Undo unavailable)         │
```

### Rollback of a Rollback

Not supported from the history panel. Rollback entries don't have [Undo Push].
If the user needs to re-apply a rolled-back change, they should:
1. Use the snapshot panel to find an earlier snapshot
2. Or re-block the publishers manually

```
│ Feb 22, 15:01  ·  ROLLBACK  ·  Restored pre-push state   │
│                                                            │
│   UNBLOCK  com.fakegame.slots                              │
│   UNBLOCK  clickbait-news.com                              │
│   UNBLOCK  com.vpn.scam                                    │
│                                                            │
│   Reason: "Blocked wrong publishers"                       │
│   (Rollback entries cannot be undone from here.            │
│    Use Snapshots in Full Editor to restore further.)       │
```

### Push Contains Mixed Changes (Publisher + Size + Geo)

The publisher history panel only shows publisher-related changes. If a push
contained both publisher and size changes, only the publisher changes appear.
The full view is on `/history`.

```
│ Feb 22, 14:34  ·  PUSH  ·  3 publisher changes (+2 other)  │
│                                                              │
│   BLOCK   com.fakegame.slots                                 │
│   BLOCK   clickbait-news.com                                 │
│   BLOCK   com.vpn.scam                                       │
│                                                              │
│   + 2 size changes (view in Full History)                    │
│                                                [Undo Push]   │
```

Note: [Undo Push] rolls back the ENTIRE snapshot (all changes, not just
publisher). The modal must make this clear.

### Concurrent Pending Changes During Undo

If pending changes exist when the user tries to undo a push:

```
│  (!) You have 2 pending changes that haven't been pushed.    │
│      Undoing this push won't affect your pending changes.    │
│      Push your pending changes after the undo if needed.     │
```

---

## 10. Implementation Plan

### Phase 1: Wire Rollback + History on Home

**Files changed:**

| File | Changes |
|------|---------|
| `dashboard/src/app/history/page.tsx` | Replace stub mutation with real `rollbackSnapshot()` call |
| `dashboard/src/components/rtb/config-breakdown-panel.tsx` | Add [History] button, inline history panel, [Undo Push] flow |

**Steps:**

1. **Fix history page rollback stub** (quick win)
   - Replace the TODO mutation with real `rollbackSnapshot()` call
   - Wire dry_run preview into modal
   - Show `changes_made[]` from API response

2. **Add [History] toggle to publisher tab toolbar**
   - New state: `showPublisherHistory`
   - Button in the info bar between filter and Full Editor link

3. **Add inline history panel component**
   - `useQuery` for `getPretargetingHistory({ billing_id, days: 30 })`
   - Filter to publisher-related entries
   - Group entries by timestamp (push batches)
   - `useQuery` for `getSnapshots({ billing_id })` to associate snapshots

4. **Add [Undo Push] button per push group**
   - Disabled when no associated auto-snapshot found
   - On click: open undo confirmation modal

5. **Build undo confirmation modal**
   - Calls `rollbackSnapshot(dry_run=true)` on open to get preview
   - Shows changes_made list
   - Requires reason input
   - On confirm: calls `rollbackSnapshot(dry_run=false)`
   - Invalidates queries on success

6. **Add "Last pushed" indicator**
   - Derive from most recent `api_write` history entry
   - Show in publisher info bar

### Phase 2: Enhanced Snapshot Panel

**Files changed:**

| File | Changes |
|------|---------|
| `dashboard/src/components/rtb/snapshot-comparison-panel.tsx` | Add [Restore] button, config summary, rollback flow |

**Steps:**

1. **Add config summary to snapshot cards**
   - Parse `publisher_targeting_values`, `included_sizes`, `included_geos` from snapshot
   - Show publisher count, size list, geo list

2. **Add [Preview Restore] and [Restore] buttons**
   - [Preview Restore] calls `rollbackSnapshot(dry_run=true)`, shows diff inline
   - [Restore] opens same confirmation modal as Undo Push

3. **Handle "no changes" dry_run result**
   - Show informational message if snapshot matches current state

---

## 11. Files Changed (Summary)

| File | Change | Phase |
|------|--------|-------|
| `dashboard/src/app/history/page.tsx` | Wire rollback stub to real API | 1 |
| `dashboard/src/components/rtb/config-breakdown-panel.tsx` | History panel, [Undo Push], last-pushed indicator | 1 |
| `dashboard/src/components/rtb/snapshot-comparison-panel.tsx` | [Restore] button, config summary | 2 |

---

## 12. Out of Scope

- Backend API changes
- New API endpoints
- Rollback-of-rollback
- Cross-config undo (undo across multiple configs at once)
- Keyboard shortcuts
- Export history from Home panel (use global /history page for that)
- Auto-refresh history after external changes
