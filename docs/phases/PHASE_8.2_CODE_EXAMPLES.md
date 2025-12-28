# Phase 8.2 Supplement: Code Examples & React Patterns

**Companion to:** PHASE_8.2_PROMPT.md  
**Purpose:** Detailed implementation examples and best practices

---

## 📁 Component Structure

### Recommended File Organization

```
dashboard/
├── pages/
│   └── creatives.tsx              # Main page (updated)
├── components/
│   ├── CreativeCard.tsx           # Card component (updated)
│   ├── PerformanceBadge.tsx       # NEW: Performance metrics display
│   ├── SortDropdown.tsx           # NEW: Period selector
│   └── TierFilter.tsx             # NEW: Performance tier filter
├── lib/
│   ├── api.ts                     # API functions (updated)
│   └── performance.ts             # NEW: Performance calculations
└── types/
    └── performance.ts             # NEW: TypeScript types
```

---

## 🔧 TypeScript Types

### `/dashboard/types/performance.ts`

```typescript
export type Period = '1d' | '7d' | '30d' | 'all';

export interface PerformanceMetrics {
  creative_id: number;
  period: Period;
  spend: number;
  impressions: number;
  clicks: number;
  cpc: number;
  cpm: number;
  ctr: number; // Click-through rate
  top_geo: string | null; // ISO country code
  geo_percentage: number | null;
  trend: number | null; // Percentage change vs previous period
  updated_at: string; // ISO timestamp
}

export interface PerformanceBatch {
  creative_ids: number[];
  period: Period;
}

export interface PerformanceBatchResponse {
  data: PerformanceMetrics[];
  missing: number[]; // Creative IDs with no data
  timestamp: string;
}

export type PerformanceTier = 'high' | 'medium' | 'low' | 'none';

export interface CreativeWithPerformance {
  id: number;
  // ... existing creative fields
  performance?: PerformanceMetrics;
  performanceTier?: PerformanceTier;
}
```

---

## 🎨 Component Examples

### 1. Sort Dropdown Component

**`/dashboard/components/SortDropdown.tsx`**

```typescript
import React from 'react';
import { Period } from '@/types/performance';

interface SortDropdownProps {
  value: Period;
  onChange: (period: Period) => void;
  disabled?: boolean;
}

const PERIOD_LABELS: Record<Period, string> = {
  '1d': 'Yesterday',
  '7d': 'Last 7 days',
  '30d': 'Last 30 days',
  'all': 'All time'
};

export const SortDropdown: React.FC<SortDropdownProps> = ({ 
  value, 
  onChange, 
  disabled = false 
}) => {
  return (
    <div className="inline-flex items-center gap-2">
      <label 
        htmlFor="sort-period" 
        className="text-sm font-medium text-gray-700"
      >
        Sort by:
      </label>
      <select
        id="sort-period"
        value={value}
        onChange={(e) => onChange(e.target.value as Period)}
        disabled={disabled}
        className="px-3 py-2 border border-gray-300 rounded-md shadow-sm 
                   focus:ring-2 focus:ring-blue-500 focus:border-blue-500
                   disabled:bg-gray-100 disabled:cursor-not-allowed
                   text-sm"
      >
        {Object.entries(PERIOD_LABELS).map(([period, label]) => (
          <option key={period} value={period}>
            {label}
          </option>
        ))}
      </select>
    </div>
  );
};
```

---

### 2. Performance Badge Component

**`/dashboard/components/PerformanceBadge.tsx`**

```typescript
import React from 'react';
import { PerformanceMetrics } from '@/types/performance';

interface PerformanceBadgeProps {
  metrics?: PerformanceMetrics;
  compact?: boolean;
}

const formatCurrency = (amount: number): string => {
  if (amount >= 1000) {
    return `$${(amount / 1000).toFixed(1)}k`;
  }
  return `$${amount.toFixed(0)}`;
};

const formatNumber = (num: number): string => {
  if (num >= 1000000) {
    return `${(num / 1000000).toFixed(1)}M`;
  }
  if (num >= 1000) {
    return `${(num / 1000).toFixed(1)}k`;
  }
  return num.toFixed(0);
};

const getCPCColor = (cpc: number): string => {
  if (cpc < 0.30) return 'text-green-600';
  if (cpc < 0.60) return 'text-yellow-600';
  return 'text-red-600';
};

const getTrendIcon = (trend: number | null): string => {
  if (!trend || Math.abs(trend) < 5) return '→';
  return trend > 0 ? '↗️' : '↘️';
};

const getTrendColor = (trend: number | null): string => {
  if (!trend || Math.abs(trend) < 5) return 'text-gray-500';
  return trend > 0 ? 'text-green-600' : 'text-red-600';
};

export const PerformanceBadge: React.FC<PerformanceBadgeProps> = ({ 
  metrics,
  compact = false 
}) => {
  if (!metrics) {
    return (
      <div className="text-xs text-gray-400 italic border border-dashed 
                      border-gray-300 rounded px-2 py-1">
        No data
      </div>
    );
  }

  if (compact) {
    return (
      <div className="text-xs space-y-1">
        <div className="font-semibold text-gray-900">
          💰 {formatCurrency(metrics.spend)}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-2 text-xs">
      {/* Spend - most prominent */}
      <div className="flex items-center justify-between">
        <span className="text-gray-600">Spend</span>
        <span className={`font-bold text-sm ${
          metrics.spend > 1000 ? 'text-blue-600' : 'text-gray-900'
        }`}>
          💰 {formatCurrency(metrics.spend)}
        </span>
      </div>

      {/* CPC and CPM */}
      <div className="flex items-center justify-between text-xs">
        <span className="text-gray-600">CPC</span>
        <span className={`font-medium ${getCPCColor(metrics.cpc)}`}>
          ${metrics.cpc.toFixed(2)}
        </span>
      </div>

      <div className="flex items-center justify-between text-xs">
        <span className="text-gray-600">CPM</span>
        <span className="font-medium text-gray-700">
          ${metrics.cpm.toFixed(2)}
        </span>
      </div>

      {/* CTR */}
      <div className="flex items-center justify-between text-xs">
        <span className="text-gray-600">CTR</span>
        <span className="font-medium text-gray-700">
          {(metrics.ctr * 100).toFixed(2)}%
        </span>
      </div>

      {/* Top Geography (if significant) */}
      {metrics.top_geo && metrics.geo_percentage && metrics.geo_percentage > 30 && (
        <div className="flex items-center justify-between text-xs">
          <span className="text-gray-600">Top Geo</span>
          <span className="font-medium text-gray-900">
            🌍 {metrics.top_geo} ({metrics.geo_percentage.toFixed(0)}%)
          </span>
        </div>
      )}

      {/* Trend (if available) */}
      {metrics.trend !== null && (
        <div className="flex items-center justify-between text-xs">
          <span className="text-gray-600">Trend</span>
          <span className={`font-medium ${getTrendColor(metrics.trend)}`}>
            {getTrendIcon(metrics.trend)} {Math.abs(metrics.trend).toFixed(0)}%
          </span>
        </div>
      )}

      {/* Impressions & Clicks */}
      <div className="pt-2 border-t border-gray-200 text-xs text-gray-500">
        {formatNumber(metrics.impressions)} imp · {formatNumber(metrics.clicks)} clicks
      </div>
    </div>
  );
};
```

---

### 3. Tier Filter Component

**`/dashboard/components/TierFilter.tsx`**

```typescript
import React from 'react';
import { PerformanceTier } from '@/types/performance';

interface TierFilterProps {
  value: PerformanceTier | 'all';
  onChange: (tier: PerformanceTier | 'all') => void;
  counts?: Record<PerformanceTier | 'all', number>;
}

const TIER_LABELS: Record<PerformanceTier | 'all', string> = {
  all: 'All',
  high: 'High Spend',
  medium: 'Medium Spend',
  low: 'Low Spend',
  none: 'No Data'
};

const TIER_COLORS: Record<PerformanceTier | 'all', string> = {
  all: 'bg-gray-100 text-gray-800',
  high: 'bg-green-100 text-green-800',
  medium: 'bg-blue-100 text-blue-800',
  low: 'bg-gray-100 text-gray-700',
  none: 'bg-gray-50 text-gray-400'
};

export const TierFilter: React.FC<TierFilterProps> = ({ 
  value, 
  onChange, 
  counts 
}) => {
  return (
    <div className="inline-flex items-center gap-2">
      <label className="text-sm font-medium text-gray-700">
        Filter:
      </label>
      <div className="inline-flex rounded-md shadow-sm" role="group">
        {Object.entries(TIER_LABELS).map(([tier, label]) => {
          const isActive = value === tier;
          const count = counts?.[tier as PerformanceTier | 'all'];
          
          return (
            <button
              key={tier}
              type="button"
              onClick={() => onChange(tier as PerformanceTier | 'all')}
              className={`
                px-3 py-2 text-xs font-medium
                first:rounded-l-md last:rounded-r-md
                border border-gray-300
                ${isActive 
                  ? TIER_COLORS[tier as PerformanceTier | 'all'] + ' ring-2 ring-blue-500' 
                  : 'bg-white text-gray-700 hover:bg-gray-50'
                }
                transition-colors
              `}
            >
              {label}
              {count !== undefined && (
                <span className="ml-1 text-xs opacity-70">
                  ({count})
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
};
```

---

### 4. Updated Creative Card

**`/dashboard/components/CreativeCard.tsx`** (additions only)

```typescript
import { PerformanceBadge } from './PerformanceBadge';
import { CreativeWithPerformance } from '@/types/performance';

interface CreativeCardProps {
  creative: CreativeWithPerformance;
  onClick?: () => void;
}

export const CreativeCard: React.FC<CreativeCardProps> = ({ 
  creative, 
  onClick 
}) => {
  return (
    <div 
      className="border rounded-lg p-4 hover:shadow-lg transition-shadow cursor-pointer"
      onClick={onClick}
    >
      {/* Existing thumbnail and basic info */}
      <img 
        src={creative.thumbnail_url} 
        alt={`Creative ${creative.id}`}
        className="w-full h-48 object-cover rounded"
      />
      
      <div className="mt-3">
        <div className="text-sm text-gray-600">
          ID: {creative.id}
        </div>
        
        {/* NEW: Performance Badge */}
        <div className="mt-3">
          <PerformanceBadge metrics={creative.performance} />
        </div>
        
        {/* Existing info (size, type, etc.) */}
      </div>
    </div>
  );
};
```

---

## 🔌 API Integration

### `/dashboard/lib/api.ts`

```typescript
import { 
  Period, 
  PerformanceMetrics, 
  PerformanceBatch,
  PerformanceBatchResponse 
} from '@/types/performance';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/**
 * Fetch performance metrics for a single creative
 */
export async function fetchPerformanceMetrics(
  creativeId: number,
  period: Period = '7d'
): Promise<PerformanceMetrics | null> {
  try {
    const response = await fetch(
      `${API_BASE}/api/performance/metrics/${creativeId}?period=${period}`
    );
    
    if (response.status === 404) {
      return null; // No data for this creative
    }
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('Failed to fetch performance metrics:', error);
    throw error;
  }
}

/**
 * Fetch performance metrics for multiple creatives (batch)
 * Much more efficient than individual calls
 */
export async function fetchBatchPerformanceMetrics(
  creativeIds: number[],
  period: Period = '7d'
): Promise<PerformanceBatchResponse> {
  try {
    const response = await fetch(
      `${API_BASE}/api/performance/metrics/batch`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          creative_ids: creativeIds,
          period: period
        } as PerformanceBatch)
      }
    );
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('Failed to fetch batch performance metrics:', error);
    throw error;
  }
}
```

---

## 🧮 Performance Calculations

### `/dashboard/lib/performance.ts`

```typescript
import { 
  CreativeWithPerformance, 
  PerformanceTier,
  PerformanceMetrics 
} from '@/types/performance';

/**
 * Calculate performance tier based on spend percentiles
 */
export function calculatePerformanceTiers(
  creatives: CreativeWithPerformance[]
): CreativeWithPerformance[] {
  // Separate creatives with and without performance data
  const withData = creatives.filter(c => c.performance);
  const withoutData = creatives.filter(c => !c.performance);
  
  if (withData.length === 0) {
    return creatives.map(c => ({ ...c, performanceTier: 'none' }));
  }
  
  // Sort by spend
  const sorted = [...withData].sort((a, b) => 
    (b.performance!.spend) - (a.performance!.spend)
  );
  
  // Calculate percentile thresholds
  const p20 = Math.floor(sorted.length * 0.2);
  const p80 = Math.floor(sorted.length * 0.8);
  
  // Assign tiers
  const tiered = sorted.map((creative, index) => {
    let tier: PerformanceTier;
    if (index < p20) {
      tier = 'high';
    } else if (index < p80) {
      tier = 'medium';
    } else {
      tier = 'low';
    }
    
    return { ...creative, performanceTier: tier };
  });
  
  // Add back creatives without data
  const withoutDataTiered = withoutData.map(c => ({
    ...c,
    performanceTier: 'none' as PerformanceTier
  }));
  
  return [...tiered, ...withoutDataTiered];
}

/**
 * Filter creatives by performance tier
 */
export function filterByTier(
  creatives: CreativeWithPerformance[],
  tier: PerformanceTier | 'all'
): CreativeWithPerformance[] {
  if (tier === 'all') return creatives;
  return creatives.filter(c => c.performanceTier === tier);
}

/**
 * Get tier counts for UI
 */
export function getTierCounts(
  creatives: CreativeWithPerformance[]
): Record<PerformanceTier | 'all', number> {
  const counts: Record<PerformanceTier | 'all', number> = {
    all: creatives.length,
    high: 0,
    medium: 0,
    low: 0,
    none: 0
  };
  
  creatives.forEach(c => {
    if (c.performanceTier) {
      counts[c.performanceTier]++;
    }
  });
  
  return counts;
}
```

---

## 📄 Main Page Implementation

### `/dashboard/pages/creatives.tsx`

```typescript
import React, { useState, useEffect, useMemo } from 'react';
import { CreativeCard } from '@/components/CreativeCard';
import { SortDropdown } from '@/components/SortDropdown';
import { TierFilter } from '@/components/TierFilter';
import { 
  Period, 
  CreativeWithPerformance,
  PerformanceTier 
} from '@/types/performance';
import { 
  fetchCreatives, 
  fetchBatchPerformanceMetrics 
} from '@/lib/api';
import {
  calculatePerformanceTiers,
  filterByTier,
  getTierCounts
} from '@/lib/performance';

export default function CreativesPage() {
  // State
  const [creatives, setCreatives] = useState<CreativeWithPerformance[]>([]);
  const [performanceData, setPerformanceData] = useState<Record<number, any>>({});
  const [sortPeriod, setSortPeriod] = useState<Period>('7d');
  const [tierFilter, setTierFilter] = useState<PerformanceTier | 'all'>('all');
  const [loading, setLoading] = useState(true);
  const [performanceLoading, setPerformanceLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch creatives on mount
  useEffect(() => {
    const loadCreatives = async () => {
      try {
        setLoading(true);
        const data = await fetchCreatives();
        setCreatives(data);
      } catch (err) {
        setError('Failed to load creatives');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    loadCreatives();
  }, []);

  // Fetch performance data when period changes or creatives load
  useEffect(() => {
    if (creatives.length === 0) return;

    const loadPerformanceData = async () => {
      try {
        setPerformanceLoading(true);
        
        const batchResponse = await fetchBatchPerformanceMetrics(
          creatives.map(c => c.id),
          sortPeriod
        );

        // Convert array to lookup object
        const perfMap: Record<number, any> = {};
        batchResponse.data.forEach(p => {
          perfMap[p.creative_id] = p;
        });

        setPerformanceData(perfMap);
      } catch (err) {
        console.error('Failed to load performance data:', err);
        // Don't set error - performance data is optional
      } finally {
        setPerformanceLoading(false);
      }
    };

    loadPerformanceData();
  }, [creatives, sortPeriod]);

  // Merge creatives with performance data
  const creativesWithPerformance = useMemo(() => {
    return creatives.map(c => ({
      ...c,
      performance: performanceData[c.id]
    }));
  }, [creatives, performanceData]);

  // Calculate tiers
  const creativesWithTiers = useMemo(() => {
    return calculatePerformanceTiers(creativesWithPerformance);
  }, [creativesWithPerformance]);

  // Sort by spend (descending)
  const sortedCreatives = useMemo(() => {
    return [...creativesWithTiers].sort((a, b) => {
      const spendA = a.performance?.spend || 0;
      const spendB = b.performance?.spend || 0;
      return spendB - spendA;
    });
  }, [creativesWithTiers]);

  // Filter by tier
  const filteredCreatives = useMemo(() => {
    return filterByTier(sortedCreatives, tierFilter);
  }, [sortedCreatives, tierFilter]);

  // Tier counts for filter UI
  const tierCounts = useMemo(() => {
    return getTierCounts(creativesWithTiers);
  }, [creativesWithTiers]);

  // Loading state
  if (loading) {
    return (
      <div className="p-8">
        <div className="animate-pulse space-y-4">
          <div className="h-10 bg-gray-200 rounded w-1/4"></div>
          <div className="grid grid-cols-3 gap-4">
            {[...Array(9)].map((_, i) => (
              <div key={i} className="h-64 bg-gray-200 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="p-8">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-800">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Creatives</h1>
        <p className="text-gray-600 mt-1">
          {creatives.length} total creatives
        </p>
      </div>

      {/* Controls */}
      <div className="mb-6 flex items-center gap-4 flex-wrap">
        <SortDropdown
          value={sortPeriod}
          onChange={setSortPeriod}
          disabled={performanceLoading}
        />
        
        <TierFilter
          value={tierFilter}
          onChange={setTierFilter}
          counts={tierCounts}
        />

        {performanceLoading && (
          <div className="text-sm text-gray-500 flex items-center gap-2">
            <div className="animate-spin h-4 w-4 border-2 border-blue-500 
                            border-t-transparent rounded-full" />
            Loading performance data...
          </div>
        )}
      </div>

      {/* Empty state */}
      {filteredCreatives.length === 0 && (
        <div className="text-center py-12">
          <p className="text-gray-500">
            No creatives match the selected filters
          </p>
        </div>
      )}

      {/* Creatives grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredCreatives.map(creative => (
          <CreativeCard
            key={creative.id}
            creative={creative}
          />
        ))}
      </div>
    </div>
  );
}
```

---

## ⚡ Performance Optimization Tips

### 1. Memoization

```typescript
// ✅ Good - memoize expensive calculations
const sortedCreatives = useMemo(() => {
  return [...creatives].sort((a, b) => 
    (b.performance?.spend || 0) - (a.performance?.spend || 0)
  );
}, [creatives, performanceData]);

// ❌ Bad - sorts on every render
const sortedCreatives = [...creatives].sort(...);
```

### 2. Batch API Calls

```typescript
// ✅ Good - single batch call
await fetchBatchPerformanceMetrics(allCreativeIds, period);

// ❌ Bad - 652 individual calls
for (const id of allCreativeIds) {
  await fetchPerformanceMetrics(id, period);
}
```

### 3. Progressive Enhancement

```typescript
// ✅ Good - show creatives immediately, then add performance
useEffect(() => {
  loadCreatives(); // Fast, shows immediately
}, []);

useEffect(() => {
  if (creatives.length > 0) {
    loadPerformanceData(); // Slower, enhances existing UI
  }
}, [creatives]);

// ❌ Bad - wait for everything
useEffect(() => {
  await loadCreatives();
  await loadPerformanceData();
}, []);
```

### 4. React.memo for Cards

```typescript
// ✅ Good - prevent unnecessary re-renders
export const CreativeCard = React.memo<CreativeCardProps>(({ creative }) => {
  // Component code
}, (prevProps, nextProps) => {
  // Custom comparison
  return prevProps.creative.id === nextProps.creative.id &&
         prevProps.creative.performance === nextProps.creative.performance;
});
```

---

## 🐛 Debugging Tips

### Check if API is responding

```bash
# Test single creative
curl http://localhost:8000/api/performance/metrics/79783?period=7d

# Test batch
curl -X POST http://localhost:8000/api/performance/metrics/batch \
  -H "Content-Type: application/json" \
  -d '{"creative_ids": [79783, 79784], "period": "7d"}'
```

### Check React DevTools Profiler

1. Open Chrome DevTools
2. Go to "Profiler" tab
3. Click "Record"
4. Change sort period
5. Stop recording
6. Look for components that took >16ms to render

### Check Network Tab

1. Open Network tab in DevTools
2. Filter by "Fetch/XHR"
3. Verify batch API is called (not 652 individual calls)
4. Check response time (<500ms target)

---

## ✅ Final Checklist

- [ ] All TypeScript types defined
- [ ] API functions handle errors gracefully
- [ ] Components use React.memo where appropriate
- [ ] Performance data loads progressively
- [ ] Virtual scrolling still smooth
- [ ] No console errors
- [ ] Works on mobile
- [ ] Tier filter updates instantly
- [ ] Sort dropdown disables during load
- [ ] Empty states are friendly
- [ ] No data state shows helpful message

---

**This supplement provides production-ready code examples. Adapt as needed for your specific component structure and styling preferences.**
