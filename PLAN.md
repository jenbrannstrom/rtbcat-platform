# Plan: Auto-Sync Endpoints and Pretargeting After Seat Discovery

## Problem

The main dashboard shows "No RTB Endpoints Configured" even though:
- Service account is connected
- 22 creatives synced
- Buyer seats discovered

**Root Cause:** Endpoints and pretargeting configs are **never auto-synced**. The setup page auto-discovers buyer seats after adding an account, but does NOT trigger endpoint/pretargeting sync.

## Current Flow (Broken)

1. User uploads service account JSON → ✅
2. `discoverSeats()` is called automatically → ✅ seats discovered
3. User syncs creatives manually → ✅ 22 creatives
4. **Endpoints never synced** → ❌ `rtb_endpoints` table is empty
5. **Pretargeting never synced** → ❌ `pretargeting_configs` table may be empty

The `AccountEndpointsHeader` component on the main page queries `getRTBEndpoints()`, which returns empty because no one called `syncRTBEndpoints()`.

## Solution

**Option A: Auto-sync after seat discovery (Recommended)**

Modify the seat discovery success handler in `setup/page.tsx` to also trigger:
1. `syncRTBEndpoints()` - sync endpoints from Google
2. `syncPretargetingConfigs()` - sync pretargeting from Google

This mirrors the existing auto-discovery pattern and ensures data is populated immediately.

**Option B: Add sync buttons to setup page**

Add explicit "Sync Endpoints" and "Sync Pretargeting" buttons to the setup page's API tab so users can manually trigger syncs.

## Implementation (Option A - Auto-sync)

### Step 1: Add imports to setup page

```tsx
// In dashboard/src/app/setup/page.tsx
import {
  // ... existing imports ...
  syncRTBEndpoints,
  syncPretargetingConfigs,
} from "@/lib/api";
```

### Step 2: Chain syncs after seat discovery

Modify the `discoverMutation` success handler:

```tsx
const discoverMutation = useMutation({
  mutationFn: (bidderId: string) => discoverSeats({ bidder_id: bidderId }),
  onSuccess: async (data) => {
    setMessage({ type: "success", text: `Discovered ${data.seats_discovered} buyer seat(s)` });
    queryClient.invalidateQueries({ queryKey: ["seats"] });

    // Also sync endpoints and pretargeting automatically
    try {
      await syncRTBEndpoints();
      queryClient.invalidateQueries({ queryKey: ["rtb-endpoints"] });
    } catch (e) {
      console.error("Failed to sync endpoints:", e);
    }

    try {
      await syncPretargetingConfigs();
      queryClient.invalidateQueries({ queryKey: ["pretargeting-configs"] });
    } catch (e) {
      console.error("Failed to sync pretargeting:", e);
    }

    setTimeout(() => setMessage(null), 5000);
  },
  // ... rest unchanged
});
```

### Step 3: Also trigger sync when syncing individual seats

When a user clicks "Sync Now" on a buyer seat, also refresh endpoints/pretargeting:

```tsx
const syncMutation = useMutation({
  mutationFn: (buyerId: string) => syncSeat(buyerId),
  onSuccess: async (data) => {
    setMessage({ type: "success", text: `Synced ${data.creatives_synced} creatives` });
    queryClient.invalidateQueries({ queryKey: ["creatives"] });
    queryClient.invalidateQueries({ queryKey: ["seats"] });
    queryClient.invalidateQueries({ queryKey: ["stats"] });
    queryClient.invalidateQueries({ queryKey: ["rtb-endpoints"] });
    queryClient.invalidateQueries({ queryKey: ["pretargeting-configs"] });
    setSyncingId(null);
    setTimeout(() => setMessage(null), 5000);
  },
  // ...
});
```

## Files to Modify

1. **`dashboard/src/app/setup/page.tsx`**
   - Import `syncRTBEndpoints`, `syncPretargetingConfigs`
   - Call them in `discoverMutation.onSuccess`
   - Invalidate related query caches

## Testing

After implementation:
1. Go to Setup page
2. If seats already exist, click "Discover seats for: [project]" button
3. Check main dashboard - endpoints should now appear
4. Pretargeting configs section should also be populated

## Alternative: Force sync on first load

Could also add a one-time sync check in the main page's `useEffect`:
- If endpoints query returns empty but seats exist → trigger sync
- This handles cases where user already has seats but never synced endpoints
