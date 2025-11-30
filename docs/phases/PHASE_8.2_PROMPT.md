# Phase 8.2: Update Creatives Page with "Sort by Spend"

**Project:** RTB.cat Creative Intelligence Platform  
**Task:** Frontend UI updates for performance-based sorting  
**Developer:** Claude in VSCode  
**Prerequisites:** Phase 8.1 complete (backend API endpoints ready)  
**Location:** `/home/jen/Documents/rtbcat-platform/dashboard/`

---

## 🎯 Objective

Transform the creatives page from a simple catalog into a **performance-driven dashboard** by adding:
1. Sort by spend dropdown (yesterday, 7d, 30d, all-time)
2. Performance badges on creative cards (spend, CPC, CPM)
3. Performance-based filtering (high/medium/low spend tiers)
4. Top geography display
5. Smooth loading states and error handling

**Current State:** Creatives sorted by ID (not useful)  
**Target State:** Creatives sorted by spend with visual performance indicators

---

## 📋 Requirements

### 1. Sort by Spend Dropdown

**Location:** Top of creatives page, next to existing filters

**Options:**
- Yesterday (last 24 hours)
- Last 7 days (default)
- Last 30 days
- All time

**Behavior:**
- Fetches performance data from API: `GET /api/performance/metrics/{creative_id}?period={period}`
- Re-sorts creatives array by total spend for selected period
- Maintains virtual scrolling performance
- Shows loading state during re-sort
- Persists selection in URL query params (optional but nice)

**Visual Design:**
```
[Sort by: Last 7 days ▼]  [Filter: All ▼]  [Search...]
```

### 2. Performance Badges on Creative Cards

**Update the creative card component to show:**

```
┌─────────────────────────────────────┐
│  [Creative Thumbnail]               │
│                                     │
│  ID: 79783                          │
│  💰 $1,234  (7d spend)             │
│  📊 CPC: $0.45  CPM: $2.20         │
│  🌍 Top: Brazil (45%)              │
│  ↗️ +15%  (trend vs prev period)   │
└─────────────────────────────────────┘
```

**Badge Requirements:**
- Show spend badge in **bold** if >$1,000 in period
- Color-code CPC: Green (<$0.30), Yellow ($0.30-$0.60), Red (>$0.60)
- Show top geography only if >30% of traffic
- Trend indicator: ↗️ increase, ↘️ decrease, → stable (±5%)
- Handle missing data gracefully (show "No data" badge)

### 3. Performance Tier Filtering

**Add filter dropdown:**
- High Spend (top 20% of creatives by spend)
- Medium Spend (middle 60%)
- Low Spend (bottom 20%)
- No Data (creatives without performance metrics)

**Implementation:**
- Calculate percentiles client-side after fetching data
- Update filter instantly (no API call needed)
- Combine with existing filters (if any)

### 4. Loading States

**Three loading states to handle:**

1. **Initial page load:**
   - Show skeleton cards
   - Load creatives first (fast)
   - Then fetch performance data (slower)
   - Progressive enhancement: cards appear, then badges populate

2. **Changing sort period:**
   - Show spinner on dropdown
   - Disable dropdown during fetch
   - Smooth transition when data arrives

3. **Error states:**
   - API timeout: "Performance data unavailable"
   - No data for period: "No activity in selected period"
   - Network error: Retry button

### 5. Empty States

**Scenarios to handle:**

1. **No creatives:** (existing, should still work)
2. **Creatives but no performance data:** 
   ```
   ℹ️ No performance data yet
   Upload CSV data to see spend metrics
   [Import Performance Data] button
   ```
3. **No activity in selected period:**
   ```
   No spend recorded for Last 30 days
   Try selecting "All time" or import newer data
   ```

---

## 🛠️ Technical Implementation

### File Changes Required

1. **`/dashboard/pages/creatives.tsx`** (or similar)
   - Add sort dropdown state
   - Add period selection state
   - Fetch performance data
   - Calculate spend-based sort order
   - Add tier filter logic

2. **`/dashboard/components/CreativeCard.tsx`** (or similar)
   - Add performance badges section
   - Add trend indicator
   - Add conditional styling based on metrics
   - Handle missing data

3. **`/dashboard/types/performance.ts`** (create if needed)
   ```typescript
   interface PerformanceMetrics {
     creative_id: number;
     period: string; // "1d" | "7d" | "30d" | "all"
     spend: number;
     impressions: number;
     clicks: number;
     cpc: number;
     cpm: number;
     top_geo: string;
     geo_percentage: number;
     trend: number; // percentage change vs previous period
   }
   ```

4. **`/dashboard/lib/api.ts`** (or similar)
   - Add `fetchPerformanceMetrics(creativeId, period)` function
   - Add `fetchBatchPerformanceMetrics(creativeIds, period)` for efficiency
   - Add error handling

### API Integration

**Endpoint:** `GET /api/performance/metrics/{creative_id}?period={period}`

**Response format:**
```json
{
  "creative_id": 79783,
  "period": "7d",
  "spend": 1234.56,
  "impressions": 50000,
  "clicks": 2500,
  "cpc": 0.45,
  "cpm": 2.20,
  "top_geo": "BR",
  "geo_percentage": 45.2,
  "trend": 15.3
}
```

**Batch endpoint (if available):** `POST /api/performance/metrics/batch`
```json
{
  "creative_ids": [79783, 79784, 79785],
  "period": "7d"
}
```

**Error handling:**
- 404: Creative has no performance data
- 400: Invalid period
- 500: Database error
- Network timeout: Show retry

### Performance Optimization

**Critical: Virtual scrolling must remain smooth**

**Strategy:**
1. Fetch performance data **after** initial render
2. Use **batch API** if available (1 call for all 652 creatives)
3. Cache performance data in state (don't refetch on scroll)
4. Only re-fetch when period changes
5. Use React.memo for creative cards
6. Debounce filter changes

**Target metrics:**
- Initial page load: <1 second
- Sort change: <200ms
- Scroll performance: 60fps maintained
- Performance data load: <500ms for 652 creatives

### State Management

**Suggested state structure:**
```typescript
const [creatives, setCreatives] = useState([]);
const [performanceData, setPerformanceData] = useState({});
const [sortPeriod, setSortPeriod] = useState('7d');
const [tierFilter, setTierFilter] = useState('all');
const [loading, setLoading] = useState(false);
const [error, setError] = useState(null);

// Derived state
const sortedCreatives = useMemo(() => {
  return creatives
    .map(c => ({
      ...c,
      perf: performanceData[c.id]
    }))
    .sort((a, b) => (b.perf?.spend || 0) - (a.perf?.spend || 0))
    .filter(c => matchesTierFilter(c, tierFilter));
}, [creatives, performanceData, tierFilter]);
```

---

## 🎨 UI/UX Guidelines

### Visual Hierarchy

1. **Most important:** Spend (largest, bold)
2. **Secondary:** CPC/CPM (smaller, inline)
3. **Tertiary:** Geography, trend (subtle)

### Color Palette

**Performance tiers:**
- High: Green (#10B981) - top performers
- Medium: Blue (#3B82F6) - average
- Low: Gray (#6B7280) - underperformers
- No data: Light gray (#D1D5DB) - dashed border

**CPC color coding:**
- Excellent (<$0.30): Green
- Good ($0.30-$0.60): Yellow
- Poor (>$0.60): Red

### Responsive Design

**Desktop (>1024px):**
- Show all badges inline
- 3-4 cards per row

**Tablet (768-1024px):**
- Compress badges slightly
- 2-3 cards per row

**Mobile (<768px):**
- Stack badges vertically
- 1 card per row
- Collapse less important metrics

---

## ✅ Testing Checklist

### Functional Tests

- [ ] Sort dropdown changes creative order
- [ ] Performance badges appear on cards with data
- [ ] "No data" badge shows for creatives without metrics
- [ ] Tier filter works correctly
- [ ] Trend indicators show correctly (up/down/stable)
- [ ] Top geography displays when >30% traffic
- [ ] Empty state shows when no performance data exists

### Performance Tests

- [ ] Initial page load <1 second
- [ ] Sort change <200ms
- [ ] Virtual scrolling smooth (60fps)
- [ ] No memory leaks (check Chrome DevTools)
- [ ] Performance data fetches once per period change

### Edge Cases

- [ ] Handle 0 creatives
- [ ] Handle creatives with no performance data
- [ ] Handle API timeout gracefully
- [ ] Handle invalid period selection
- [ ] Handle extremely large spend values ($1M+)
- [ ] Handle missing geography data

### Browser Compatibility

- [ ] Chrome (latest)
- [ ] Firefox (latest)
- [ ] Safari (latest)
- [ ] Mobile Safari (iOS)
- [ ] Mobile Chrome (Android)

---

## 🚨 Common Pitfalls to Avoid

1. **Don't fetch performance data in the render loop**
   - Use useEffect with proper dependencies
   - Cache results in state

2. **Don't block initial render waiting for performance data**
   - Show creatives first, then add badges
   - Progressive enhancement

3. **Don't sort on every keystroke**
   - Debounce filter inputs
   - Only sort on period change

4. **Don't forget error boundaries**
   - Wrap performance features in error boundary
   - Fallback to non-performance view if needed

5. **Don't sacrifice virtual scrolling performance**
   - Measure before and after
   - Use React DevTools Profiler
   - Keep cards lightweight

---

## 📖 Example Implementation Snippet

```typescript
// Fetch performance data after creatives load
useEffect(() => {
  if (creatives.length === 0) return;
  
  const fetchPerformanceData = async () => {
    setLoading(true);
    try {
      // Batch fetch all performance data
      const response = await fetch(
        `/api/performance/metrics/batch`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            creative_ids: creatives.map(c => c.id),
            period: sortPeriod
          })
        }
      );
      
      if (!response.ok) throw new Error('Failed to fetch');
      
      const data = await response.json();
      
      // Convert array to lookup object
      const perfMap = {};
      data.forEach(p => {
        perfMap[p.creative_id] = p;
      });
      
      setPerformanceData(perfMap);
    } catch (err) {
      console.error('Performance data fetch failed:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  
  fetchPerformanceData();
}, [creatives, sortPeriod]);

// Sort creatives by spend
const sortedCreatives = useMemo(() => {
  return [...creatives].sort((a, b) => {
    const spendA = performanceData[a.id]?.spend || 0;
    const spendB = performanceData[b.id]?.spend || 0;
    return spendB - spendA; // Descending
  });
}, [creatives, performanceData]);
```

---

## 🎯 Success Criteria

**Phase 8.2 is complete when:**

1. ✅ User can select sort period (yesterday/7d/30d/all)
2. ✅ Creatives re-order by spend correctly
3. ✅ Performance badges appear on all cards with data
4. ✅ Tier filter works (high/medium/low/no data)
5. ✅ Loading states are smooth and non-blocking
6. ✅ Error states are handled gracefully
7. ✅ Virtual scrolling performance maintained (<100ms per frame)
8. ✅ No console errors in production
9. ✅ Works on mobile and desktop
10. ✅ Code is clean, typed, and well-commented

---

## 📦 Deliverables

1. Updated `/dashboard/pages/creatives.tsx`
2. Updated `/dashboard/components/CreativeCard.tsx`
3. New `/dashboard/types/performance.ts`
4. Updated `/dashboard/lib/api.ts`
5. Screenshot of new UI
6. Brief testing notes

---

## 🔄 Next Steps

**After Phase 8.2:**
- Phase 8.3: Performance import UI (upload CSV via dashboard)
- Phase 9: AI campaign clustering (group creatives automatically)
- Phase 10: Opportunity detection (find profit pockets)

---

## 📞 Support

**Backend API should be running on:** `http://localhost:8000`  
**API Docs:** `http://localhost:8000/docs`  
**Database:** `~/.rtbcat/rtbcat.db`

**Questions about backend endpoints?** Check Phase 8.1 documentation or API docs.

---

**Good luck! Focus on progressive enhancement and smooth UX. The creatives page should work perfectly without performance data, then get better when data is available.**
