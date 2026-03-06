# Moboost UI Data Audit + RCA (2026-03-06)

## Incident
- Reported symptom: on `https://scan.rtb.cat/6574658621?days=30`, the "By Creative" table looked implausibly low for Moboost spend.
- Screenshot reference: `/home/x1-7/Pictures/Screenshots/Screenshot from 2026-03-06 00-41-03.png`
- Screenshot showed top context date: `Data as of 2026-03-01`.

## What was audited
- UI query path for config breakdowns.
- API/service/repository path that serves "By Creative".
- Production data freshness in:
  - `home_config_daily`
  - `config_creative_daily`
  - `config_size_daily`
  - `precompute_refresh_runs`
  - `rtb_daily`
- Active pretargeting config inventory vs delivered spend buckets.

## Findings
1. The selected config (`billing_id=161718481143`) is not account-total spend.
   - 30d config total (from `config_creative_daily`): `$25,144.88`, 13 creatives.
   - The screenshot row (`..._7749`) is `$528.07`; it exists but is not the config max.
   - Top creatives for that config are `$6.8k`, `$6.2k`, `$3.7k`, `$3.6k`, etc.

2. A very large unattributed bucket exists under `billing_id='unknown'`.
   - Buyer `6574658621`, 30d `config_creative_daily` total: `$347,396.90`.
   - `unknown` share: `$180,615.56` (~52%).
   - `unknown` appears in home config payload, but not in active Google pretargeting configs list.

3. Config breakdown tables are stale after `2026-02-28`.
   - `config_creative_daily` max date: `2026-02-28`.
   - `config_size_daily` max date: `2026-02-28`.
   - `home_config_daily` continues through `2026-03-06`.

4. Root failure in config breakdown backfill is reproducible from run history.
   - `precompute_refresh_runs` failures (`cache_name=config_breakdowns`) repeatedly show:
     - `null value in column "clicks" of relation "fact_delivery_daily" violates not-null constraint`
   - Failing rows are from dates starting `2026-03-01`.

5. Upstream raw rows changed semantics on/after `2026-03-01`.
   - In `rtb_daily`, `clicks` is null for all sampled rows from `2026-03-01` to `2026-03-05`.
   - Pre-`2026-03-01` rows had non-null clicks.

## Root cause
- In canonical reconciliation (`services/config_precompute.py`), billing-level inserts used `SUM(clicks)`.
- Once source rows had all-null clicks for a group, `SUM(clicks)` returned `NULL`.
- Insert into `fact_delivery_daily.clicks` (`NOT NULL`) failed.
- Failure aborted full config breakdown refresh runs, leaving `config_creative_daily` / `config_size_daily` stale.

## Code fix applied (local)
- File: `services/config_precompute.py`
- Change in `_refresh_canonical_reconciliation`:
  - `SUM(clicks)` -> `COALESCE(SUM(clicks), 0)` in both billing geo and billing publisher inserts.
- Validation:
  - `python3 -m py_compile services/config_precompute.py` passed.

## Why UI appeared false
- It was a combination of:
  - stale config breakdown tables (missing dates after 2026-02-28), and
  - large spend in an `unknown` billing bucket not shown in the active pretargeting config list.
- The specific `$528` creative value is real for that config row, but it is not representative of seat-total spend.

## Immediate remediation steps
1. Deploy the `COALESCE(SUM(clicks), 0)` patch.
2. Run config-breakdown backfill for `2026-03-01` onward.
3. Verify:
   - `MAX(metric_date)` advances in `config_creative_daily` and `config_size_daily`.
   - `/6574658621?days=30` "By Creative" reflects refreshed dates.
4. Product follow-up:
   - surface unattributed/`unknown` bucket explicitly in UI, or add clear "not in active pretargeting config list" indicator.

