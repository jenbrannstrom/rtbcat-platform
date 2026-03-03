# API Quick Reference

This is a navigable index of Cat-Scan's 118+ API endpoints, grouped by
domain. For full request/response schemas, see the interactive OpenAPI docs
at `https://scan.rtb.cat/api/docs`.

## Core / System

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness check (git_sha, version) |
| GET | `/stats` | System statistics |
| GET | `/sizes` | Available ad sizes |
| GET | `/system/status` | Server status (Python, Node, FFmpeg, DB, disk) |
| GET | `/system/data-health` | Data completeness per buyer |
| GET | `/system/ui-page-load-metrics` | Frontend performance metrics |
| GET | `/geo/lookup` | Geo ID to name resolution |
| GET | `/geo/search` | Search countries/cities |

## Auth

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/auth/check` | Check if current session is authenticated |
| POST | `/auth/logout` | End session |

## Seats

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/seats` | List buyer seats |
| GET | `/seats/{buyer_id}` | Get specific seat |
| PUT | `/seats/{buyer_id}` | Update seat display name |
| POST | `/seats/populate` | Auto-create seats from data |
| POST | `/seats/discover` | Discover seats from Google API |
| POST | `/seats/{buyer_id}/sync` | Sync specific seat |
| POST | `/seats/sync-all` | Full sync (all seats) |
| POST | `/seats/collect-creatives` | Collect creative data |

## Creatives

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/creatives` | List creatives (with filters) |
| GET | `/creatives/paginated` | Paginated creative list |
| GET | `/creatives/{id}` | Creative details |
| GET | `/creatives/{id}/live` | Live creative data (cache-aware) |
| GET | `/creatives/{id}/destination-diagnostics` | Destination URL health |
| GET | `/creatives/{id}/countries` | Country performance breakdown |
| GET | `/creatives/{id}/geo-linguistic` | Geo-linguistic analysis |
| POST | `/creatives/{id}/detect-language` | Auto-detect language |
| PUT | `/creatives/{id}/language` | Manual language override |
| GET | `/creatives/thumbnail-status` | Batch thumbnail status |
| POST | `/creatives/thumbnails/batch` | Generate missing thumbnails |

## Campaigns

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/campaigns` | List campaigns |
| GET | `/campaigns/{id}` | Campaign details |
| GET | `/campaigns/ai` | AI-generated clusters |
| GET | `/campaigns/ai/{id}` | AI campaign details |
| PUT | `/campaigns/ai/{id}` | Update campaign |
| DELETE | `/campaigns/ai/{id}` | Delete campaign |
| GET | `/campaigns/ai/{id}/creatives` | Campaign's creatives |
| DELETE | `/campaigns/ai/{id}/creatives/{creative_id}` | Remove creative from campaign |
| POST | `/campaigns/auto-cluster` | AI auto-clustering |
| GET | `/campaigns/ai/{id}/performance` | Campaign performance |
| GET | `/campaigns/ai/{id}/daily-trend` | Campaign trend data |

## Analytics

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/analytics/waste-report` | Overall waste metrics |
| GET | `/analytics/size-coverage` | Size targeting coverage |
| GET | `/analytics/rtb-funnel` | RTB funnel breakdown |
| GET | `/analytics/rtb-funnel/configs` | Config-level funnel |
| GET | `/analytics/endpoint-efficiency` | QPS efficiency by endpoint |
| GET | `/analytics/spend-stats` | Spend statistics |
| GET | `/analytics/config-performance` | Config performance over time |
| GET | `/analytics/config-performance/breakdown` | Config field breakdown |
| GET | `/analytics/qps-recommendations` | AI recommendations |
| GET | `/analytics/performance/batch` | Batch creative performance |
| GET | `/analytics/performance/{creative_id}` | Single creative performance |
| GET | `/analytics/publishers` | Publisher domain metrics |
| GET | `/analytics/publishers/search` | Search publishers |
| GET | `/analytics/languages` | Language performance |
| GET | `/analytics/languages/multi` | Multiple language analysis |
| GET | `/analytics/geo-performance` | Geographic performance |
| GET | `/analytics/geo-performance/multi` | Multiple geo analysis |
| POST | `/analytics/import` | CSV import |
| POST | `/analytics/mock-traffic` | Generate test data |

## Settings / Pretargeting

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/settings/rtb-endpoints` | Bidder RTB endpoints |
| POST | `/settings/rtb-endpoints/sync` | Sync endpoint data |
| GET | `/settings/pretargeting-configs` | List pretargeting configs |
| GET | `/settings/pretargeting-configs/{id}` | Config details |
| GET | `/settings/pretargeting-history` | Config change history |
| POST | `/settings/pretargeting-configs/sync` | Sync configs from Google |
| POST | `/settings/pretargeting-configs/{id}/apply` | Apply a config change |
| POST | `/settings/pretargeting-configs/apply-all` | Apply all pending changes |
| PUT | `/settings/pretargeting-configs/{id}` | Batch update config |

## Uploads

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/uploads/tracking` | Daily upload summary |
| GET | `/uploads/import-matrix` | Import status by report type |
| GET | `/uploads/data-freshness` | Data freshness grid (date x type) |
| GET | `/uploads/history` | Import history |

## Optimizer

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/optimizer/models` | List BYOM models |
| POST | `/optimizer/models` | Register model |
| PUT | `/optimizer/models/{id}` | Update model |
| POST | `/optimizer/models/{id}/activate` | Activate model |
| POST | `/optimizer/models/{id}/deactivate` | Deactivate model |
| POST | `/optimizer/models/{id}/validate` | Test model endpoint |
| POST | `/optimizer/score-and-propose` | Generate proposals |
| GET | `/optimizer/proposals` | List active proposals |
| GET | `/optimizer/proposals/history` | Proposal history |
| POST | `/optimizer/proposals/{id}/approve` | Approve proposal |
| POST | `/optimizer/proposals/{id}/apply` | Apply proposal |
| POST | `/optimizer/proposals/{id}/sync-status` | Check apply status |
| GET | `/optimizer/segment-scores` | Segment-level scores |
| GET | `/optimizer/economics/efficiency` | Efficiency summary |
| GET | `/optimizer/economics/effective-cpm` | CPM analysis |
| GET | `/optimizer/setup` | Optimizer configuration |
| PUT | `/optimizer/setup` | Update optimizer config |

## Conversions

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/conversions/health` | Ingestion and aggregation status |
| GET | `/conversions/readiness` | Source readiness check |
| GET | `/conversions/ingestion-stats` | Event counts by source/period |
| GET | `/conversions/security/status` | Webhook security status |
| GET | `/conversions/pixel` | Pixel tracking endpoint |

## Snapshots

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/snapshots` | List config snapshots |
| POST | `/snapshots/rollback` | Restore a snapshot (with dry-run) |

## Integrations

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/integrations/credentials` | Upload GCP service account JSON |
| GET | `/integrations/service-accounts` | List service accounts |
| DELETE | `/integrations/service-accounts/{id}` | Delete service account |
| GET | `/integrations/language-ai/config` | AI provider status |
| PUT | `/integrations/language-ai/config` | Configure AI provider |
| GET | `/integrations/gmail/status` | Gmail import status |
| POST | `/integrations/gmail/import/start` | Trigger manual import |
| POST | `/integrations/gmail/import/stop` | Stop import job |
| GET | `/integrations/gmail/import/history` | Import history |
| GET | `/integrations/gcp/project-status` | GCP project health |
| POST | `/integrations/gcp/validate` | Test GCP connection |

## Admin

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/admin/users` | List users |
| POST | `/admin/users` | Create user |
| GET | `/admin/users/{id}` | User details |
| PUT | `/admin/users/{id}` | Update user |
| POST | `/admin/users/{id}/deactivate` | Deactivate user |
| GET | `/admin/users/{id}/permissions` | User's global permissions |
| GET | `/admin/users/{id}/seat-permissions` | User's per-seat permissions |
| POST | `/admin/users/{id}/seat-permissions` | Grant seat access |
| DELETE | `/admin/users/{id}/seat-permissions/{buyer_id}` | Revoke seat access |
| POST | `/admin/users/{id}/permissions` | Grant global permission |
| DELETE | `/admin/users/{id}/permissions/{sa_id}` | Revoke global permission |
| GET | `/admin/audit-log` | Audit trail |
| GET | `/admin/stats` | Admin dashboard stats |
| GET | `/admin/settings` | System configuration |
| PUT | `/admin/settings/{key}` | Update system setting |
