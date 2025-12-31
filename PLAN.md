# Plan: Show Endpoints and Pretargeting on Setup Page

## Problem
The setup page shows Connected Accounts and Buyer Seats, but does NOT show:
- **RTB Endpoints** (URL, QPS, trading location, protocol)
- **Pretargeting Configurations** (targeting rules, state, formats, platforms, sizes, geos)

These are critical configuration items that users expect to see when they have 22 creatives synced. The data exists in the database and APIs work - it's just not integrated into the setup page UI.

## Current State

### Setup Page Structure (`/setup/page.tsx`)
- Tab 1: **Connect API** - Service accounts + Buyer seats
- Tab 2: **Gmail Reports** - Gmail integration
- Tab 3: **System** - Database stats, thumbnails

### Existing Components (on main dashboard, NOT setup)
- `AccountEndpointsHeader` - Shows RTB endpoints with URLs, QPS, protocols
- `PretargetingConfigCard` - Shows pretargeting configs with targeting settings

### Available APIs
- `getRTBEndpoints()` / `syncRTBEndpoints()` - Endpoint management
- `getPretargetingConfigs()` / `syncPretargetingConfigs()` - Pretargeting management

---

## Solution

Add two new sections to the **API Connection Tab** (below Buyer Seats):

### 1. RTB Endpoints Section
**Location:** After "Buyer Seats" in `ApiConnectionTab`

**Display:**
- List all RTB endpoints showing:
  - Trading location (US West, US East, Europe, Asia)
  - Endpoint URL
  - Max QPS
  - Bid protocol (OpenRTB 2.5, etc.)
- Total QPS allocated across all endpoints
- "Sync Endpoints" button to refresh from Google API
- Last synced timestamp

**Empty state:** "No endpoints configured. Endpoints will sync automatically when you add a service account."

### 2. Pretargeting Configurations Section
**Location:** After RTB Endpoints

**Display:**
- List all pretargeting configs showing:
  - Config name (display_name or billing_id)
  - State badge (ACTIVE/SUSPENDED)
  - Format targets (HTML, VAST, etc.)
  - Platform targets (PHONE, TABLET, DESKTOP)
  - Size targets (300x250, 320x50, etc.)
  - Geo targets (country codes)
- "Sync Configs" button to refresh from Google API
- Last synced timestamp

**Empty state:** "No pretargeting configurations found. These will appear after syncing your endpoints."

---

## Implementation Steps

### Step 1: Add imports to setup page
Add API imports for:
- `getRTBEndpoints`, `syncRTBEndpoints`
- `getPretargetingConfigs`, `syncPretargetingConfigs`
- Types: `RTBEndpointsResponse`, `PretargetingConfigResponse`

### Step 2: Create RTBEndpointsSection component
New component inside setup/page.tsx that:
- Fetches endpoints with `useQuery`
- Shows endpoint list with location, URL, QPS, protocol
- Has sync button with `useMutation`
- Shows total QPS summary
- Handles loading/error/empty states

### Step 3: Create PretargetingSection component
New component inside setup/page.tsx that:
- Fetches pretargeting configs with `useQuery`
- Shows config list with name, state, targeting summary
- Has sync button with `useMutation`
- Handles loading/error/empty states

### Step 4: Integrate into ApiConnectionTab
Add both sections after the Buyer Seats section:
```tsx
{/* Buyer Seats Section */}
<div>...</div>

{/* RTB Endpoints Section */}
<RTBEndpointsSection />

{/* Pretargeting Configs Section */}
<PretargetingSection />
```

### Step 5: Add icons
Import additional icons: `Globe`, `Target`, `Zap` (or similar for endpoints/pretargeting)

---

## UI Design

```
┌─────────────────────────────────────────────────────────────┐
│ Connected Accounts                                    [Add] │
│ ✓ adx-service-mingle-mobyoung                       Remove │
│   mobyoung-adx-bidder-access@...                           │
│   1 buyer seat discovered                                   │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Buyer Seats                                                 │
│ [Discover: adx-service-mingle-mobyoung]                    │
│ ┌─────────────────────────────────────────────────────┐    │
│ │ Amazing MobYoung                                     │    │
│ │ 22 creatives · Last synced 30/12/2025   [Sync Now] │    │
│ └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ RTB Endpoints                                    [Sync Now] │
│ ┌─────────────────────────────────────────────────────┐    │
│ │ 🌐 US West    rtb.google.com/bidder/...   5,000 QPS │    │
│ │ 🌐 Europe     rtb-eu.google.com/...       3,000 QPS │    │
│ └─────────────────────────────────────────────────────┘    │
│ Total: 8,000 QPS allocated · Last synced: 30/12/2025       │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Pretargeting Configurations                      [Sync Now] │
│ ┌─────────────────────────────────────────────────────┐    │
│ │ Config: Mobile Video US          [ACTIVE]           │    │
│ │ Formats: VAST · Platforms: PHONE, TABLET           │    │
│ │ Sizes: 320x480 · Geos: USA, CAN, MEX              │    │
│ └─────────────────────────────────────────────────────┘    │
│ ┌─────────────────────────────────────────────────────┐    │
│ │ Config: Desktop Display EU       [SUSPENDED]        │    │
│ │ Formats: HTML · Platforms: DESKTOP                 │    │
│ │ Sizes: 300x250, 728x90 · Geos: DEU, FRA, GBR      │    │
│ └─────────────────────────────────────────────────────┘    │
│ Last synced: 30/12/2025                                    │
└─────────────────────────────────────────────────────────────┘
```

---

## Files to Modify

1. **`dashboard/src/app/setup/page.tsx`**
   - Add imports for endpoint/pretargeting APIs
   - Add `RTBEndpointsSection` component
   - Add `PretargetingSection` component
   - Integrate sections into `ApiConnectionTab`

---

## Estimated Changes
- ~150-200 lines of new code for two new sections
- No new files needed - all additions to existing setup page
- Reuses existing API functions and types
