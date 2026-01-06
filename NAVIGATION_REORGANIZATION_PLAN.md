# Plan: Navigation Reorganization

## Problem Statement

The current sidebar navigation evolved organically and doesn't clearly communicate Cat-Scan's purpose as a **QPS optimization tool**. Users may not understand the relationship between features or the recommended workflow.

---

## Current Navigation

```
├── Waste Optimizer (/)           ← Home, but "waste" is confusing
├── Creatives (/creatives)        ← Browse creatives
├── Campaigns (/campaigns)        ← Manual groupings
├── Change History (/history)     ← Pretargeting changes
├── Import (/import)              ← CSV upload
└── Setup (/setup)                ← Initial config
    └── Admin (/admin)            ← Admin only
```

**Issues:**
1. "Waste Optimizer" doesn't convey QPS optimization
2. No clear path to Pretargeting management
3. Analytics buried or missing from nav
4. "Campaigns" is secondary to optimization goal
5. Workflow order unclear

---

## Proposed Navigation

### Primary Navigation (Task-Oriented)

```
├── QPS Dashboard (/)             ← Rename from "Waste Optimizer"
│   └── Overview of QPS efficiency, top recommendations
│
├── Pretargeting (/pretargeting)  ← NEW: Dedicated section
│   ├── Configs list
│   ├── Pending changes
│   └── Change history
│
├── Creatives (/creatives)        ← Keep, add geo section
│   └── Browse, filter, detail modal
│
├── Analytics (/analytics)        ← NEW: Consolidate analytics
│   ├── RTB Funnel
│   ├── Publisher Performance
│   ├── Geo Performance
│   └── Size Coverage
│
├── Import (/import)              ← Keep
│   └── CSV upload, Gmail sync status
│
└── Settings (/settings)          ← Consolidate setup + settings
    ├── Buyer Seats
    ├── Credentials
    ├── Data Retention
    └── Admin (if admin)
```

### Workflow-Based Grouping

| Group | Pages | Purpose |
|-------|-------|---------|
| **Monitor** | QPS Dashboard, Analytics | Understand current state |
| **Optimize** | Pretargeting, Creatives | Take action |
| **Data** | Import | Feed the system |
| **Configure** | Settings | One-time setup |

---

## Implementation Details

### File: `dashboard/src/components/sidebar.tsx`

**Current navigation array (line 34-41):**
```typescript
const navigationItems = [
  { key: "wasteOptimizer" as const, href: "/", icon: TrendingDown },
  { key: "creatives" as const, href: "/creatives", icon: Image },
  { key: "campaigns" as const, href: "/campaigns", icon: FolderKanban },
  { key: "changeHistory" as const, href: "/history", icon: History },
  { key: "import" as const, href: "/import", icon: RefreshCw },
  { key: "setup" as const, href: "/setup", icon: Settings },
];
```

**Proposed navigation array:**
```typescript
import {
  Gauge,           // QPS Dashboard
  Target,          // Pretargeting
  Image,           // Creatives
  BarChart3,       // Analytics
  Upload,          // Import
  Settings,        // Settings
} from "lucide-react";

const navigationItems = [
  { key: "qpsDashboard" as const, href: "/", icon: Gauge },
  { key: "pretargeting" as const, href: "/pretargeting", icon: Target },
  { key: "creatives" as const, href: "/creatives", icon: Image },
  { key: "analytics" as const, href: "/analytics", icon: BarChart3 },
  { key: "import" as const, href: "/import", icon: Upload },
  { key: "settings" as const, href: "/settings", icon: Settings },
];
```

### File: `dashboard/src/lib/i18n/translations/en.ts`

Add new translation keys:
```typescript
navigation: {
  qpsDashboard: "QPS Dashboard",
  pretargeting: "Pretargeting",
  creatives: "Creatives",
  analytics: "Analytics",
  import: "Import",
  settings: "Settings",
  // ... keep others for backwards compatibility
}
```

### New Pages Needed

| Route | File | Purpose |
|-------|------|---------|
| `/pretargeting` | `app/pretargeting/page.tsx` | Pretargeting configs list |
| `/pretargeting/[id]` | `app/pretargeting/[id]/page.tsx` | Config detail + pending changes |
| `/analytics` | `app/analytics/page.tsx` | Analytics hub |
| `/analytics/funnel` | `app/analytics/funnel/page.tsx` | RTB funnel analysis |
| `/analytics/publishers` | `app/analytics/publishers/page.tsx` | Publisher performance |
| `/analytics/geo` | `app/analytics/geo/page.tsx` | Geographic performance |

### Redirects for Backwards Compatibility

```typescript
// app/history/page.tsx
redirect('/pretargeting?tab=history')

// app/setup/page.tsx
redirect('/settings')

// app/waste-analysis/page.tsx
redirect('/')
```

---

## Migration Steps

### Phase 1: Restructure Routes (Non-Breaking)
- [ ] Create `/pretargeting` pages (move from `/settings/pretargeting`)
- [ ] Create `/analytics` pages (consolidate existing analytics)
- [ ] Create `/settings` hub page
- [ ] Add redirects from old routes

### Phase 2: Update Navigation
- [ ] Update `sidebar.tsx` with new navigation items
- [ ] Update translations for all languages
- [ ] Update any hardcoded route references

### Phase 3: Rename Home
- [ ] Rename "Waste Optimizer" → "QPS Dashboard" in UI
- [ ] Update home page title and description
- [ ] Update documentation references

### Phase 4: Cleanup
- [ ] Remove old route files (after redirect period)
- [ ] Remove deprecated translation keys
- [ ] Update README navigation section

---

## Edge Cases

1. **Bookmarked URLs**: Redirects preserve old URLs for 90 days
2. **Admin section**: Remains under `/admin`, accessible from Settings
3. **Campaigns**: Demote to secondary (accessible but not in main nav)
4. **Mobile**: Ensure new nav works in collapsed sidebar

---

## Success Metrics

- Users find Pretargeting in <2 clicks from home
- Analytics usage increases (currently underutilized)
- Setup/onboarding flow clearer for new users
- Navigation labels match RTB terminology
