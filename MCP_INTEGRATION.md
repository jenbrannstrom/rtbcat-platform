# MCP Integration Guide

**Version:** 1.0 | **Last Updated:** January 2026

This guide explains how to connect AI tools (Claude, GPT, etc.) to Cat-Scan via the Model Context Protocol (MCP).

---

## Overview

Cat-Scan exposes a comprehensive REST API that can be connected to AI assistants through MCP servers. This allows AI tools to:

- Query creative performance data
- Analyze QPS efficiency metrics
- Generate optimization recommendations
- Monitor RTB funnel performance
- Manage pretargeting configurations

---

## Quick Start

### 1. API Access

Cat-Scan API is available at:
- **Local Development:** `http://localhost:8000`
- **Production:** `https://scan.rtb.cat` (or your deployment URL)

Full API documentation (Swagger UI): `http://localhost:8000/docs`

### 2. Authentication

Two authentication methods are supported:

**Option A: API Key** (recommended for MCP)
```bash
# Set environment variable
export CATSCAN_API_KEY="your-secure-key"

# Or pass in request header
curl -H "X-API-Key: your-secure-key" http://localhost:8000/health
```

**Option B: Session Authentication**
```bash
# Login to get session cookie
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "your-password"}'
```

---

## Key API Endpoints for AI Integration

### Creative Data

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/creatives` | GET | List all creatives with filters |
| `/creatives/{id}` | GET | Get specific creative details |
| `/creatives/newly-uploaded` | GET | Get recently added creatives |

**Example Query:**
```bash
# Get creatives with performance data
curl "http://localhost:8000/creatives?limit=100&days=7"
```

### Performance Analytics

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/analytics/size-coverage` | GET | Size gap analysis |
| `/analytics/rtb-funnel` | GET | Full RTB funnel metrics |
| `/analytics/rtb-funnel/configs` | GET | Config performance comparison |
| `/analytics/qps-summary` | GET | QPS efficiency summary |
| `/analytics/waste` | GET | Waste analysis report |

**Example Query:**
```bash
# Get QPS summary for last 7 days
curl "http://localhost:8000/analytics/qps-summary?days=7"
```

### Recommendations

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/recommendations` | GET | AI-generated recommendations |
| `/recommendations/summary` | GET | Recommendation summary |
| `/recommendations/{id}/resolve` | POST | Mark recommendation resolved |

**Example Response:**
```json
{
  "id": "rec_123",
  "type": "size_gap",
  "severity": "high",
  "title": "Missing 320x50 creatives",
  "description": "High traffic for 320x50 but no creatives available",
  "impact": {
    "wasted_qps": 1500,
    "potential_savings_monthly": 450.00
  },
  "actions": [
    {
      "action_type": "add",
      "target_type": "size",
      "target_id": "320x50"
    }
  ]
}
```

### Pretargeting Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/settings/pretargeting` | GET | List pretargeting configs |
| `/settings/pretargeting/{billing_id}/detail` | GET | Config with pending changes |
| `/settings/pretargeting/pending-change` | POST | Create pending change |
| `/settings/pretargeting/{billing_id}/apply` | POST | Apply changes (dry_run=true) |

---

## MCP Server Configuration

### Generic HTTP MCP Server

Most MCP implementations support HTTP APIs. Configure your MCP server to connect to Cat-Scan:

```json
{
  "name": "catscan",
  "type": "http",
  "base_url": "http://localhost:8000",
  "headers": {
    "X-API-Key": "${CATSCAN_API_KEY}"
  },
  "endpoints": [
    {
      "name": "get_creatives",
      "path": "/creatives",
      "method": "GET",
      "description": "List creatives with optional filters"
    },
    {
      "name": "get_recommendations",
      "path": "/recommendations",
      "method": "GET",
      "description": "Get AI-generated optimization recommendations"
    },
    {
      "name": "get_qps_summary",
      "path": "/analytics/qps-summary",
      "method": "GET",
      "description": "Get QPS efficiency summary"
    }
  ]
}
```

### Claude Desktop MCP Configuration

For Claude Desktop, add to your MCP config:

```json
{
  "mcpServers": {
    "catscan": {
      "command": "npx",
      "args": [
        "-y",
        "@anthropic/mcp-server-http",
        "--base-url", "http://localhost:8000",
        "--api-key-header", "X-API-Key",
        "--api-key", "${CATSCAN_API_KEY}"
      ]
    }
  }
}
```

---

## Common AI Queries

Here are example prompts for AI assistants connected to Cat-Scan:

### Performance Analysis

```
"What are the top 5 underperforming creative sizes in the last 7 days?"

"Show me the RTB funnel conversion rates for each pretargeting config"

"Which publishers have the lowest win rates?"
```

### Optimization Recommendations

```
"Generate recommendations for improving QPS efficiency"

"What creative sizes should we add to capture more inventory?"

"Which regions should we exclude due to poor performance?"
```

### Pretargeting Management

```
"Show me all pending pretargeting changes"

"Create a pending change to exclude publisher X from config Y"

"What would happen if we activated the pending changes for billing_id 123?"
```

---

## Data Models

### Creative Object

```typescript
interface Creative {
  id: string;
  name: string;
  format: "VIDEO" | "HTML" | "NATIVE";
  approval_status: string;
  width: number;
  height: number;
  final_url: string;
  buyer_id: string;
  // Performance metrics (when requested)
  thumbnail_status?: ThumbnailStatus;
  waste_flags?: WasteFlags;
}
```

### QPS Summary

```typescript
interface QPSSummary {
  period_days: number;
  size_coverage: {
    coverage_rate_pct: number;
    sizes_covered: number;
    sizes_missing: number;
    wasted_qps: number;
  };
  regional_efficiency: {
    regions_analyzed: number;
    regions_to_exclude: number;
    waste_pct: number;
  };
  estimated_savings: {
    regional_waste_monthly_usd: number;
  };
}
```

### Recommendation

```typescript
interface Recommendation {
  id: string;
  type: string;
  severity: "critical" | "high" | "medium" | "low";
  confidence: string;
  title: string;
  description: string;
  evidence: Evidence[];
  impact: Impact;
  actions: Action[];
}
```

---

## Rate Limits & Best Practices

### Rate Limits

- **Default:** No hard rate limits for local deployments
- **Production:** Consider implementing rate limiting via reverse proxy

### Best Practices

1. **Cache responses** - Creative data doesn't change frequently
2. **Use pagination** - For large creative lists, use `limit` and `offset`
3. **Batch requests** - Use batch endpoints where available
4. **Check health first** - Call `/health` before complex queries

### Example Batch Request

```bash
# Get performance for multiple creatives at once
curl -X POST "http://localhost:8000/performance/metrics/batch" \
  -H "Content-Type: application/json" \
  -d '{"creative_ids": ["cr-123", "cr-456", "cr-789"], "period": "7d"}'
```

---

## Error Handling

### Common Error Codes

| Code | Meaning | Resolution |
|------|---------|------------|
| 401 | Unauthorized | Check API key or session |
| 404 | Not found | Verify resource ID exists |
| 422 | Validation error | Check request parameters |
| 500 | Server error | Check API logs |

### Error Response Format

```json
{
  "detail": "Creative not found",
  "status_code": 404
}
```

---

## Advanced: Custom MCP Tools

For advanced integrations, you can create custom MCP tools that combine multiple Cat-Scan API calls:

### Example: Optimization Report Tool

```python
async def generate_optimization_report(days: int = 7) -> dict:
    """Generate a comprehensive optimization report."""

    # Fetch multiple data sources
    qps_summary = await fetch("/analytics/qps-summary", {"days": days})
    recommendations = await fetch("/recommendations", {"days": days})
    config_perf = await fetch("/analytics/rtb-funnel/configs", {"days": days})

    return {
        "summary": qps_summary,
        "top_recommendations": recommendations[:5],
        "config_performance": config_perf,
        "generated_at": datetime.now().isoformat()
    }
```

---

## Troubleshooting

### Connection Issues

```bash
# Test API connectivity
curl -v http://localhost:8000/health

# Expected response
{"status": "healthy", "version": "0.1.0"}
```

### Authentication Issues

```bash
# Test API key authentication
curl -H "X-API-Key: your-key" http://localhost:8000/stats

# If 401 error, verify CATSCAN_API_KEY is set in API environment
```

### No Data Returned

```bash
# Check if data exists
curl http://localhost:8000/stats

# Expected: {"creatives": 600, "campaigns": 25, ...}
# If all zeros, import CSV data or sync from Google API
```

---

## Resources

- **API Documentation:** `http://localhost:8000/docs`
- **OpenAPI Spec:** `http://localhost:8000/openapi.json`
- **Project Repository:** [GitHub](https://github.com/rtbcat/rtbcat-platform)

---

*This guide is for Cat-Scan v24.0. API endpoints may change in future versions.*
