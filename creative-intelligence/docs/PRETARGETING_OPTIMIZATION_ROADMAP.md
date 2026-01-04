# Pretargeting Optimization Roadmap

**Version:** 1.0 | **Created:** December 26, 2025

## Executive Summary

Cat-Scan will evolve from a **read-only analytics tool** to a **closed-loop optimization system** that can automatically adjust Google Authorized Buyers pretargeting configurations to minimize QPS waste.

### Vision

```
 Current State                    Future State
 ─────────────                    ────────────
 ┌──────────────┐                ┌──────────────┐
 │   Manual     │                │   AI-Driven  │
 │   Analysis   │                │ Optimization │
 │      +       │      ──►       │      +       │
 │   Manual     │                │   Rollback   │
 │   Changes    │                │   Safety     │
 └──────────────┘                └──────────────┘
```

---

## Phase 1: Pretargeting Write API

**Goal:** Enable Cat-Scan to push pretargeting configuration changes to Google Authorized Buyers.

### 1.1 API Integration

Implement Google RTB API write operations:
- `bidders.pretargetingConfigs.patch` - Update existing configs
- `bidders.pretargetingConfigs.activate` - Enable a config
- `bidders.pretargetingConfigs.suspend` - Disable a config

### 1.2 Supported Operations

| Operation | API Method | Description |
|-----------|------------|-------------|
| Add size | patch | Add a creative size to `includedCreativeDimensions` |
| Remove size | patch | Remove a size from targeting |
| Add geo | patch | Add country/region to `geoTargeting.includedIds` |
| Remove geo | patch | Add to `geoTargeting.excludedIds` |
| Add format | patch | Add HTML/VIDEO/NATIVE to `includedFormats` |
| Suspend config | suspend | Temporarily disable entire config |
| Activate config | activate | Re-enable a suspended config |

### 1.3 Safety Constraints

- **Dry-run mode** by default (show what would change)
- **Confirmation required** for production writes
- **Rate limiting** to avoid API quota issues
- **Audit logging** of all write operations

### 1.4 Endpoints

```
POST /api/settings/pretargeting/{billing_id}/apply-change
  - Apply a single pending change

POST /api/settings/pretargeting/{billing_id}/apply-all
  - Apply all pending changes for a config

POST /api/settings/pretargeting/{billing_id}/suspend
  - Suspend a pretargeting config

POST /api/settings/pretargeting/{billing_id}/activate
  - Activate a suspended config
```

---

## Phase 2: Change History & Rollback

**Goal:** Track all configuration changes and enable point-in-time rollback.

### 2.1 Enhanced History Tracking

Current schema already has:
- `pretargeting_history` - Records all changes
- `pretargeting_snapshots` - Point-in-time config states
- `pretargeting_pending_changes` - Staged changes

### 2.2 Rollback Capabilities

| Rollback Type | Description |
|---------------|-------------|
| **Undo last change** | Revert the most recent modification |
| **Restore snapshot** | Return config to a saved state |
| **Selective undo** | Revert specific fields only |
| **Emergency suspend** | One-click disable with auto-snapshot |

### 2.3 Snapshot Comparison

```
Snapshot A (Before)          Snapshot B (After)
───────────────────          ──────────────────
sizes: [300x250, 728x90]     sizes: [300x250]  ← Removed 728x90
geos: [US, CA, MX]           geos: [US, CA]    ← Removed MX
state: ACTIVE                state: ACTIVE

Performance Impact:
  Impressions: 1.2M → 0.9M  (-25%)
  QPS Used:    45K → 32K    (-29%)
  Waste:       35% → 22%    (-13pp)
```

### 2.4 Endpoints

```
POST /api/settings/pretargeting/{billing_id}/rollback
  - body: { snapshot_id: 123 }
  - Restore config to snapshot state

POST /api/settings/pretargeting/{billing_id}/undo
  - Undo the last change

GET /api/settings/pretargeting/{billing_id}/diff
  - Compare current state to a snapshot
```

---

## Phase 3: QPS Adjudication Engine

**Goal:** Automatically calculate optimal pretargeting settings based on performance data.

### 3.1 Optimization Signals

| Signal | Weight | Description |
|--------|--------|-------------|
| **Size waste** | High | Sizes receiving QPS but no approved creatives |
| **Geo waste** | Medium | Countries with high QPS, low win rate |
| **Format waste** | High | Formats with no approved creatives |
| **Historic performance** | Medium | CTR, conversion rate by segment |
| **Budget allocation** | High | Spend vs. available QPS ratio |

### 3.2 Recommendation Types

```python
class OptimizationRecommendation:
    type: Literal["remove_size", "add_size", "exclude_geo", "suspend_config"]
    confidence: float  # 0.0 - 1.0
    impact_qps: int    # Estimated QPS saved/added
    impact_spend: float  # Estimated spend change
    reasoning: str
    auto_apply: bool   # Can be auto-applied vs requires approval
```

### 3.3 Decision Rules

```
IF size NOT in approved_creatives AND qps_last_7d > 1000:
    RECOMMEND remove_size with confidence=0.95

IF geo win_rate < 0.1% AND qps_last_7d > 10000:
    RECOMMEND exclude_geo with confidence=0.80

IF config state=ACTIVE AND impressions_last_30d = 0:
    RECOMMEND suspend_config with confidence=0.70
```

### 3.4 Endpoints

```
GET /api/optimization/recommendations
  - Get all current recommendations

GET /api/optimization/recommendations/{billing_id}
  - Get recommendations for specific config

POST /api/optimization/simulate
  - body: { changes: [...] }
  - Simulate impact of proposed changes

POST /api/optimization/auto-optimize
  - body: { billing_id, confidence_threshold: 0.9 }
  - Auto-apply high-confidence recommendations
```

---

## Phase 4: AI/MCP Integration

**Goal:** Enable AI agents (Claude via MCP) to analyze and optimize configurations.

### 4.1 MCP Server Implementation

```typescript
// MCP Tools for Cat-Scan
const tools = [
  {
    name: "get_pretargeting_configs",
    description: "List all pretargeting configurations with current state"
  },
  {
    name: "get_qps_waste_analysis",
    description: "Analyze QPS waste by size, geo, and format"
  },
  {
    name: "propose_optimization",
    description: "Propose a pretargeting change with reasoning"
  },
  {
    name: "apply_optimization",
    description: "Apply a proposed optimization (requires confirmation)"
  },
  {
    name: "rollback_change",
    description: "Rollback to a previous configuration state"
  }
]
```

### 4.2 AI Decision Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        AI Optimization Loop                      │
└─────────────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────┐     ┌──────────────────┐
│  Fetch Current   │────►│  Analyze Waste   │
│  Configuration   │     │  Patterns        │
└──────────────────┘     └────────┬─────────┘
                                  │
                                  ▼
                    ┌─────────────────────────┐
                    │  Generate Optimization  │
                    │  Proposals with         │
                    │  Confidence Scores      │
                    └────────────┬────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
    ┌─────────────────┐ ┌───────────────┐ ┌───────────────┐
    │ Auto-Apply      │ │ Queue for     │ │ Log for       │
    │ (confidence>0.9)│ │ Human Review  │ │ Analysis      │
    └─────────────────┘ └───────────────┘ └───────────────┘
```

### 4.3 Safety Guardrails

| Guardrail | Implementation |
|-----------|----------------|
| **Spend cap** | the app has no access to spend settings |
| **QPS floor** | Maintain minimum QPS for A/B testing |
| **Rollback window** | Auto-rollback if performance drops 20% in 24h |
| **Human approval** | Changes require confirmation |
| **Audit trail** | All AI decisions logged with reasoning |

### 4.4 MCP Endpoints

```
# Read-only (no confirmation needed)
GET /mcp/pretargeting/status
GET /mcp/qps/waste-analysis
GET /mcp/recommendations

# Write operations (require confirmation)
POST /mcp/pretargeting/propose
POST /mcp/pretargeting/apply
POST /mcp/pretargeting/rollback
```

---

## Implementation Timeline

| Phase | Description | Status |
|-------|-------------|--------|
| **Phase 1.1** | Pending changes UI (local staging) | DONE |
| **Phase 1.2** | Write API integration | TODO |
| **Phase 1.3** | Apply changes to Google | TODO |
| **Phase 2.1** | Enhanced history tracking | PARTIAL |
| **Phase 2.2** | Rollback functionality | TODO |
| **Phase 3** | Adjudication engine | TODO |
| **Phase 4** | MCP integration | TODO |

---

## Database Schema Extensions

### New Tables

```sql
-- Optimization recommendations
CREATE TABLE optimization_recommendations (
    id TEXT PRIMARY KEY,
    billing_id TEXT NOT NULL,
    recommendation_type TEXT NOT NULL,
    field_name TEXT,
    current_value TEXT,
    proposed_value TEXT,
    confidence REAL NOT NULL,
    impact_qps INTEGER,
    impact_spend_usd REAL,
    reasoning TEXT,
    auto_apply_eligible BOOLEAN DEFAULT FALSE,
    status TEXT DEFAULT 'pending',  -- pending, applied, rejected, expired
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    applied_at TIMESTAMP,
    applied_by TEXT,
    rejected_reason TEXT
);

-- Optimization runs (for tracking batch optimizations)
CREATE TABLE optimization_runs (
    id TEXT PRIMARY KEY,
    run_type TEXT NOT NULL,  -- manual, scheduled, ai
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    configs_analyzed INTEGER DEFAULT 0,
    recommendations_generated INTEGER DEFAULT 0,
    recommendations_applied INTEGER DEFAULT 0,
    total_qps_saved INTEGER DEFAULT 0,
    notes TEXT
);
```

---

## API Contract Example

### Propose Optimization

```http
POST /api/optimization/propose
Content-Type: application/json

{
  "billing_id": "164717596699",
  "changes": [
    {
      "type": "remove_size",
      "field": "included_sizes",
      "value": "728x90",
      "reason": "No approved creatives for this size"
    }
  ],
  "dry_run": true
}
```

**Response:**
```json
{
  "proposal_id": "prop-abc123",
  "billing_id": "164717596699",
  "changes": [...],
  "impact": {
    "qps_saved": 12500,
    "spend_change_usd": -45.00,
    "impressions_lost_estimate": 8000
  },
  "warnings": [
    "This will reduce reach by approximately 12%"
  ],
  "requires_approval": true,
  "auto_apply_eligible": false
}
```

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| QPS waste reduction | >5% | Before/after comparison |
| Time to optimize | <15 min | From analysis to applied |
| Rollback success rate | 100% | All rollbacks restore previous state |
| AI recommendation accuracy | >85% | Applied recommendations improve metrics |
| System uptime | 99.9% | No optimization causes outage |

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Over-optimization removes too much QPS | Minimum QPS floor per config |
| API rate limiting | Batch changes, respect quotas |
| Incorrect rollback | Test rollback in staging first |
| AI makes poor decisions | Confidence thresholds, human review |
| Billing impact | Spend caps, incremental changes |

---

## References

- [Google RTB API - Pretargeting](https://developers.google.com/authorized-buyers/apis/realtimebidding/reference/rest/v1/bidders.pretargetingConfigs)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [Cat-Scan Architecture](../README.md)
