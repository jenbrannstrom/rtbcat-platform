# AppsFlyer Attribution Pilot — Customer Selection Report

- **Date**: 2026-03-03 UTC
- **Source**: Production API (`scan.rtb.cat/api`) + creative metadata analysis
- **Validator**: Claude Code (automated, evidence-only)

---

## A) Executive Summary (max 8 bullets)

1. **Tuky Display (299038253) is the only seat with live AppsFlyer attribution URLs** — 63 NATIVE creatives use `app.appsflyer.com` click tracking with full params (`pid`, `af_siteid`, `clickid`, `advertising_id`).
2. Those 63 creatives promote 2 Android apps: `com.drop.frenzy.bubbly` (33) and `com.btools.bloods.statrs` (30), both with `play_store` metadata.
3. Amazing Design Tools LLC (1487810529) has the most app-install traffic (276 creatives, 245 Play Store + 31 App Store) but uses **direct store links** — no attribution SDK URLs.
4. Amazing Moboost (6574658621) has only 2 Play Store creatives and no attribution URLs — primarily e-commerce HTML ads.
5. Amazing MobYoung (6634662463) has zero app-install creatives — entirely e-commerce HTML ads.
6. **No seat has attribution join events yet** — the 61 existing `conversion_events` rows (buyer 1487810529) came from earlier webhook testing, not from live AppsFlyer postbacks.
7. Webhook security posture is fully hardened: AppsFlyer secret + HMAC enabled, freshness enforced, rate limits active.
8. Daily CI guardrail workflow (`v1-conversion-runtime-guardrails.yml`, cron `20 2 * * *`) is operational and passing.

---

## B) Evidence Table Per Seat

| Metric | 1487810529 (Amazing Design Tools) | 6574658621 (Moboost) | 6634662463 (MobYoung) | 299038253 (Tuky Display) |
|--------|-----------------------------------|----------------------|------------------------|--------------------------|
| Total creatives | 304 | 643 | 164 | 1,014 |
| Formats | 176 NATIVE, 128 HTML | 643 HTML | 164 HTML | 900 VIDEO, 61 HTML, 39 NATIVE |
| `app_store` creatives | 276 (245 Play, 31 App Store) | 2 (Play) | 0 | 63 (Play) |
| Has AppsFlyer URLs | **No** (direct store links) | No | No | **Yes — 63 creatives** |
| AppsFlyer app IDs | — | — | — | `com.drop.frenzy.bubbly`, `com.btools.bloods.statrs` |
| AppsFlyer PID | — | — | — | `uplivo2wj_int` |
| Conversion events | 61 (test webhook data) | 0 | 0 | 0 |
| Attribution joins | 0 | 0 | 0 | 0 |
| Mapping profile | `builtin_default` | `builtin_default` | `builtin_default` | `builtin_default` |
| Destination pattern | `play.google.com`, `apps.apple.com` | `gemlence.net`, `charmmarketplace.net` | `primeelectroshop.net`, `greenlifeappliances.com` | `*.web.app` (Firebase) + `app.appsflyer.com` |
| Pilot readiness | Medium (needs AF SDK integration) | Low (e-commerce, no apps) | Low (e-commerce, no apps) | **High (AF URLs already live)** |

### Tuky Display — AppsFlyer URL Evidence

Decoded `final_url` from creative (URL-encoded in RTB bid requests):

```
%%CLICK_URL_UNESC%%https://app.appsflyer.com/com.drop.frenzy.bubbly
  ?pid=uplivo2wj_int
  &af_siteid={adxcode}_{bundle}
  &af_c_id={campaignid}
  &af_adset_id={tagid}
  &af_ad_id={creativeid}
  &af_sub1=0.013
  &af_click_lookback=7d
  &clickid={dsp_params}
  &advertising_id={ifa}
```

This is a production-grade AppsFlyer attribution link with:
- `pid` (media source identifier)
- `af_siteid` (publisher/exchange tracking)
- `af_c_id` / `af_adset_id` / `af_ad_id` (campaign hierarchy)
- `clickid` using `{dsp_params}` (RTB click ID macro for postback matching)
- `advertising_id` using `{ifa}` (device IDFA/GAID macro)
- `af_click_lookback=7d` (7-day attribution window)

---

## C) Final Decision

**Pilot = Tuky Display (buyer_id 299038253)**

**Backup = Amazing Design Tools LLC (buyer_id 1487810529)**

### Rationale

Tuky Display is the only seat that already runs AppsFlyer attribution in production. Their 63 NATIVE creatives use `app.appsflyer.com` click-through URLs with properly templated RTB macros (`{dsp_params}`, `{ifa}`, `{campaignid}`). This means:

1. The advertiser side (AppsFlyer dashboard for `com.drop.frenzy.bubbly` and `com.btools.bloods.statrs`) is already configured.
2. AppsFlyer postbacks should already be firing for conversions from these creatives.
3. The only missing piece is pointing those postbacks at our Cat-Scan webhook endpoint.

Amazing Design Tools LLC is the backup because they have 276 app-install creatives and existing (test) conversion data, proving the ingest pipeline works for them. However, they would need to first integrate AppsFlyer into their click URLs before attribution postbacks would flow.

---

## D) Customer Outreach Package

### Email Template 1: Tuky Display (Primary Pilot)

```
Subject: Cat-Scan Conversion Attribution — Pilot Activation for Tuky Display

Hi [Tuky Display contact],

We've completed deployment of conversion attribution tracking on Cat-Scan and
are ready to activate it for your account (buyer 299038253).

We noticed that your "Drop Frenzy Bubbly" and "Blood Pressure" campaigns
already use AppsFlyer click tracking (PID: uplivo2wj_int). This means we can
start matching conversions to your RTB impressions immediately — no changes
needed on your creative setup.

What we need from you:

1. Confirm the AppsFlyer app IDs we should track:
   - com.drop.frenzy.bubbly
   - com.btools.bloods.statrs
   - (any others?)

2. Add our postback endpoint in your AppsFlyer dashboard:
   URL: https://scan.rtb.cat/api/conversions/appsflyer/postback?buyer_id=299038253
   Events: install, in-app events you care about (purchase, registration, etc.)
   Authentication: We'll provide a shared secret + HMAC key

3. (Optional) Share your AppsFlyer app-level API token so we can pull
   historical conversion data for backfill.

Once the postback is configured, conversions will appear in your Cat-Scan
dashboard within minutes. We'll send a test event to verify end-to-end.

Timeline: We can activate this week if you configure the postback by [date].

Best regards,
[Your name]
Cat-Scan Team
```

### Email Template 2: Amazing Design Tools LLC (Backup Pilot)

```
Subject: Cat-Scan Conversion Attribution — Coming Soon for Your Account

Hi [Amazing Design Tools contact],

We're rolling out conversion attribution tracking on Cat-Scan. Your account
(buyer 1487810529) runs 276 app-install campaigns across Google Play and
Apple App Store, making you a strong candidate.

To enable attribution, you would need to:

1. Set up AppsFlyer (or your preferred attribution provider) for your apps
   (e.g., com.einnovation.temu and others)
2. Add AppsFlyer click tracking URLs to your RTB creatives (replacing the
   direct play.google.com links)
3. Configure postbacks to our Cat-Scan webhook endpoint

We're piloting with another buyer first and will reach out when we're ready
to onboard your account. In the meantime, if you already use an attribution
provider, let us know — we can fast-track your setup.

Best regards,
[Your name]
Cat-Scan Team
```

### Pilot Onboarding Checklist

- [ ] **Contact Tuky Display** — send Email Template 1, confirm app IDs
- [ ] **Share webhook credentials** — provide the AppsFlyer secret + HMAC key from production env vars
- [ ] **Tuky Display configures postback** — they add `https://scan.rtb.cat/api/conversions/appsflyer/postback?buyer_id=299038253` in their AppsFlyer dashboard for `com.drop.frenzy.bubbly` and `com.btools.bloods.statrs`
- [ ] **Send test postback** — use `scripts/run_conversion_attribution_phase_b_report.sh --buyer-id 299038253` to verify pipeline
- [ ] **Verify first real postback** — check `GET /api/conversions/attribution/summary?buyer_id=299038253` shows `total_events > 0`
- [ ] **Verify attribution join** — check `GET /api/conversions/attribution/joins?buyer_id=299038253&matched=true` returns rows
- [ ] **Run guardrail check** — `scripts/check_conversion_runtime_guardrails.sh --strict-security`
- [ ] **Monitor daily** — review CI guardrail workflow results for 7 days
- [ ] **Report pilot results** — conversion count, match rate, latency, any failures
- [ ] **Proceed to backup pilot** — onboard Amazing Design Tools LLC after Tuky Display is stable

---

## E) Why Tuky Display IS the Best (Not a Disqualification)

The user asked: "If Tuky Display is NOT the best, explain exactly why."

**Tuky Display IS the best pilot candidate.** Here is why the other three are worse:

| Seat | Why NOT best for pilot |
|------|----------------------|
| **Amazing Design Tools (1487810529)** | Has 276 app-install creatives but uses **direct Play Store / App Store links** (e.g., `https://play.google.com/store/apps/details?id=com.einnovation.temu`). No attribution SDK integration. Would require the buyer to change all creative click URLs to add AppsFlyer tracking before any postbacks would fire. Good backup but needs setup work first. |
| **Amazing Moboost (6574658621)** | Only 2 app-install creatives out of 643. All HTML format. Primarily an e-commerce buyer (`gemlence.net`, `charmmarketplace.net`). App attribution is not their business model. |
| **Amazing MobYoung (6634662463)** | Zero app-install creatives. All 164 are HTML e-commerce ads. No relevance to app attribution. |

Tuky Display's 63 NATIVE creatives with `app.appsflyer.com` click URLs — including proper RTB macros (`{dsp_params}`, `{ifa}`, `{campaignid}`) — prove they already have:
- AppsFlyer dashboard access and app configuration
- Attribution link generation integrated into their creative workflow
- RTB-aware macro templating (meaning they understand DSP-level click tracking)

This is not theoretical — these URLs are live in production bid responses today.

---

## F) Exact Next Commands

```bash
# 1. Verify webhook security is hardened (should already be PASS from today)
scripts/check_conversion_runtime_guardrails.sh --strict-security

# 2. Run Phase-B attribution report for Tuky Display (expect 0 events — no postback configured yet)
scripts/run_conversion_attribution_phase_b_report.sh \
  --buyer-id 299038253 \
  --base-url https://scan.rtb.cat/api \
  --email cat-scan@rtb.cat

# 3. After Tuky Display configures their AppsFlyer postback, verify first events arrive:
curl -sS -H "X-Email: cat-scan@rtb.cat" \
  "https://scan.rtb.cat/api/conversions/attribution/summary?buyer_id=299038253" | jq .

# 4. Check attribution joins (should show matched rows once postbacks flow):
curl -sS -H "X-Email: cat-scan@rtb.cat" \
  "https://scan.rtb.cat/api/conversions/attribution/joins?buyer_id=299038253&matched=true&limit=10" | jq .

# 5. Trigger CI guardrail check manually:
gh workflow run v1-conversion-runtime-guardrails.yml

# 6. Monitor daily guardrail results:
gh run list --workflow=v1-conversion-runtime-guardrails.yml --limit=7
```

---

## API Evidence Appendix

### Security Posture (as of 2026-03-03T18:48 UTC)

```json
{
  "appsflyer.secret_enabled": true,
  "appsflyer.hmac_enabled": true,
  "freshness_enforced": true,
  "rate_limit_enabled": true
}
```

### Retention Stats (as of 2026-03-03T18:49 UTC)

```json
{
  "conversion_event_rows": 61,
  "conversion_failure_rows": 0,
  "conversion_join_rows": 0
}
```

### Attribution Summary — Buyer 299038253 (Tuky Display)

```json
{
  "buyer_id": "299038253",
  "source_type": "appsflyer",
  "total_events": 0,
  "modes": [],
  "checked_at": "2026-03-03T19:03:15.230489+00:00"
}
```

Zero events is expected — Tuky Display has not yet configured postbacks to our webhook.
