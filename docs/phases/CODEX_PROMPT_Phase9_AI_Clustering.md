# ChatGPT Codex CLI Prompt: Phase 9 - AI Campaign Clustering

**Project:** RTB.cat Creative Intelligence Platform  
**Context:** Phase 8 complete. CSV import working, performance data flowing.  
**Goal:** Automatically group 652 creatives into meaningful campaigns using AI

---

## 🎯 The Problem

Right now, users see 652 individual creatives. That's overwhelming.

```
Current view:
├── Creative 131197
├── Creative 131198
├── Creative 131199
├── Creative 131200
├── Creative 131201
├── Creative 131202
├── ... (646 more)
└── 😵 User is lost
```

**What users actually need:**

```
Campaign view:
├── 🎮 Mobile Gaming Q4 Campaign (47 creatives)
│   ├── Spend: $12,450
│   ├── Best performer: Creative 131197
│   └── Top geos: US, UK, DE
├── 🎬 Video Streaming Promo (23 creatives)  
├── 🛒 E-commerce Holiday (31 creatives)
└── ... (~15-20 campaigns total)
```

---

## 🎯 Your Mission

Build an AI-powered clustering system that:
1. Analyzes creative metadata (URLs, filenames, visual similarity)
2. Groups creatives into logical campaigns
3. Generates descriptive campaign names
4. Shows campaign-level performance aggregates
5. Lets users manually adjust groupings

---

## 📋 Part 1: What Data Do We Have?

Each creative in the database has:

```sql
SELECT 
    id,
    buyer_creative_id,    -- External ID from SSP
    detected_url,         -- Landing page URL
    detected_domain,      -- Domain extracted from URL
    width, height,        -- Dimensions
    format,               -- 'image', 'video', 'html5'
    detected_advertiser,  -- Sometimes available
    file_hash,            -- For duplicate detection
    created_at
FROM creatives;
```

**Clustering signals:**
- **URL patterns:** `shop.example.com/holiday-sale` → Holiday campaign
- **Domain:** All `gaming-app.com` creatives → Same campaign
- **Dimensions:** 300x250 vs 728x90 → Different placements, maybe same campaign
- **Timing:** Creatives added same week → Likely same campaign
- **Performance correlation:** Creatives that perform similarly in same geos

---

## 📋 Part 2: Clustering Strategy

### Step 1: Rule-Based Pre-Clustering

Before using AI, apply obvious rules:

```python
# api/clustering/rule_based.py

def pre_cluster_creatives(creatives: list[dict]) -> dict[str, list[int]]:
    """
    Group creatives by obvious signals.
    Returns: {cluster_key: [creative_ids]}
    """
    clusters = defaultdict(list)
    
    for creative in creatives:
        # Primary: Group by domain
        if creative['detected_domain']:
            key = f"domain:{creative['detected_domain']}"
            clusters[key].append(creative['id'])
            continue
        
        # Secondary: Group by URL path patterns
        if creative['detected_url']:
            path_key = extract_campaign_hint(creative['detected_url'])
            if path_key:
                key = f"url:{path_key}"
                clusters[key].append(creative['id'])
                continue
        
        # Fallback: Group by week created
        week = creative['created_at'].isocalendar()[:2]
        key = f"week:{week[0]}-W{week[1]}"
        clusters[key].append(creative['id'])
    
    return clusters

def extract_campaign_hint(url: str) -> str | None:
    """
    Extract campaign-like patterns from URL.
    Examples:
      /holiday-sale-2025 → holiday-sale
      /promo/summer → summer
      /campaigns/abc123 → abc123
    """
    patterns = [
        r'/campaigns?/([^/]+)',
        r'/promo/([^/]+)',
        r'/(holiday|summer|winter|spring|black-friday|cyber-monday)[^/]*',
        r'/([a-z]+-sale)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url.lower())
        if match:
            return match.group(1)
    
    return None
```

### Step 2: AI-Powered Refinement

Use Claude API to:
1. Analyze pre-clusters
2. Merge similar clusters
3. Split clusters that seem unrelated
4. Generate descriptive names

```python
# api/clustering/ai_clusterer.py

import anthropic
from typing import List, Dict

class AICampaignClusterer:
    def __init__(self):
        self.client = anthropic.Anthropic()
    
    async def analyze_and_name_clusters(
        self, 
        clusters: Dict[str, List[dict]]
    ) -> List[dict]:
        """
        Use Claude to analyze clusters and generate campaign names.
        """
        # Prepare cluster summaries for Claude
        cluster_summaries = []
        for cluster_key, creatives in clusters.items():
            summary = {
                'key': cluster_key,
                'count': len(creatives),
                'domains': list(set(c['detected_domain'] for c in creatives if c['detected_domain'])),
                'urls_sample': [c['detected_url'] for c in creatives[:5] if c['detected_url']],
                'formats': list(set(c['format'] for c in creatives)),
                'date_range': self._get_date_range(creatives),
            }
            cluster_summaries.append(summary)
        
        # Ask Claude to analyze
        prompt = self._build_analysis_prompt(cluster_summaries)
        
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return self._parse_claude_response(response.content[0].text)
    
    def _build_analysis_prompt(self, summaries: List[dict]) -> str:
        return f"""You are analyzing advertising creative clusters to identify campaigns.

Here are {len(summaries)} clusters of creatives:

{json.dumps(summaries, indent=2)}

For each cluster, provide:
1. A descriptive campaign name (e.g., "Holiday Shopping Campaign", "Mobile Gaming Q4")
2. Confidence score (0-1) that these creatives belong together
3. Any clusters that should be merged (same campaign, different placements)
4. Any clusters that should be split (unrelated creatives grouped together)

Respond in JSON format:
{{
  "campaigns": [
    {{
      "cluster_keys": ["domain:example.com"],  // Which clusters to merge
      "name": "Example Brand Campaign",
      "confidence": 0.85,
      "reasoning": "All creatives point to same advertiser domain"
    }}
  ],
  "splits": [
    {{
      "cluster_key": "week:2025-W45",
      "reason": "Contains unrelated advertisers, should not be grouped"
    }}
  ]
}}

Be concise. Focus on actionable groupings."""
    
    def _parse_claude_response(self, text: str) -> List[dict]:
        """Parse JSON from Claude's response."""
        # Handle markdown code blocks
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        
        return json.loads(text.strip())
```

### Step 3: Performance-Based Validation

Validate clusters by checking if creatives perform similarly:

```python
# api/clustering/performance_validator.py

class ClusterPerformanceValidator:
    def validate_cluster(self, creative_ids: List[int]) -> dict:
        """
        Check if creatives in a cluster have similar performance patterns.
        """
        # Get performance data for all creatives
        metrics = self.db.execute("""
            SELECT 
                creative_id,
                geo_id,
                SUM(impressions) as impressions,
                SUM(clicks) as clicks,
                SUM(spend) as spend
            FROM performance_metrics
            WHERE creative_id IN ({})
            AND date >= date('now', '-30 days')
            GROUP BY creative_id, geo_id
        """.format(','.join('?' * len(creative_ids))), creative_ids).fetchall()
        
        # Calculate correlation between creatives
        # High correlation = likely same campaign
        # Low correlation = might be unrelated
        
        correlation = self._calculate_geo_correlation(metrics)
        
        return {
            'creative_ids': creative_ids,
            'correlation': correlation,
            'is_coherent': correlation > 0.6,
            'top_geos': self._get_top_geos(metrics),
        }
```

---

## 📋 Part 3: Database Schema

```sql
-- ============================================
-- CAMPAIGNS TABLE
-- ============================================

CREATE TABLE IF NOT EXISTS campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seat_id INTEGER REFERENCES seats(id),
    
    -- Identity
    name TEXT NOT NULL,
    description TEXT,
    
    -- AI metadata
    ai_generated BOOLEAN DEFAULT TRUE,
    ai_confidence REAL,  -- 0-1, how confident AI was about this grouping
    clustering_method TEXT,  -- 'domain', 'url', 'ai', 'manual'
    
    -- Status
    status TEXT DEFAULT 'active',  -- 'active', 'paused', 'archived'
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_campaigns_seat ON campaigns(seat_id);

-- ============================================
-- CREATIVE-CAMPAIGN MAPPING
-- ============================================

CREATE TABLE IF NOT EXISTS creative_campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    creative_id INTEGER NOT NULL REFERENCES creatives(id),
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id),
    
    -- Allow override
    manually_assigned BOOLEAN DEFAULT FALSE,
    
    -- Track changes
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    assigned_by TEXT,  -- 'ai', 'user', 'rule'
    
    UNIQUE(creative_id)  -- Each creative belongs to ONE campaign
);

CREATE INDEX idx_cc_campaign ON creative_campaigns(campaign_id);
CREATE INDEX idx_cc_creative ON creative_campaigns(creative_id);

-- ============================================
-- CAMPAIGN PERFORMANCE (aggregated)
-- ============================================

CREATE TABLE IF NOT EXISTS campaign_daily_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id),
    date DATE NOT NULL,
    
    -- Aggregated from all creatives in campaign
    total_creatives INTEGER,
    active_creatives INTEGER,  -- Creatives with impressions > 0
    
    total_queries INTEGER DEFAULT 0,
    total_impressions INTEGER DEFAULT 0,
    total_clicks INTEGER DEFAULT 0,
    total_spend REAL DEFAULT 0,
    
    -- Video (if applicable)
    total_video_starts INTEGER,
    total_video_completions INTEGER,
    
    -- Calculated
    avg_win_rate REAL,
    avg_ctr REAL,
    avg_cpm REAL,
    
    -- Geographic diversity
    unique_geos INTEGER,
    top_geo_id INTEGER,
    top_geo_spend REAL,
    
    UNIQUE(campaign_id, date)
);

CREATE INDEX idx_cds_campaign_date ON campaign_daily_summary(campaign_id, date DESC);
```

---

## 📋 Part 4: API Endpoints

```python
# api/campaigns.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter()

# ============================================
# CLUSTERING ENDPOINTS
# ============================================

@router.post("/api/campaigns/auto-cluster")
async def auto_cluster_creatives(
    seat_id: int,
    use_ai: bool = True,
    min_cluster_size: int = 3
):
    """
    Automatically cluster all uncategorized creatives into campaigns.
    """
    # Get uncategorized creatives
    creatives = get_uncategorized_creatives(seat_id)
    
    if not creatives:
        return {"message": "All creatives already categorized", "campaigns_created": 0}
    
    # Step 1: Rule-based pre-clustering
    clusters = pre_cluster_creatives(creatives)
    
    # Step 2: AI refinement (if enabled)
    if use_ai:
        clusterer = AICampaignClusterer()
        ai_result = await clusterer.analyze_and_name_clusters(clusters)
        campaigns = apply_ai_suggestions(clusters, ai_result)
    else:
        campaigns = create_campaigns_from_clusters(clusters)
    
    # Step 3: Save to database
    created = []
    for campaign_data in campaigns:
        campaign = save_campaign(seat_id, campaign_data)
        assign_creatives_to_campaign(campaign.id, campaign_data['creative_ids'])
        created.append(campaign)
    
    return {
        "campaigns_created": len(created),
        "creatives_categorized": sum(len(c['creative_ids']) for c in campaigns),
        "campaigns": [{"id": c.id, "name": c.name, "count": c.creative_count} for c in created]
    }


@router.get("/api/campaigns")
async def list_campaigns(
    seat_id: int,
    include_performance: bool = True,
    period: str = "7d"
):
    """
    List all campaigns with optional performance data.
    """
    campaigns = get_campaigns_for_seat(seat_id)
    
    if include_performance:
        for campaign in campaigns:
            campaign['performance'] = get_campaign_performance(campaign['id'], period)
    
    return {"campaigns": campaigns}


@router.get("/api/campaigns/{campaign_id}")
async def get_campaign(campaign_id: int, include_creatives: bool = True):
    """
    Get campaign details.
    """
    campaign = get_campaign_by_id(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    if include_creatives:
        campaign['creatives'] = get_campaign_creatives(campaign_id)
    
    return campaign


@router.put("/api/campaigns/{campaign_id}")
async def update_campaign(campaign_id: int, data: CampaignUpdate):
    """
    Update campaign name or description.
    """
    campaign = get_campaign_by_id(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    update_campaign_details(campaign_id, data.name, data.description)
    
    return {"status": "updated"}


# ============================================
# CREATIVE ASSIGNMENT ENDPOINTS
# ============================================

@router.post("/api/campaigns/{campaign_id}/creatives")
async def add_creatives_to_campaign(campaign_id: int, creative_ids: List[int]):
    """
    Manually assign creatives to a campaign.
    """
    assign_creatives_to_campaign(
        campaign_id, 
        creative_ids, 
        assigned_by='user',
        manually_assigned=True
    )
    
    return {"status": "assigned", "count": len(creative_ids)}


@router.delete("/api/campaigns/{campaign_id}/creatives/{creative_id}")
async def remove_creative_from_campaign(campaign_id: int, creative_id: int):
    """
    Remove a creative from a campaign.
    """
    remove_creative_assignment(creative_id)
    
    return {"status": "removed"}


@router.post("/api/creatives/{creative_id}/move")
async def move_creative(creative_id: int, to_campaign_id: int):
    """
    Move a creative from one campaign to another.
    """
    move_creative_to_campaign(creative_id, to_campaign_id, assigned_by='user')
    
    return {"status": "moved"}


# ============================================
# CAMPAIGN PERFORMANCE ENDPOINTS
# ============================================

@router.get("/api/campaigns/{campaign_id}/performance")
async def get_campaign_performance(
    campaign_id: int,
    period: str = "7d",
    breakdown: str = None  # 'geo', 'creative', 'day'
):
    """
    Get performance metrics for a campaign.
    """
    if breakdown == 'geo':
        return get_campaign_geo_breakdown(campaign_id, period)
    elif breakdown == 'creative':
        return get_campaign_creative_breakdown(campaign_id, period)
    elif breakdown == 'day':
        return get_campaign_daily_trend(campaign_id, period)
    else:
        return get_campaign_summary(campaign_id, period)


@router.post("/api/campaigns/refresh-summaries")
async def refresh_campaign_summaries(seat_id: int = None):
    """
    Recalculate campaign_daily_summary from performance_metrics.
    Run this after importing new data.
    """
    if seat_id:
        campaigns = get_campaigns_for_seat(seat_id)
    else:
        campaigns = get_all_campaigns()
    
    for campaign in campaigns:
        update_campaign_summary(campaign['id'])
    
    return {"status": "refreshed", "campaigns_updated": len(campaigns)}
```

---

## 📋 Part 5: Frontend Components

### Campaign List Page

```tsx
// dashboard/src/app/campaigns/page.tsx

'use client';

import { useState, useEffect } from 'react';
import { CampaignCard } from '@/components/CampaignCard';
import { AutoClusterButton } from '@/components/AutoClusterButton';

export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState('7d');
  
  useEffect(() => {
    fetchCampaigns();
  }, [period]);
  
  const fetchCampaigns = async () => {
    setLoading(true);
    const res = await fetch(`/api/campaigns?include_performance=true&period=${period}`);
    const data = await res.json();
    setCampaigns(data.campaigns);
    setLoading(false);
  };
  
  const handleAutoCluster = async () => {
    const res = await fetch('/api/campaigns/auto-cluster', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ seat_id: 1, use_ai: true }),
    });
    const result = await res.json();
    
    if (result.campaigns_created > 0) {
      toast.success(`Created ${result.campaigns_created} campaigns!`);
      fetchCampaigns();
    }
  };
  
  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Campaigns</h1>
        
        <div className="flex gap-4">
          <select 
            value={period} 
            onChange={(e) => setPeriod(e.target.value)}
            className="border rounded px-3 py-2"
          >
            <option value="1d">Yesterday</option>
            <option value="7d">Last 7 days</option>
            <option value="30d">Last 30 days</option>
            <option value="all">All time</option>
          </select>
          
          <AutoClusterButton onClick={handleAutoCluster} />
        </div>
      </div>
      
      {loading ? (
        <div className="text-center py-12">Loading campaigns...</div>
      ) : campaigns.length === 0 ? (
        <EmptyState onAutoCluster={handleAutoCluster} />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {campaigns.map((campaign) => (
            <CampaignCard 
              key={campaign.id} 
              campaign={campaign}
              period={period}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function EmptyState({ onAutoCluster }) {
  return (
    <div className="text-center py-12 bg-gray-50 rounded-lg">
      <h2 className="text-xl font-semibold mb-2">No campaigns yet</h2>
      <p className="text-gray-600 mb-4">
        You have creatives but they haven't been organized into campaigns.
      </p>
      <button
        onClick={onAutoCluster}
        className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700"
      >
        🤖 Auto-Cluster with AI
      </button>
    </div>
  );
}
```

### Campaign Card Component

```tsx
// dashboard/src/components/CampaignCard.tsx

interface CampaignCardProps {
  campaign: {
    id: number;
    name: string;
    creative_count: number;
    ai_confidence?: number;
    performance?: {
      impressions: number;
      clicks: number;
      spend: number;
      win_rate: number;
      top_geo: string;
    };
  };
  period: string;
}

export function CampaignCard({ campaign, period }: CampaignCardProps) {
  const perf = campaign.performance;
  
  return (
    <Link href={`/campaigns/${campaign.id}`}>
      <div className="bg-white border rounded-lg p-4 hover:shadow-md transition-shadow">
        <div className="flex justify-between items-start mb-3">
          <h3 className="font-semibold text-lg">{campaign.name}</h3>
          {campaign.ai_confidence && (
            <span 
              className="text-xs px-2 py-1 rounded bg-purple-100 text-purple-700"
              title={`AI confidence: ${Math.round(campaign.ai_confidence * 100)}%`}
            >
              🤖 AI
            </span>
          )}
        </div>
        
        <p className="text-sm text-gray-500 mb-4">
          {campaign.creative_count} creatives
        </p>
        
        {perf && (
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <span className="text-gray-500">Spend</span>
              <p className="font-medium">${perf.spend.toLocaleString()}</p>
            </div>
            <div>
              <span className="text-gray-500">Impressions</span>
              <p className="font-medium">{formatNumber(perf.impressions)}</p>
            </div>
            <div>
              <span className="text-gray-500">Win Rate</span>
              <p className="font-medium">{(perf.win_rate * 100).toFixed(2)}%</p>
            </div>
            <div>
              <span className="text-gray-500">Top Geo</span>
              <p className="font-medium">{perf.top_geo || '-'}</p>
            </div>
          </div>
        )}
      </div>
    </Link>
  );
}
```

### Campaign Detail Page

```tsx
// dashboard/src/app/campaigns/[id]/page.tsx

'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import { CreativeGrid } from '@/components/CreativeGrid';
import { PerformanceChart } from '@/components/PerformanceChart';
import { GeoBreakdown } from '@/components/GeoBreakdown';

export default function CampaignDetailPage() {
  const { id } = useParams();
  const [campaign, setCampaign] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');
  
  useEffect(() => {
    fetchCampaign();
  }, [id]);
  
  const fetchCampaign = async () => {
    const res = await fetch(`/api/campaigns/${id}?include_creatives=true`);
    const data = await res.json();
    setCampaign(data);
  };
  
  if (!campaign) return <div>Loading...</div>;
  
  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex justify-between items-start mb-6">
        <div>
          <h1 className="text-2xl font-bold">{campaign.name}</h1>
          <p className="text-gray-500">
            {campaign.creative_count} creatives • 
            Created {formatDate(campaign.created_at)}
          </p>
        </div>
        
        <EditCampaignButton campaign={campaign} onUpdate={fetchCampaign} />
      </div>
      
      {/* Tabs */}
      <div className="border-b mb-6">
        <nav className="flex gap-6">
          {['overview', 'creatives', 'performance', 'geography'].map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`pb-3 px-1 capitalize ${
                activeTab === tab 
                  ? 'border-b-2 border-blue-600 text-blue-600' 
                  : 'text-gray-500'
              }`}
            >
              {tab}
            </button>
          ))}
        </nav>
      </div>
      
      {/* Tab Content */}
      {activeTab === 'overview' && (
        <CampaignOverview campaign={campaign} />
      )}
      {activeTab === 'creatives' && (
        <CreativeGrid 
          creatives={campaign.creatives}
          campaignId={campaign.id}
          onMove={fetchCampaign}
        />
      )}
      {activeTab === 'performance' && (
        <PerformanceChart campaignId={campaign.id} />
      )}
      {activeTab === 'geography' && (
        <GeoBreakdown campaignId={campaign.id} />
      )}
    </div>
  );
}
```

### Drag-and-Drop Creative Management

```tsx
// dashboard/src/components/CreativeGrid.tsx

import { useDrag, useDrop } from 'react-dnd';

export function CreativeGrid({ creatives, campaignId, onMove }) {
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  
  const handleMoveSelected = async (toCampaignId: number) => {
    for (const creativeId of selectedIds) {
      await fetch(`/api/creatives/${creativeId}/move`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ to_campaign_id: toCampaignId }),
      });
    }
    setSelectedIds([]);
    onMove();
  };
  
  return (
    <div>
      {selectedIds.length > 0 && (
        <div className="bg-blue-50 p-4 rounded-lg mb-4 flex justify-between items-center">
          <span>{selectedIds.length} creatives selected</span>
          <CampaignSelector 
            onSelect={handleMoveSelected}
            excludeCampaignId={campaignId}
          />
        </div>
      )}
      
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
        {creatives.map((creative) => (
          <CreativeThumbnail
            key={creative.id}
            creative={creative}
            selected={selectedIds.includes(creative.id)}
            onToggleSelect={() => {
              setSelectedIds((prev) =>
                prev.includes(creative.id)
                  ? prev.filter((id) => id !== creative.id)
                  : [...prev, creative.id]
              );
            }}
          />
        ))}
      </div>
    </div>
  );
}
```

---

## 📋 Part 6: Clustering Job (Background)

For large accounts, run clustering as a background job:

```python
# api/jobs/clustering_job.py

from celery import shared_task
from api.clustering.ai_clusterer import AICampaignClusterer
from api.clustering.rule_based import pre_cluster_creatives

@shared_task
def run_auto_clustering(seat_id: int):
    """
    Background job to cluster creatives.
    Can take several minutes for large accounts.
    """
    # Get uncategorized creatives
    creatives = get_uncategorized_creatives(seat_id)
    
    if not creatives:
        return {"status": "nothing_to_cluster"}
    
    # Update job status
    update_job_status(seat_id, "clustering", "running", f"Processing {len(creatives)} creatives")
    
    # Step 1: Rule-based
    clusters = pre_cluster_creatives(creatives)
    update_job_status(seat_id, "clustering", "running", f"Found {len(clusters)} initial clusters")
    
    # Step 2: AI refinement
    clusterer = AICampaignClusterer()
    ai_result = clusterer.analyze_and_name_clusters(clusters)
    
    # Step 3: Create campaigns
    campaigns_created = 0
    for campaign_data in ai_result['campaigns']:
        campaign = save_campaign(seat_id, campaign_data)
        assign_creatives_to_campaign(campaign.id, campaign_data['creative_ids'])
        campaigns_created += 1
    
    update_job_status(seat_id, "clustering", "complete", f"Created {campaigns_created} campaigns")
    
    return {
        "status": "complete",
        "campaigns_created": campaigns_created,
        "creatives_categorized": len(creatives)
    }
```

---

## 📋 Part 7: Files to Create/Modify

**New files:**
```
api/clustering/rule_based.py              # Domain/URL-based pre-clustering
api/clustering/ai_clusterer.py            # Claude API integration
api/clustering/performance_validator.py   # Validate cluster coherence
api/campaigns.py                          # Campaign API endpoints
api/jobs/clustering_job.py                # Background clustering job

api/storage/migrations/010_campaigns.py   # Campaign tables migration

dashboard/src/app/campaigns/page.tsx      # Campaign list page
dashboard/src/app/campaigns/[id]/page.tsx # Campaign detail page
dashboard/src/components/CampaignCard.tsx
dashboard/src/components/AutoClusterButton.tsx
dashboard/src/components/CreativeGrid.tsx
dashboard/src/components/CampaignSelector.tsx
```

**Modified files:**
```
api/main.py                               # Add campaign router
dashboard/src/app/layout.tsx              # Add Campaigns to nav
```

---

## 📋 Part 8: Testing Checklist

- [ ] Auto-cluster creates campaigns from uncategorized creatives
- [ ] AI generates meaningful campaign names
- [ ] Campaigns show aggregated performance
- [ ] Creatives can be moved between campaigns
- [ ] Manual campaign creation works
- [ ] Campaign detail page shows all creatives
- [ ] Performance breakdown by geo/creative/day works
- [ ] Re-running auto-cluster doesn't duplicate campaigns

---

## 🚀 Expected Outcome

**Before:**
```
652 individual creatives - overwhelming
```

**After:**
```
~15-20 campaigns:
├── Holiday Shopping 2025 (47 creatives) - $12,450 spend
├── Mobile Gaming Q4 (89 creatives) - $8,230 spend  
├── Video Streaming Promo (23 creatives) - $5,120 spend
└── ... organized and actionable
```

---

## 📍 Location Reference

```
Project root: /home/jen/Documents/rtbcat-platform/
Database: ~/.rtbcat/rtbcat.db
```

**After code changes:**
```bash
sudo systemctl restart rtbcat-api
```

**Test clustering:**
```bash
curl -X POST "http://localhost:8000/api/campaigns/auto-cluster" \
  -H "Content-Type: application/json" \
  -d '{"seat_id": 1, "use_ai": true}'
```
