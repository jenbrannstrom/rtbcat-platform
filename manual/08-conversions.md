# Chapter 8: Conversions and Attribution

*Audience: media buyers, campaign managers*

Conversion tracking lets Cat-Scan measure what happens after an impression:
did the user take a valuable action? This data feeds into the optimizer's
scoring and helps you evaluate true campaign performance.

## Conversion sources

Cat-Scan supports two integration methods:

### Pixel

A tracking pixel fires on your conversion page (e.g., checkout confirmation).

- Endpoint: `/api/conversions/pixel`
- Parameters: `buyer_id`, `source_type=pixel`, `event_name`, `event_value`,
  `currency`, `event_ts`
- No server-side setup required beyond placing the pixel on your page.

### Webhook

Your server sends conversion events to Cat-Scan's webhook endpoint.

- More reliable than pixels (no ad blockers, no client-side dependencies).
- Requires server-side integration.
- Supports HMAC signature verification for security.

## Webhook security

Cat-Scan provides layered webhook security:

| Feature | What it does |
|---------|-------------|
| **HMAC verification** | Each webhook request is signed with a shared secret. Cat-Scan rejects unsigned or mis-signed requests. |
| **Rate limiting** | Prevents abuse by capping requests per time window. |
| **Freshness monitoring** | Alerts if webhook events stop arriving (staleness detection). |

Configure webhook security at `/settings/system` > Conversion Health.

## Readiness check

Before relying on conversion data, verify readiness:

1. Go to `/settings/system` or the setup checklist.
2. Check **Conversion Readiness**: shows whether a source is connected and
   delivering events within the expected freshness window.
3. Check **Ingestion Stats**: event counts by source type and time period.

## Conversion health

The Conversion Health panel shows:

- Ingestion status (receiving events or not)
- Aggregation status (events being processed into metrics)
- Last event timestamp
- Error counts if any

## Related

- [The Optimizer](07-optimizer.md): conversion data improves scoring accuracy
- [Data Import](09-data-import.md): another data input path
- For DevOps: webhook endpoint configuration and troubleshooting, see
  [Integrations](17-integrations.md).
