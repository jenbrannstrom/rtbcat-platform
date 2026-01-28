# Publisher List Management - UI Specification

## Overview

This feature enables users to manage publisher whitelists and blacklists directly within each pretargeting configuration, eliminating the need for CSV uploads through the Google UI.

**Key Principles:**
- One-click add/remove of individual publishers
- All changes are staged locally before applying to Google
- Full audit trail with timestamps and user tracking
- One-click rollback to any previous state
- Clear separation between **Publisher List** and general **Config Settings**

---

## 1. Entry Point (Refined)

The publisher list editor is accessed via a dedicated **Publisher List** button in the pretargeting config header, not buried under a generic "Edit" button.

```
┌─────────────────────────────────────────────────────────────┐
│ Pretargeting Config: "US Mobile Display"      [Sync 🔄]     │
│                                                             │
│ [Publisher List]  [Config Settings]                         │
│                                                             │
│ Mode: Blacklist (12 blocked)                                │
└─────────────────────────────────────────────────────────────┘
```

**UX Notes:**
- Replace any ambiguous "Edit" button with **Publisher List** (primary) and **Config Settings** (secondary).
- Publisher List opens a **dedicated editor screen** (not a small inline panel).
- If no publishers are configured, show "No publisher targeting" with a clear CTA.

---

## 2. Publisher List Screen (Full Page)

The Publisher List opens in a full-page editor for clarity and speed. This avoids cramped inline panels and makes block/unblock the primary workflow.

**Header:**
- Title: `Publisher List — {Config Name}`
- Status pill: `Changes pending` (if any)
- Buttons: **Sync with Google**, **History**

**Mode Toggle:**
- Large toggle with confirmation when switching to Whitelist
- Confirmation text explains that switching **clears** the current list

---

## 3. Publisher Table - Blacklist Mode

When the pretargeting config is set to block specific publishers:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Publishers                                          Mode: ● Blacklist      │
│                                                             ○ Whitelist     │
├─────────────────────────────────────────────────────────────────────────────┤
│  🔍 Filter publishers...                                                    │
├───────────────────────────────────┬────────┬─────────────┬──────────────────┤
│  Publisher ID                     │ Type   │ Status      │ Action           │
├───────────────────────────────────┼────────┼─────────────┼──────────────────┤
│  com.fakegame.slots               │ App    │ Blocked     │ [Remove]         │
│  clickbait-news.com               │ Web    │ Blocked     │ [Remove]         │
│  com.badapp.vpn                   │ App    │ Blocked     │ [Remove]         │
│  spammy-site.net                  │ Web    │ Blocked     │ [Remove]         │
├───────────────────────────────────┴────────┴─────────────┴──────────────────┤
│                                                                             │
│  + Add publisher to block: [_______________________] [Block]                │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  [Bulk Import]    [Export CSV]    [View History]                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

**UX Notes:**
- **Mode indicator**: Radio buttons at top right show current mode
- **Filter**: Instant client-side filtering as user types
- **Type column**: Auto-detected from publisher ID format (app IDs vs domains)
- **Status**: Shows "Blocked" for all items in blacklist mode
- **Action**: [Remove] button to unblock a publisher
- **Input row**: Always visible at bottom for quick additions
- **Button label**: Shows [Block] because we're in blacklist mode

---

## 4. Publisher Table - Whitelist Mode

When the pretargeting config is set to allow only specific publishers:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Publishers                                          Mode: ○ Blacklist      │
│                                                             ● Whitelist     │
├─────────────────────────────────────────────────────────────────────────────┤
│  🔍 Filter publishers...                                                    │
├───────────────────────────────────┬────────┬─────────────┬──────────────────┤
│  Publisher ID                     │ Type   │ Status      │ Action           │
├───────────────────────────────────┼────────┼─────────────┼──────────────────┤
│  premium-news.com                 │ Web    │ Allowed     │ [Remove]         │
│  com.trusted.app                  │ App    │ Allowed     │ [Remove]         │
│  quality-publisher.net            │ Web    │ Allowed     │ [Remove]         │
│  com.verified.game                │ App    │ Allowed     │ [Remove]         │
├───────────────────────────────────┴────────┴─────────────┴──────────────────┤
│                                                                             │
│  + Add publisher to allow: [_______________________] [Add]                  │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  [Bulk Import]    [Export CSV]    [View History]                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

**UX Notes:**
- **Status**: Shows "Allowed" for all items in whitelist mode
- **Input label**: "Add publisher to allow:"
- **Button label**: Shows [Add] because we're in whitelist mode
- All other elements behave the same as blacklist mode

---

## 5. Dynamic Elements by Mode

The UI adapts based on the current targeting mode:

| Element              | Blacklist Mode          | Whitelist Mode          |
|----------------------|-------------------------|-------------------------|
| Status column        | "Blocked"               | "Allowed"               |
| Input label          | "Add publisher to block:" | "Add publisher to allow:" |
| Action button        | **[Block]**             | **[Add]**               |
| Pending add label    | "Block: publisher.com"  | "Add: publisher.com"    |
| Pending remove label | "Unblock: publisher.com"| "Remove: publisher.com" |

---

## 6. Adding a Publisher

### Step 1: Enter Publisher ID

User types a publisher ID in the input field and clicks the action button.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  + Add publisher to block: [com.newfraud.app_______] [Block]                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Step 2: Publisher Appears as Pending

The new publisher appears in the table with "Pending" status:

```
├───────────────────────────────────┬────────┬─────────────┬──────────────────┤
│  Publisher ID                     │ Type   │ Status      │ Action           │
├───────────────────────────────────┼────────┼─────────────┼──────────────────┤
│  com.fakegame.slots               │ App    │ Blocked     │ [Remove]         │
│  clickbait-news.com               │ Web    │ Blocked     │ [Remove]         │
│  com.newfraud.app                 │ App    │ ⏳ Pending   │ [Undo]           │
├───────────────────────────────────┴────────┴─────────────┴──────────────────┤
```

### Step 3: Pending Changes Panel Appears

A panel appears at the bottom showing all uncommitted changes:

```
├─────────────────────────────────────────────────────────────────────────────┤
│  Pending Changes (1)                                        not yet applied │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  • Block: com.newfraud.app                                    [Undo]  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  [Discard All]                                      [Apply to Google]       │
└─────────────────────────────────────────────────────────────────────────────┘
```

**UX Notes:**
- Pending items are visually distinct (yellow/orange background or icon)
- [Undo] removes the pending change without affecting Google
- Changes are NOT sent to Google until user clicks [Apply to Google]
- User can continue adding/removing publishers before applying
- Pending Changes panel is sticky at the bottom whenever changes exist

---

## 7. Removing a Publisher

### Step 1: Click Remove

User clicks [Remove] on an existing publisher:

```
│  clickbait-news.com               │ Web    │ Blocked     │ [Remove] ◀── CLICK
```

### Step 2: Row Shows Pending Removal

The row changes to show it's pending removal (strikethrough styling):

```
├───────────────────────────────────┬────────┬─────────────┬──────────────────┤
│  Publisher ID                     │ Type   │ Status      │ Action           │
├───────────────────────────────────┼────────┼─────────────┼──────────────────┤
│  com.fakegame.slots               │ App    │ Blocked     │ [Remove]         │
│  ~~clickbait-news.com~~           │ ~~Web~~│ 🗑 Removing  │ [Undo]           │
│  com.badapp.vpn                   │ App    │ Blocked     │ [Remove]         │
├───────────────────────────────────┴────────┴─────────────┴──────────────────┤
```

### Step 3: Pending Changes Updated

```
├─────────────────────────────────────────────────────────────────────────────┤
│  Pending Changes (1)                                        not yet applied │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  • Unblock: clickbait-news.com                                [Undo]  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  [Discard All]                                      [Apply to Google]       │
└─────────────────────────────────────────────────────────────────────────────┘
```

**UX Notes:**
- Strikethrough text indicates pending removal
- Status changes to "🗑 Removing"
- Action button changes from [Remove] to [Undo]
- Item remains visible until changes are applied

---

## 8. Multiple Pending Changes

Users can batch multiple changes before applying:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Publishers                                          Mode: ● Blacklist      │
│                                                             ○ Whitelist     │
├─────────────────────────────────────────────────────────────────────────────┤
│  🔍 Filter publishers...                                                    │
├───────────────────────────────────┬────────┬─────────────┬──────────────────┤
│  Publisher ID                     │ Type   │ Status      │ Action           │
├───────────────────────────────────┼────────┼─────────────┼──────────────────┤
│  com.fakegame.slots               │ App    │ Blocked     │ [Remove]         │
│  ~~clickbait-news.com~~           │ ~~Web~~│ 🗑 Removing  │ [Undo]           │
│  com.badapp.vpn                   │ App    │ Blocked     │ [Remove]         │
│  com.newfraud.app                 │ App    │ ⏳ Pending   │ [Undo]           │
│  another-spam.net                 │ Web    │ ⏳ Pending   │ [Undo]           │
├───────────────────────────────────┴────────┴─────────────┴──────────────────┤
│                                                                             │
│  + Add publisher to block: [_______________________] [Block]                │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  Pending Changes (3)                                        not yet applied │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  • Block: com.newfraud.app                                    [Undo]  │  │
│  │  • Block: another-spam.net                                    [Undo]  │  │
│  │  • Unblock: clickbait-news.com                                [Undo]  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  [Discard All]                                      [Apply to Google]       │
└─────────────────────────────────────────────────────────────────────────────┘
```

**UX Notes:**
- All pending changes are batched into a single API call
- [Discard All] removes all pending changes
- Individual [Undo] buttons allow selective removal
- Count in header updates: "Pending Changes (3)"

---

## 9. Apply Changes Confirmation

When user clicks [Apply to Google], show a confirmation dialog:

```
┌──────────────────────────────────────────────────────────────┐
│  Apply Changes to Google?                                    │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  The following changes will be applied:                      │
│                                                              │
│    + Block: com.newfraud.app                                 │
│    + Block: another-spam.net                                 │
│    - Unblock: clickbait-news.com                             │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  ℹ️  A snapshot will be created automatically so you    │  │
│  │     can rollback if needed.                             │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│                        [Cancel]    [Apply Changes]           │
└──────────────────────────────────────────────────────────────┘
```

**UX Notes:**
- Shows clear summary of what will change
- Mentions automatic snapshot creation for rollback
- [Cancel] returns to the table without applying
- [Apply Changes] sends the request to Google API

---

## 10. Apply Success State

After successful application:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  ✅ Changes applied successfully                                     [Dismiss]│
│     3 changes saved to Google at 2:34 PM                                     │
└──────────────────────────────────────────────────────────────────────────────┘
```

The table refreshes to show the new state:
- Previously pending items now show normal "Blocked" status
- Removed items are no longer in the table
- Pending Changes panel is hidden (no pending changes)

---

## 11. Switching Modes (Blacklist ↔ Whitelist)

When user clicks the other mode radio button:

### Warning Dialog

```
┌──────────────────────────────────────────────────────────────┐
│  ⚠️  Switch to Whitelist Mode?                                │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  This will CLEAR your current blacklist (4 publishers).     │
│                                                              │
│  In Whitelist mode:                                          │
│  • You will ONLY receive bid requests from publishers        │
│    you explicitly add to the list                            │
│  • All other publishers will be blocked                      │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  ⚠️  Your current blocked publishers will be removed.   │  │
│  │     This cannot be undone without rollback.             │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│                      [Cancel]    [Switch to Whitelist]       │
└──────────────────────────────────────────────────────────────┘
```

### After Confirming Switch

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Publishers                                          Mode: ○ Blacklist      │
│                                                             ● Whitelist     │
├─────────────────────────────────────────────────────────────────────────────┤
│  🔍 Filter publishers...                                                    │
├───────────────────────────────────┬────────┬─────────────┬──────────────────┤
│  Publisher ID                     │ Type   │ Status      │ Action           │
├───────────────────────────────────┼────────┼─────────────┼──────────────────┤
│                                                                             │
│                    No publishers in whitelist yet.                          │
│            Add publishers below to start receiving their traffic.           │
│                                                                             │
├───────────────────────────────────┴────────┴─────────────┴──────────────────┤
│                                                                             │
│  + Add publisher to allow: [_______________________] [Add]                  │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  Pending Changes (1)                                        not yet applied │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  • Mode changed: Blacklist → Whitelist                        [Undo]  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  [Discard All]                                      [Apply to Google]       │
└─────────────────────────────────────────────────────────────────────────────┘
```

**UX Notes:**
- Mode switch is also a pending change until applied
- [Undo] on mode change reverts to previous mode and restores the list
- Empty state message explains what whitelist mode means
- Labels and buttons update immediately to reflect new mode

---

## 12. Bulk Import

For adding many publishers at once, click [Bulk Import]:

### Step 1: Import Dialog

```
┌──────────────────────────────────────────────────────────────┐
│  Bulk Import Publishers                                      │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Enter publisher IDs (one per line or comma-separated):      │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ com.spam.app1                                          │  │
│  │ com.spam.app2                                          │  │
│  │ badsite.com                                            │  │
│  │ another-bad.net                                        │  │
│  │ com.fraud.game                                         │  │
│  │                                                        │  │
│  │                                                        │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│                        [Cancel]    [Preview Import]          │
└──────────────────────────────────────────────────────────────┘
```

### Step 2: Preview Results

```
┌──────────────────────────────────────────────────────────────┐
│  Bulk Import Preview                                         │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ✅ Valid: 4 publishers                                       │
│     • com.spam.app1                                          │
│     • com.spam.app2                                          │
│     • badsite.com                                            │
│     • com.fraud.game                                         │
│                                                              │
│  ⚠️  Skipped: 1 (already in list)                             │
│     • another-bad.net                                        │
│                                                              │
│                          [Back]    [Import 4 Publishers]     │
└──────────────────────────────────────────────────────────────┘
```

**UX Notes:**
- Validates input before importing
- Shows duplicates that will be skipped
- [Back] returns to edit the input
- Imported publishers appear as pending changes

---

## 13. View History

Click [View History] to see the audit log:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Publisher Targeting History                                    [Export ↓]  │
├─────────────────────────────────────────────────────────────────────────────┤
│  Filter: [All Changes ▼]    Date: [Last 30 days ▼]                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  Jan 23, 2026 · 2:34 PM · user@company.com                            │  │
│  │  ──────────────────────────────────────────────────────────────────── │  │
│  │  Added 2 publishers to blacklist:                                     │  │
│  │    + com.newfraud.app                                                 │  │
│  │    + another-spam.net                                                 │  │
│  │                                                                       │  │
│  │  Removed 1 publisher from blacklist:                                  │  │
│  │    - clickbait-news.com                                               │  │
│  │                                                         [Rollback ↩]  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  Jan 22, 2026 · 9:15 AM · user@company.com                            │  │
│  │  ──────────────────────────────────────────────────────────────────── │  │
│  │  Removed 1 publisher from blacklist:                                  │  │
│  │    - legitimate-app.com (accidentally blocked)                        │  │
│  │                                                         [Rollback ↩]  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  Jan 20, 2026 · 4:45 PM · admin@company.com                           │  │
│  │  ──────────────────────────────────────────────────────────────────── │  │
│  │  Changed mode: Whitelist → Blacklist                                  │  │
│  │  Cleared 45 publishers from whitelist                                 │  │
│  │                                                         [Rollback ↩]  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  [Load More...]                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**UX Notes:**
- Each entry shows: date, time, user who made the change
- Changes are grouped by apply action (single API call = single entry)
- [Rollback ↩] appears on each entry to restore that state
- Filter dropdown: All Changes, Additions, Removals, Mode Changes
- Date filter: Last 7 days, Last 30 days, Last 90 days, Custom range
- [Export ↓] downloads history as CSV

---

## 14. Rollback Flow

### Step 1: Click Rollback

User clicks [Rollback ↩] on a history entry.

### Step 2: Confirmation Dialog

```
┌──────────────────────────────────────────────────────────────┐
│  Rollback Publisher List                                     │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Restore to state BEFORE this change:                        │
│  January 23, 2026 at 2:34 PM                                 │
│                                                              │
│  This will:                                                  │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  ✓ Restore: clickbait-news.com (was removed)           │  │
│  │  ✗ Remove: com.newfraud.app (was added)                │  │
│  │  ✗ Remove: another-spam.net (was added)                │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ⚠️  All changes made after Jan 23 will be undone.           │
│     These changes will remain visible in history.            │
│                                                              │
│                        [Cancel]    [Rollback Now]            │
└──────────────────────────────────────────────────────────────┘
```

### Step 3: Success

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  ✅ Rollback successful                                              [Dismiss]│
│     Publisher list restored to January 22, 2026 state                        │
└──────────────────────────────────────────────────────────────────────────────┘
```

**UX Notes:**
- Rollback creates a NEW history entry (audit trail preserved)
- Shows exactly what will change before confirming
- All post-rollback changes remain visible in history for reference
- Rollback is itself rollback-able

---

## 15. Empty States

### No Publisher Targeting Configured

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Publishers                                          Mode: ● Blacklist      │
│                                                             ○ Whitelist     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│                        📋 No publishers blocked yet                          │
│                                                                             │
│         Add publishers below to block them from bid requests.               │
│         Or switch to Whitelist mode to allow only specific publishers.      │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  + Add publisher to block: [_______________________] [Block]                │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  [Bulk Import]    [Export CSV]    [View History]                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

### No History

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Publisher Targeting History                                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│                          📜 No history yet                                   │
│                                                                             │
│              Changes to publisher targeting will appear here.               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 16. Error States

### API Error on Apply

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  ❌ Failed to apply changes                                          [Dismiss]│
│     Google API error: Rate limit exceeded. Please try again in 60 seconds.   │
│                                                              [Retry]         │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Invalid Publisher ID

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  ⚠️  Invalid publisher ID                                            [Dismiss]│
│     "not a valid id!" contains invalid characters.                           │
│     Use app bundle IDs (com.example.app) or domains (example.com).           │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Duplicate Publisher

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  ℹ️  Publisher already in list                                       [Dismiss]│
│     com.fakegame.slots is already blocked.                                   │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 17. Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Enter` (in input field) | Add/Block publisher |
| `Escape` | Close modal / Cancel pending action |
| `/` | Focus filter input |
| `Ctrl+Z` | Undo last pending change |

---

## 18. Responsive Behavior

On smaller screens, the table collapses:

```
┌─────────────────────────────────────────────┐
│  Publishers          Mode: [Blacklist ▼]   │
├─────────────────────────────────────────────┤
│  🔍 Filter...                               │
├─────────────────────────────────────────────┤
│  com.fakegame.slots              [Remove]   │
│  App · Blocked                              │
├─────────────────────────────────────────────┤
│  clickbait-news.com              [Remove]   │
│  Web · Blocked                              │
├─────────────────────────────────────────────┤
│  com.newfraud.app                  [Undo]   │
│  App · ⏳ Pending                            │
├─────────────────────────────────────────────┤
│  + [________________________] [Block]       │
├─────────────────────────────────────────────┤
│  Pending Changes (1)                        │
│  • Block: com.newfraud.app          [Undo]  │
│                                             │
│  [Discard]              [Apply to Google]   │
└─────────────────────────────────────────────┘
```

---

## Summary

This UI provides:

1. **Simplicity**: Add/remove publishers with one click
2. **Safety**: All changes staged before applying
3. **Visibility**: Clear pending changes panel
4. **Auditability**: Full history with timestamps and users
5. **Recoverability**: One-click rollback to any previous state
6. **Flexibility**: Bulk import for large changes
7. **Clarity**: Mode-aware labels and actions
