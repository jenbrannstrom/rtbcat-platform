# Phase 8.2: Quick Reference & Troubleshooting

**Last Updated:** November 30, 2025  
**For:** Claude in VSCode working on frontend

---

## 🎯 Quick Goals Summary

1. Add sort dropdown (4 periods)
2. Show performance badges on cards
3. Add tier filter (high/med/low/none)
4. Maintain smooth performance
5. Handle loading/error states gracefully

---

## 📝 Quick Checklist

**Before Starting:**
- [ ] Backend API is running on port 8000
- [ ] Can access http://localhost:8000/docs
- [ ] Phase 8.1 is complete (performance endpoints exist)
- [ ] npm run dev works without errors

**During Development:**
- [ ] TypeScript types created first
- [ ] API functions tested in isolation
- [ ] Components built incrementally
- [ ] Test in Chrome DevTools as you go
- [ ] Check virtual scrolling performance

**Before Committing:**
- [ ] No TypeScript errors
- [ ] No console errors
- [ ] Works on mobile (Chrome DevTools device mode)
- [ ] Loading states smooth
- [ ] Error states friendly
- [ ] Screenshot taken for documentation

---

## 🚨 Common Issues & Solutions

### Issue 1: "Cannot find module '@/types/performance'"

**Cause:** TypeScript path alias not configured

**Solution:**
```json
// tsconfig.json
{
  "compilerOptions": {
    "paths": {
      "@/*": ["./src/*"]
    }
  }
}
```

Or use relative imports:
```typescript
import { Period } from '../types/performance';
```

---

### Issue 2: API returns 404 for performance metrics

**Cause:** Creative has no performance data yet

**Solution:**
```typescript
// Handle 404 gracefully
try {
  const response = await fetch(`/api/performance/metrics/${id}`);
  if (response.status === 404) {
    return null; // No data, not an error
  }
  // ... handle other statuses
} catch (err) {
  // Network error
}
```

**Display:**
```typescript
{!metrics && (
  <div className="text-xs text-gray-400">No data</div>
)}
```

---

### Issue 3: Virtual scrolling breaks after adding performance data

**Cause:** Cards changing height, or expensive calculations in render

**Solutions:**

1. **Fixed card height:**
```typescript
// CreativeCard.tsx
<div className="h-[400px] ...">
  {/* Content */}
</div>
```

2. **Memoize calculations:**
```typescript
const sortedCreatives = useMemo(() => {
  // Expensive sorting
}, [creatives, performanceData]);
```

3. **Use React.memo:**
```typescript
export const CreativeCard = React.memo(({ creative }) => {
  // Component
});
```

---

### Issue 4: Performance data loads slowly (>2 seconds)

**Cause:** Making 652 individual API calls instead of batch

**Solution:**
```typescript
// ❌ Don't do this
for (const creative of creatives) {
  await fetchPerformanceMetrics(creative.id);
}

// ✅ Do this
const batchResponse = await fetchBatchPerformanceMetrics(
  creatives.map(c => c.id),
  period
);
```

---

### Issue 5: Changing period doesn't update the display

**Cause:** Missing dependency in useEffect

**Solution:**
```typescript
useEffect(() => {
  loadPerformanceData();
}, [sortPeriod]); // ← Add sortPeriod dependency
```

---

### Issue 6: "Spend" shows as "$NaN" or "$undefined"

**Cause:** Missing null/undefined check

**Solution:**
```typescript
const formatCurrency = (amount: number | null | undefined): string => {
  if (amount === null || amount === undefined) {
    return 'N/A';
  }
  // ... format
};
```

---

### Issue 7: Sort dropdown doesn't disable during loading

**Cause:** Not passing disabled prop

**Solution:**
```typescript
<SortDropdown
  value={sortPeriod}
  onChange={setSortPeriod}
  disabled={performanceLoading} // ← Add this
/>
```

---

### Issue 8: Page re-renders constantly

**Cause:** Creating new objects/arrays in render

**Solutions:**

1. **Move static data outside component:**
```typescript
// ❌ Don't do this
function Component() {
  const options = ['1d', '7d', '30d'];
}

// ✅ Do this
const OPTIONS = ['1d', '7d', '30d'];
function Component() {
  // ...
}
```

2. **Use useMemo for derived state:**
```typescript
const filteredData = useMemo(() => {
  return data.filter(/* ... */);
}, [data]);
```

---

### Issue 9: CORS error when calling API

**Cause:** API not configured for CORS

**Quick fix (development only):**
```typescript
// Use proxy in next.config.js
module.exports = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/api/:path*',
      },
    ];
  },
};
```

**Proper fix:** Backend should set CORS headers (handled in Phase 8.1)

---

### Issue 10: TypeScript errors for unknown properties

**Cause:** Type definitions don't match API response

**Solution:**
```typescript
// Add debug logging
const data = await response.json();
console.log('API response:', data);

// Update types to match
interface PerformanceMetrics {
  // Add missing fields
  creative_id: number;
  // ...
}
```

---

## 🔍 Debugging Commands

### Check if backend is running
```bash
curl http://localhost:8000/health
# Should return: {"status": "ok"}
```

### Test performance API endpoint
```bash
# Single creative
curl http://localhost:8000/api/performance/metrics/79783?period=7d

# Batch
curl -X POST http://localhost:8000/api/performance/metrics/batch \
  -H "Content-Type: application/json" \
  -d '{"creative_ids": [79783, 79784], "period": "7d"}'
```

### Check database
```bash
sqlite3 ~/.rtbcat/rtbcat.db

SELECT COUNT(*) FROM performance_metrics;
SELECT * FROM performance_metrics LIMIT 5;

.exit
```

### Monitor API calls in browser
```javascript
// In browser console
performance.getEntriesByType('resource')
  .filter(r => r.name.includes('performance'))
  .forEach(r => console.log(r.name, r.duration));
```

---

## 📊 Performance Benchmarks

**Target metrics:**
- Initial page load: <1 second
- Performance data fetch: <500ms
- Sort change: <200ms
- Scroll performance: 60fps (16.7ms per frame)

**How to measure:**

1. **Page load:**
```javascript
// In browser console
performance.timing.loadEventEnd - performance.timing.navigationStart
```

2. **Component render time:**
- Use React DevTools Profiler
- Record while changing sort period
- Look for components >16ms

3. **Scroll performance:**
- Chrome DevTools > Performance
- Record while scrolling
- Check for dropped frames (red bars)

---

## 🎨 Styling Quick Reference

### Tailwind Colors for Performance

```typescript
// Spend tiers
high:   'bg-green-100 text-green-800'
medium: 'bg-blue-100 text-blue-800'
low:    'bg-gray-100 text-gray-700'
none:   'bg-gray-50 text-gray-400'

// CPC colors
excellent: 'text-green-600'  // <$0.30
good:      'text-yellow-600' // $0.30-$0.60
poor:      'text-red-600'    // >$0.60

// Trend colors
up:      'text-green-600'
down:    'text-red-600'
stable:  'text-gray-500'
```

### Component Spacing

```typescript
// Card padding
p-4  // Main card padding

// Badge spacing
space-y-2  // Vertical spacing between metrics
gap-2      // Horizontal spacing in flex

// Grid layout
grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6
```

---

## 🧪 Testing Scenarios

### Scenario 1: No performance data
```
Expected: "No data" badge shows
Test: Fresh database, no CSV imported
```

### Scenario 2: Partial data
```
Expected: Some cards have badges, others show "No data"
Test: Import CSV with only 100 creative IDs
```

### Scenario 3: All have data
```
Expected: All cards show performance badges
Test: Import CSV with all 652 creative IDs
```

### Scenario 4: Change period
```
Expected: Badges update with new spend values
Test: Switch from "7d" to "30d"
```

### Scenario 5: Tier filter
```
Expected: Only creatives in selected tier visible
Test: Click "High Spend" - should show ~130 creatives (top 20%)
```

---

## 📦 File Locations Reference

```
dashboard/
├── pages/
│   └── creatives.tsx              # UPDATE: Main page
├── components/
│   ├── CreativeCard.tsx           # UPDATE: Add performance section
│   ├── PerformanceBadge.tsx       # NEW: Create this
│   ├── SortDropdown.tsx           # NEW: Create this
│   └── TierFilter.tsx             # NEW: Create this
├── lib/
│   ├── api.ts                     # UPDATE: Add performance functions
│   └── performance.ts             # NEW: Create this (calculations)
├── types/
│   └── performance.ts             # NEW: Create this (TypeScript types)
└── styles/
    └── globals.css                # No changes needed
```

---

## 🔗 API Endpoints Reference

### GET /api/performance/metrics/{creative_id}

**Parameters:**
- `creative_id`: number (path)
- `period`: "1d" | "7d" | "30d" | "all" (query)

**Response:**
```json
{
  "creative_id": 79783,
  "period": "7d",
  "spend": 1234.56,
  "impressions": 50000,
  "clicks": 2500,
  "cpc": 0.45,
  "cpm": 2.20,
  "ctr": 0.05,
  "top_geo": "BR",
  "geo_percentage": 45.2,
  "trend": 15.3
}
```

**Status codes:**
- 200: Success
- 404: No data for this creative/period
- 400: Invalid period
- 500: Server error

---

### POST /api/performance/metrics/batch

**Request body:**
```json
{
  "creative_ids": [79783, 79784, 79785],
  "period": "7d"
}
```

**Response:**
```json
{
  "data": [
    { "creative_id": 79783, "spend": 1234.56, ... },
    { "creative_id": 79784, "spend": 567.89, ... }
  ],
  "missing": [79785],
  "timestamp": "2025-11-30T12:00:00Z"
}
```

---

## 💡 Pro Tips

### 1. Start Simple
Build in this order:
1. Types first
2. API functions (test in console)
3. Simple dropdown (hardcoded data)
4. Connect to real API
5. Add loading states
6. Add error handling
7. Polish UI

### 2. Test as You Go
Don't wait until the end to test. After each component:
- Check in browser
- Test edge cases
- Verify performance
- Fix issues immediately

### 3. Use Browser DevTools
- Console: Check for errors
- Network: Verify API calls
- Elements: Inspect DOM/CSS
- Performance: Check render times
- React DevTools: Component hierarchy

### 4. Commit Often
```bash
git add .
git commit -m "feat: add sort dropdown"
# Continue working
git commit -m "feat: add performance badges"
# Continue working
git commit -m "feat: add tier filter"
```

### 5. Progressive Enhancement
The page should work at every stage:
1. Works with no performance data ✓
2. Works with some performance data ✓
3. Works with all performance data ✓
4. Gracefully handles errors ✓

---

## 🎉 Success Indicators

**You're done when:**
- [ ] All 4 periods work in dropdown
- [ ] Performance badges show on cards
- [ ] Tier filter works correctly
- [ ] Page loads in <1 second
- [ ] No TypeScript errors
- [ ] No console errors
- [ ] Works on mobile
- [ ] Screenshot looks good
- [ ] You're proud of the code

---

## 📞 Need Help?

**Check these first:**
1. This quick reference
2. PHASE_8.2_PROMPT.md (main requirements)
3. PHASE_8.2_CODE_EXAMPLES.md (implementation examples)
4. http://localhost:8000/docs (API documentation)

**Still stuck?**
- Add detailed console.log statements
- Check Network tab in DevTools
- Simplify to minimal test case
- Ask Jen for backend help if API issues

---

**Remember:** Perfect is the enemy of done. Ship a working version first, then iterate! 🚀
