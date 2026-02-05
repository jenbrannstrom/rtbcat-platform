# Missing Country Data Report - 2026-02-03

**Generated:** 2026-02-03
**Data range in DB:** 2026-01-07 to 2026-01-25
**Issue:** Country field missing in CSV reports for these billing_ids

---

## Billing IDs with Missing Country Data

| done | billing_id | account_name | days_missing_country |
|------|------------|--------------|----------------------|
| [ ] | 165882941410 | Amazing MobYoung | 2026-01-21, 2026-01-22, 2026-01-23, 2026-01-24, 2026-01-25 |
| [ ] | 168508984471 | Amazing MobYoung | 2026-01-21 |
| [ ] | 167293473801 | Amazing Moboost | 2026-01-21, 2026-01-22, 2026-01-23, 2026-01-24 |
| [ ] | 165417469574 | Amazing Moboost | 2026-01-21, 2026-01-22, 2026-01-23, 2026-01-24 |
| [ ] | 164234840345 | Amazing Moboost | 2026-01-21, 2026-01-22, 2026-01-23, 2026-01-24 |
| [ ] | 166460852529 | Amazing Moboost | 2026-01-21, 2026-01-22, 2026-01-23, 2026-01-24 |
| [ ] | 161718481143 | Amazing Moboost | 2026-01-21, 2026-01-22, 2026-01-23, 2026-01-24 |
| [ ] | 164623975432 | Amazing Moboost | 2026-01-21, 2026-01-22, 2026-01-23, 2026-01-24 |
| [ ] | 168314893429 | Amazing Moboost | 2026-01-21, 2026-01-22, 2026-01-23, 2026-01-24 |
| [ ] | 168967069197 | Amazing Moboost | 2026-01-21, 2026-01-22, 2026-01-23, 2026-01-24 |
| [ ] | 178022294840 | Amazing Moboost | 2026-01-24 |
| [ ] | 157331516553 | Tuky Display | 2026-01-21, 2026-01-22, 2026-01-23, 2026-01-24 |
| [ ] | 156494841242 | Tuky Display | 2026-01-21, 2026-01-22, 2026-01-23, 2026-01-24 |
| [ ] | 72245759413 | Tuky Display | 2026-01-21, 2026-01-22, 2026-01-23, 2026-01-24 |
| [ ] | 83435423204 | Tuky Display | 2026-01-21, 2026-01-22, 2026-01-23, 2026-01-24 |
| [ ] | 151274651962 | Tuky Display | 2026-01-21, 2026-01-22, 2026-01-23, 2026-01-24 |
| [ ] | 104602012074 | Tuky Display | 2026-01-21, 2026-01-22, 2026-01-23, 2026-01-24 |
| [ ] | 155546863666 | Tuky Display | 2026-01-21, 2026-01-22, 2026-01-23, 2026-01-24 |
| [ ] | 153322387893 | Tuky Display | 2026-01-21 |

---

## Summary by Account

| Account | Billing IDs Affected | Date Range |
|---------|---------------------|------------|
| Amazing MobYoung | 2 | 2026-01-21 to 2026-01-25 |
| Amazing Moboost | 9 | 2026-01-21 to 2026-01-24 |
| Tuky Display | 8 | 2026-01-21 to 2026-01-24 |

---

## Action Required

**For 7-day backfill, pull reports with Country dimension for:**
- Date range: **2026-01-28 through 2026-02-03** (recent missing days)
- Plus backfill: **2026-01-21 through 2026-01-25** (historical missing country)

**Report dimensions to include:**
- Billing ID
- Country (currently missing)
- Creative ID
- Creative Size
- Date
