# Chapter 17: Integrations

*Audience: DevOps, platform engineers*

## GCP service accounts

Cat-Scan needs GCP service account credentials to interact with Google APIs.

**Setup:**
1. Create a service account in your GCP project with Authorized Buyers API
   access.
2. Download the JSON key file.
3. Upload it at `/settings/accounts` > API Connection tab.
4. Validate the connection: Cat-Scan tests reachability and permissions.

**What it enables:**
- Seat discovery (`discoverSeats`)
- Pretargeting config sync (`syncPretargetingConfigs`)
- RTB endpoint sync (`syncRTBEndpoints`)
- Creative collection (`collectCreatives`)

**Project status:**
Check GCP project health at `/settings/accounts` or via
`GET /integrations/gcp/project-status`. This verifies the service account
is valid, the project is accessible, and required APIs are enabled.

## Google Authorized Buyers API

Cat-Scan syncs data from the Authorized Buyers API:

| Operation | What it pulls | When to run |
|-----------|--------------|-------------|
| **Seat discovery** | Buyer accounts linked to the service account | Initial setup, when new seats are added |
| **Pretargeting sync** | Current pretargeting config state from Google | After external changes in the AB UI |
| **RTB endpoint sync** | Bidder endpoint URLs and status | Initial setup, after endpoint changes |
| **Creative sync** | Creative metadata (formats, sizes, destinations) | Periodically, via "Sync All" in sidebar |

## Gmail integration

Google Authorized Buyers emails daily CSV reports. Cat-Scan can ingest these
automatically.

**Setup:**
1. Go to `/settings/accounts` > Gmail Reports tab.
2. Authorize Cat-Scan to access the Gmail account that receives AB reports.
3. Cat-Scan will poll for new report emails and import attached CSVs.

**Monitoring:**
- `GET /gmail/status`: current state, unread count, last reason
- `POST /gmail/import/start`: manually trigger an import cycle
- `POST /gmail/import/stop`: stop a running import
- `GET /gmail/import/history`: past import records

**Troubleshooting:**
- Large unread count (30+): import backlog, may need manual intervention
- `last_reason: error`: check logs, may need re-authorization
- See [Troubleshooting](15-troubleshooting.md) for detailed steps.

## Language AI providers

Cat-Scan uses AI to detect creative language and flag geo-linguistic
mismatches (e.g., Spanish ad in an Arabic market).

**Supported providers:**

| Provider | Configuration |
|----------|---------------|
| Gemini | API key at `/settings/accounts` |
| Claude | API key at `/settings/accounts` |
| Grok | API key at `/settings/accounts` |

Configure via `GET/PUT /integrations/language-ai/config`. Only one provider
needs to be active.

## Conversion webhooks

External systems send conversion events to Cat-Scan via webhooks.

**Security layers:**

| Layer | Purpose | Configuration |
|-------|---------|---------------|
| **HMAC verification** | Ensures requests are authentic (signed with shared secret) | Shared secret configured in webhook settings |
| **Rate limiting** | Prevents abuse | Automatic, configurable thresholds |
| **Freshness monitoring** | Alerts when events stop arriving | Configurable staleness window |

**Monitoring:**
- `GET /conversions/security/status`: HMAC status, rate limit
  status, freshness status
- `GET /conversions/health`: overall ingestion and aggregation health
- `GET /conversions/readiness`: whether conversion data is fresh enough
  to trust

## Related

- [Architecture Overview](11-architecture.md): where integrations fit
- [User Administration](16-user-admin.md): managing service accounts
- For media buyers: [Conversions and Attribution](08-conversions.md) covers
  the buyer-facing conversion setup.
