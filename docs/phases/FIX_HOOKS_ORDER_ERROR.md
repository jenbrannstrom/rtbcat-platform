# URGENT: Fix React Hooks Order Error in Phase 8.2

## 🚨 Critical Issue

**Error:** "React has detected a change in the order of Hooks called by CreativesContent"

**Cause:** Hooks (useState, useEffect, useMemo, etc.) are being called conditionally or in different order between renders.

**Location:** `dashboard/src/app/creatives/page.tsx` (CreativesContent component)

## 🔍 Common Causes

### Problem 1: Conditional Hooks
```typescript
// ❌ WRONG - Hook called conditionally
if (someCondition) {
  const [state, setState] = useState(false);
}

// ✅ CORRECT - Hook always called
const [state, setState] = useState(false);
if (someCondition) {
  // Use the state conditionally
}
```

### Problem 2: Hooks in Loops/Callbacks
```typescript
// ❌ WRONG - Hook in callback
data.map(item => {
  const [state, setState] = useState(false); // NO!
});

// ✅ CORRECT - Hook at top level
const [states, setStates] = useState({});
```

### Problem 3: Early Returns Before Hooks
```typescript
// ❌ WRONG - Return before all hooks
function Component() {
  if (loading) return <div>Loading...</div>;
  const [state, setState] = useState(false); // Hook after conditional return!
}

// ✅ CORRECT - All hooks before returns
function Component() {
  const [state, setState] = useState(false); // All hooks first
  if (loading) return <div>Loading...</div>;
}
```

## 🛠️ Likely Fix for CreativesContent

Based on the Phase 8.2 implementation, the issue is probably in the tier filter logic.

**Check this pattern in page.tsx:**

```typescript
// ❌ WRONG - Conditional hook usage
function CreativesContent() {
  const [sortPeriod, setSortPeriod] = useState<Period>("7d");
  
  // ... other hooks ...
  
  // This might be causing the issue:
  if (isSortingByPerformance) {
    const [tierFilter, setTierFilter] = useState<PerformanceTier | "all">("all");
  }
}

// ✅ CORRECT - Always call hooks
function CreativesContent() {
  const [sortPeriod, setSortPeriod] = useState<Period>("7d");
  const [tierFilter, setTierFilter] = useState<PerformanceTier | "all">("all");
  
  // ... other hooks ...
  
  // Use conditionally in JSX, not in hook definition
  const isSortingByPerformance = sortBy === "performance";
}
```

## 📋 Fix Checklist

1. **Find all useState/useEffect/useMemo calls**
   - Ensure they're ALL at the top of the component
   - Ensure they're NEVER inside if/loops/callbacks
   - Ensure they're BEFORE any early returns

2. **Check the tier filter implementation**
   - `tierFilter` state should be declared unconditionally
   - Only the UI rendering should be conditional

3. **Verify hook order is always the same**
   - Same hooks in same order every render
   - No conditional hook calls

## 🎯 Correct Pattern for Tier Filter

```typescript
export default function CreativesContent() {
  // ✅ ALL hooks at the top, ALWAYS called
  const [creatives, setCreatives] = useState<Creative[]>([]);
  const [loading, setLoading] = useState(true);
  const [sortBy, setSortBy] = useState<"id" | "performance">("id");
  const [sortPeriod, setSortPeriod] = useState<Period>("7d");
  const [tierFilter, setTierFilter] = useState<PerformanceTier | "all">("all"); // Always here!
  const [performanceData, setPerformanceData] = useState<Record<number, PerformanceMetrics>>({});
  const [performanceLoading, setPerformanceLoading] = useState(false);

  // All useEffect hooks
  useEffect(() => { /* ... */ }, []);
  useEffect(() => { /* ... */ }, [sortPeriod]);

  // All useMemo hooks
  const isSortingByPerformance = useMemo(() => sortBy === "performance", [sortBy]);
  const creativesWithPerformance = useMemo(() => { /* ... */ }, [creatives, performanceData]);
  
  // ... rest of component logic
  
  // Conditional rendering (NOT conditional hooks)
  return (
    <div>
      {/* ... */}
      
      {isSortingByPerformance && performanceData && Object.keys(performanceData).length > 0 && (
        <TierFilter
          value={tierFilter}
          onChange={setTierFilter}
          counts={tierCounts}
        />
      )}
    </div>
  );
}
```

## 🚀 Quick Fix Command for Claude CLI

Tell Claude CLI:

```
The React hooks order error is happening because hooks are being called 
conditionally. Please fix dashboard/src/app/creatives/page.tsx:

1. Move ALL useState/useEffect/useMemo calls to the top of CreativesContent
2. Ensure tierFilter state is ALWAYS declared, not conditionally
3. Only make the UI rendering conditional, not the hook declarations
4. Verify all hooks are in the same order every render

The pattern should be:
- All useState at top
- All useEffect after that
- All useMemo after that
- Then component logic
- Then conditional JSX rendering
```

## ✅ Verification

After the fix:
1. Refresh the page - no console errors
2. Check React DevTools - no warnings
3. Test switching between ID sort and Performance sort - smooth
4. Test tier filter - works without errors

---

**Priority: CRITICAL** - This breaks the page. Fix before continuing.
