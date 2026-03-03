# Frequently Asked Questions

Questions are tagged by audience: **[Buyer]** for media buyers and campaign
managers, **[DevOps]** for platform engineers, **[Both]** for shared questions.

---

### [Buyer] Why is my coverage percentage below 100%?

Coverage measures how many date x report-type cells have data vs. how many
are expected. Common reasons for gaps:

- **Google didn't send a report** for that date (public holiday, export lag).
- **Gmail import missed the email** (check Gmail status).
- **A specific report type is not available** for your seat (e.g., quality
  data may not exist for all buyers).

Check the data freshness grid on `/import` to see exactly which cells are
missing. See [Data Import](09-data-import.md).

### [Buyer] What's the difference between "waste" and "low win rate"?

**Waste** = bid requests your bidder *rejected* without bidding. This is QPS
you paid for but couldn't use at all. Fix it with pretargeting.

**Low win rate** = bid requests your bidder *bid on* but lost the auction.
This means your bids are not competitive enough. Fix it with bid strategy,
not pretargeting.

Both show up in the funnel but require different actions. See
[Understanding Your QPS Funnel](03-qps-funnel.md).

### [Buyer] Can I undo a pretargeting change?

Yes. Go to `/history`, find the change, click "Preview rollback" to see what
will revert, then confirm. The rollback itself is recorded. See
[Pretargeting Configuration](06-pretargeting.md).

### [Buyer] How often should I re-import data?

Daily. Gmail auto-import handles this automatically. If you're importing
manually, do it once per day after reports arrive. Stale data means stale
decisions.

### [Buyer] What does the optimizer actually change?

The optimizer proposes changes to your pretargeting configs: adding or removing
geos, sizes, publishers, etc. It never applies changes automatically. You
review and approve each proposal. See [The Optimizer](07-optimizer.md).

---

### [DevOps] Why did the runtime health strict gate fail?

Check the workflow logs: `gh run view <id> --log-failed`. Look for FAIL vs.
BLOCKED:

- **FAIL** = something broke. The data-freshness timeout and SET
  statement_timeout issues are common culprits. See
  [Troubleshooting](15-troubleshooting.md).
- **BLOCKED** = a dependency is missing, not necessarily a code bug. Examples:
  no quality data for this buyer, proposal has no billing_id. Compare against
  previous runs to distinguish regressions from pre-existing gaps.

### [DevOps] Why is the data-freshness endpoint slow?

The query scans `rtb_daily` (~84M rows) and `rtb_bidstream` (~21M rows). If
the query plan degrades to a sequential scan instead of using the
`(buyer_account_id, metric_date DESC)` indexes, it will take minutes.

Fix: ensure queries use the `generate_series + EXISTS` pattern (14 index
lookups instead of full table scan). See [Database Operations](14-database.md).

### [DevOps] How do I check what version is deployed?

```bash
curl -sS https://scan.rtb.cat/api/health | jq -r '.git_sha,.version'
```

This returns the git SHA and image tag. Compare against your commit log.

### [DevOps] How do I deploy a fix?

1. Push to `unified-platform`
2. Wait for `build-and-push.yml` to succeed
3. Trigger `deploy.yml` via `gh workflow run` with `confirm=DEPLOY`
4. Verify with `/api/health`

See [Deployment](12-deployment.md) for the full procedure.

### [DevOps] Users are stuck in a login loop. What do I do?

Check Cloud SQL Proxy: `sudo docker ps | grep cloudsql`. If it's down,
restart it, wait 10 seconds, then restart the API container. See
[Troubleshooting](15-troubleshooting.md) for the full procedure.

---

### [Both] Where does Cat-Scan's data come from?

Google Authorized Buyers CSV exports. There is no Reporting API. Data arrives
either by manual CSV upload or automatic Gmail ingestion. See
[Data Import](09-data-import.md).

### [Both] Is it safe to re-import the same CSV?

Yes. Every row is hashed and deduplicated. Re-importing never double-counts.

### [Both] What languages does the UI support?

English, Dutch, and Chinese (Simplified). The language selector is in the
sidebar.
