# Deploy Checklist (API + Dashboard)

Use this for the two pending fixes:
- Publisher List UI (commits `1fea149`, `dffd69a`, `50db7d6`)
- Size drill‑down fix (commit `72213ac`)

## 1) Pre‑deploy sanity

- Confirm target branch: `origin/unified-platform`
- Confirm DSNs set: `POSTGRES_DSN`, `POSTGRES_SERVING_DSN`
- Confirm BigQuery pipeline running (raw_facts current)

## 2) Deploy steps

1. Deploy API + dashboard images (normal pipeline).
2. Apply size drill‑down fix (`72213ac`) in the deployed build.
3. Apply Publisher List UI commits (`1fea149`, `dffd69a`, `50db7d6`) in the deployed build.

## 3) Post‑deploy refresh

Run config precompute refresh for the last 90 days:

```bash
python scripts/refresh_precompute.py --days 90 --validate
```

Optional seat‑scoped:

```bash
python scripts/refresh_precompute.py --days 90 --buyer-id BUYER_ACCOUNT_ID --validate
```

## 4) Verification checklist

### Publisher List UI
- Edit flow matches `docs/ui-publisher-list-management.md`
- Add/remove publisher works; list updates immediately
- Mode toggle (Blacklist/Whitelist) consistent
- Bulk import/export buttons render (and action wiring if present)

### Size drill‑down
- Size list shows creatives (no “No creatives for size” mismatch)
- Drill‑down no longer reports “No precompute” after refresh
- `config_creative_daily.creative_size` populated for recent dates

### Data health
- `precompute_refresh_log` updated (latest run timestamps)
- `home_*_daily`, `rtb_*_daily`, `config_*_daily` have recent rows

