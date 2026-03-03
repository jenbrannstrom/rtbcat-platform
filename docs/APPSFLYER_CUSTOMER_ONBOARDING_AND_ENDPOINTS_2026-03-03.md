# AppsFlyer Customer Onboarding and Endpoint Pack (2026-03-03)

## Decision (what is correct per AppsFlyer docs)

Yes: customer-side configuration to send server-to-server data to our endpoint is a valid AppsFlyer pattern.

Two AppsFlyer-supported routes exist:

1. Push API endpoint (customer account owner configures endpoint URL in AppsFlyer).
2. Partner/default postback endpoint integration (ad-network style setup).

For Cat-Scan rollout, we use **Push API -> Cat-Scan webhook endpoint** first because it is straightforward to test per buyer.

Important AppsFlyer caveat: AppsFlyer docs warn about privacy and media-source terms when sending attributed user-level data to third parties. Treat Cat-Scan as a customer-approved data processor and get customer/legal confirmation before enabling production traffic.

## Cat-Scan endpoint status

Implemented and live in API:

- `POST /api/conversions/appsflyer/postback`
- Optional query override: `buyer_id=<seat_id>`
- Mapping profile APIs: `GET/PUT /api/conversions/mapping-profile`
- Attribution diagnostics APIs:
  - `POST /api/conversions/attribution/refresh`
  - `GET /api/conversions/attribution/summary`
  - `GET /api/conversions/attribution/joins`

## Buyer-specific endpoint URLs (4 active seats)

Use HTTPS `POST`.

| Buyer | Buyer ID | Endpoint URL |
|---|---:|---|
| Amazing Design Tools LLC | `1487810529` | `https://scan.rtb.cat/api/conversions/appsflyer/postback?buyer_id=1487810529` |
| Amazing Moboost | `6574658621` | `https://scan.rtb.cat/api/conversions/appsflyer/postback?buyer_id=6574658621` |
| Amazing MobYoung | `6634662463` | `https://scan.rtb.cat/api/conversions/appsflyer/postback?buyer_id=6634662463` |
| Tuky Display | `299038253` | `https://scan.rtb.cat/api/conversions/appsflyer/postback?buyer_id=299038253` |

## Internal process (operator)

1. Generate webhook secret.
2. Share endpoint URL + secret with customer.
3. Ask customer to send exactly 1 test event first.
4. Validate ingestion and attribution readiness.

### 1) Generate secret

```bash
openssl rand -hex 32
```

Store as:

- `CATSCAN_APPSFLYER_WEBHOOK_SECRET`

### 2) Share customer config packet

- Endpoint URL for that buyer (table above)
- HTTP method: `POST`
- Header: `X-Webhook-Secret: <shared-secret>`
- Content type: `application/json`
- Send test event first, then switch to production flow

### 3) Internal validation commands

Run after first test event:

```bash
scripts/run_appsflyer_phase_a_audit.sh --buyer-id <id> --from-db --db-since-days 30
scripts/run_conversion_attribution_phase_b_report.sh --buyer-id <id>
```

Interpretation:

- Phase A confirms field coverage/mapping viability from real ingested payloads.
- Phase B confirms join refresh API path and evidence output.

## Customer email template (copy/paste)

Subject: AppsFlyer -> Cat-Scan postback setup for buyer `<BUYER_ID>`

Hello `<Customer Name>`,

Please configure an AppsFlyer Push API endpoint for this buyer:

- Endpoint URL: `<BUYER_ENDPOINT_URL>`
- Method: `POST`
- Header: `X-Webhook-Secret: <SECRET_FROM_CATSCAN>`
- Content-Type: `application/json`

Please send 1 test conversion event first and reply with timestamp (UTC).
After we validate ingestion and attribution diagnostics, we will confirm production enablement.

Thanks,
Cat-Scan Ops

## Do we need dedicated subdomains?

Not required for current rollout.

Current safe baseline is:

- per-provider webhook secrets
- optional HMAC
- replay/freshness enforcement
- rate limiting

A dedicated ingest subdomain (for example `ingest.scan.rtb.cat`) is recommended later for operational isolation (separate WAF policy, tighter routing, easier traffic controls), but it is not a blocker for onboarding the first customers.

## Do we need our own AppsFlyer account?

- For the Push API webhook route above: **No separate Cat-Scan AppsFlyer account is required**. The customer configures delivery from their AppsFlyer account to our endpoint URL.
- For official AppsFlyer ad-network/partner integration: **Yes**, that is a separate AppsFlyer partner onboarding track and may require AppsFlyer review/enablement.

## Is GCP ready?

Yes for Phase A/B ingestion path:

- webhook endpoint exists
- conversion event ingestion path exists
- mapping profile and attribution diagnostics endpoints are live
- Phase-B backend deployment evidence is already captured

Remaining dependency is customer-side AppsFlyer endpoint configuration and real event flow.

## Next roadmap step (immediate)

1. Run customer onboarding for all 4 buyers using this packet.
2. Collect first real event per buyer.
3. Run Phase-A + Phase-B scripts and publish buyer contract/evidence docs.
4. Start ingestion lineage counters and readiness status in UI for `No AF`, `AF no clickid`, `AF exact-ready`.

## External references

- AppsFlyer Push API (user-level data to endpoint): https://support.appsflyer.com/hc/en-us/articles/360007530258-Push-API-user-level-data-to-endpoint
- AppsFlyer integrated partners management (default postback endpoint field): https://support.appsflyer.com/hc/en-us/articles/4410481112081-Manage-integrated-partners
