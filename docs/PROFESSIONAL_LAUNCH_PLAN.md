# Cat-Scan Professional Launch Plan

**Created:** January 12, 2026
**Status:** Ready to Execute
**Goal:** Transform Cat-Scan into a reliable, professional RTB analytics platform

---

## Executive Summary

Cat-Scan is a powerful RTB (Real-Time Bidding) analytics platform for Google Authorized Buyers. This plan outlines everything needed to run it as a professional, production-grade application.

**Monthly Operating Cost:** ~$6/month (GCP e2-micro)

---

## Current State Assessment

### What's Working
- FastAPI backend with comprehensive RTB analytics
- Next.js dashboard with modern UI
- Google Authorized Buyers API integration
- Gmail CSV report import automation
- Pretargeting config management
- SQLite database (simple, reliable, fast)

### What Needs Attention
1. **Database migrations** - Fixed (all 15 migrations now applied)
2. **CSV data import** - Need to configure Gmail OAuth
3. **Production hosting** - Ready to migrate to GCP e2-micro
4. **Monitoring** - Need uptime and error tracking

---

## Phase 1: Foundation (This Week)

### 1.1 Complete Data Pipeline

**Priority:** CRITICAL - Without data, nothing works.

```bash
# Step 1: Configure Gmail OAuth
python scripts/gmail_auth.py

# Step 2: Test import
python scripts/gmail_import.py --status

# Step 3: Run first import
python scripts/gmail_import.py
```

**Verify Success:**
```bash
sqlite3 ~/.catscan/catscan.db "SELECT COUNT(*) FROM rtb_daily;"
# Should show rows after import
```

### 1.2 Migrate to GCP e2-micro

**Cost:** ~$6/month | **Time:** 1-2 days

See [GCP_MIGRATION_PLAN.md](GCP_MIGRATION_PLAN.md) for detailed steps.

**Quick version:**
```bash
# 1. Create VM
gcloud compute instances create catscan-production \
  --zone=europe-west1-b \
  --machine-type=e2-micro \
  --image-family=ubuntu-2404-lts-amd64 \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=20GB \
  --boot-disk-type=pd-ssd

# 2. Copy database
gcloud compute scp ~/.catscan/catscan.db catscan-production:~/.catscan/

# 3. Deploy application
# (See deployment docs)
```

### 1.3 Set Up Automated Imports

**Schedule Gmail imports via Cloud Scheduler (free tier):**

```bash
gcloud scheduler jobs create http gmail-import \
  --location=europe-west1 \
  --schedule="0 8 * * *" \
  --uri="https://scan.rtb.cat/api/gmail/import" \
  --http-method=POST \
  --oidc-service-account-email=catscan-api@PROJECT.iam.gserviceaccount.com
```

---

## Phase 2: Reliability (Week 2)

### 2.1 Automated Backups

**Daily backup to Cloud Storage:**

```bash
# Create backup bucket
gsutil mb -l europe-west1 gs://catscan-backups-$(date +%Y)

# Add to crontab on VM
echo "0 3 * * * /usr/local/bin/catscan-backup" | crontab -
```

**Backup script** (`/usr/local/bin/catscan-backup`):
```bash
#!/bin/bash
DATE=$(date +%Y%m%d)
sqlite3 ~/.catscan/catscan.db ".backup /tmp/catscan-$DATE.db"
gzip /tmp/catscan-$DATE.db
gsutil cp /tmp/catscan-$DATE.db.gz gs://catscan-backups-$(date +%Y)/
rm /tmp/catscan-$DATE.db.gz

# Keep only last 30 days
gsutil ls -l gs://catscan-backups-$(date +%Y)/ | \
  sort -k2 | head -n -30 | awk '{print $3}' | \
  xargs -I {} gsutil rm {}
```

### 2.2 Uptime Monitoring (Free)

**Option A: UptimeRobot (Recommended)**
- Free tier: 50 monitors, 5-minute intervals
- URL: https://uptimerobot.com
- Monitor: `https://scan.rtb.cat/api/health`
- Alert via: Email, Telegram, Slack

**Option B: Google Cloud Monitoring**
```bash
# Create uptime check
gcloud monitoring uptime-check-configs create catscan-health \
  --display-name="Cat-Scan Health" \
  --monitored-resource-type="uptime_url" \
  --http-check-path="/api/health" \
  --period=300s
```

### 2.3 Error Tracking (Free Tier)

**Sentry.io** (Recommended for Python/JavaScript):
- Free tier: 5,000 errors/month
- Add to API: `pip install sentry-sdk`
- Add to Dashboard: `npm install @sentry/nextjs`

```python
# api/main.py
import sentry_sdk
sentry_sdk.init(dsn="YOUR_SENTRY_DSN", traces_sample_rate=0.1)
```

---

## Phase 3: Professional Features (Week 3-4)

### 3.1 Daily Email Reports

Automated daily summary sent to your email:

```python
# scripts/daily_report.py
async def send_daily_report():
    """Send daily RTB performance summary."""
    stats = await get_yesterday_stats()

    report = f"""
    Daily RTB Report - {date.today()}

    Reached Queries: {stats.reached:,}
    Impressions: {stats.impressions:,}
    Win Rate: {stats.win_rate:.1f}%
    Spend: ${stats.spend/1_000_000:.2f}

    Top Performers:
    {format_top_configs(stats.top_configs)}

    Alerts:
    {format_alerts(stats.alerts)}
    """

    await send_email(to="you@email.com", subject=f"Cat-Scan Daily - {date.today()}", body=report)
```

**Schedule via Cloud Scheduler:**
```bash
gcloud scheduler jobs create http daily-report \
  --schedule="0 9 * * *" \
  --uri="https://scan.rtb.cat/api/reports/daily" \
  --http-method=POST
```

### 3.2 Slack/Telegram Alerts

**Critical alert conditions:**
- Win rate drops below threshold
- Spend anomaly detected
- Import failure
- API errors

```python
# Example Telegram alert
async def send_alert(message: str):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    await httpx.post(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        json={"chat_id": chat_id, "text": message}
    )
```

### 3.3 Data Retention Policy

Keep storage costs low:

```sql
-- Delete data older than 90 days
DELETE FROM rtb_daily WHERE metric_date < date('now', '-90 days');

-- Vacuum to reclaim space
VACUUM;
```

**Automated cleanup script:**
```bash
# Run monthly
sqlite3 ~/.catscan/catscan.db "DELETE FROM rtb_daily WHERE metric_date < date('now', '-90 days');"
sqlite3 ~/.catscan/catscan.db "VACUUM;"
```

---

## Phase 4: Business Growth (Ongoing)

### 4.1 Documentation

Create user-facing documentation:

```
docs/
├── USER_GUIDE.md           # How to use the dashboard
├── API_REFERENCE.md        # API endpoints documentation
├── TROUBLESHOOTING.md      # Common issues and fixes
└── CHANGELOG.md            # Version history
```

### 4.2 Feature Roadmap

**Near Term (1-2 months):**
- [ ] Automated bid optimization recommendations
- [ ] Publisher blocklist management
- [ ] Creative performance comparison
- [ ] Export to Google Sheets

**Medium Term (3-6 months):**
- [ ] Multi-user support with roles
- [ ] Custom report builder
- [ ] API for external integrations
- [ ] Mobile-responsive dashboard improvements

**Long Term (6-12 months):**
- [ ] Machine learning for bid optimization
- [ ] Automated pretargeting adjustments
- [ ] Integration with other DSPs
- [ ] White-label option for agencies

### 4.3 Potential Revenue Streams

If you want to monetize:

| Model | Description | Potential |
|-------|-------------|-----------|
| **SaaS** | Charge per Authorized Buyers account | $50-200/account/month |
| **Consulting** | RTB optimization services | $100-200/hour |
| **Reports** | Custom analytics reports | $500-2000/report |
| **Training** | Authorized Buyers training | $500-1000/session |

---

## Operational Checklist

### Daily
- [ ] Check UptimeRobot for any downtime
- [ ] Review daily email report (when implemented)
- [ ] Verify Gmail import ran successfully

### Weekly
- [ ] Review error logs: `sudo journalctl -u catscan-api --since "1 week ago"`
- [ ] Check database size: `ls -lh ~/.catscan/catscan.db`
- [ ] Review pretargeting config performance

### Monthly
- [ ] Run data retention cleanup
- [ ] Review and update any blocklists
- [ ] Check GCP billing (should be ~$6)
- [ ] Test backup restore procedure

### Quarterly
- [ ] Security updates: `sudo apt update && sudo apt upgrade`
- [ ] Review and prune unused pretargeting configs
- [ ] Export critical data to external backup
- [ ] Review and update documentation

---

## Emergency Procedures

### If Site is Down

```bash
# 1. Check if VM is running
gcloud compute instances list

# 2. SSH to VM
gcloud compute ssh catscan-production --zone=europe-west1-b

# 3. Check services
sudo systemctl status nginx catscan-api

# 4. Check logs
sudo journalctl -u catscan-api --since "10 minutes ago"

# 5. Restart if needed
sudo systemctl restart catscan-api
sudo systemctl restart nginx
```

### If Database is Corrupted

```bash
# 1. Stop services
sudo systemctl stop catscan-api

# 2. Restore from backup
gsutil cp gs://catscan-backups-2026/catscan-YYYYMMDD.db.gz /tmp/
gunzip /tmp/catscan-YYYYMMDD.db.gz
mv ~/.catscan/catscan.db ~/.catscan/catscan.db.corrupted
mv /tmp/catscan-YYYYMMDD.db ~/.catscan/catscan.db

# 3. Restart
sudo systemctl start catscan-api
```

### If You Need to Roll Back

```bash
# 1. SSH to VM
gcloud compute ssh catscan-production --zone=europe-west1-b

# 2. Check git log
cd /opt/catscan && git log --oneline -10

# 3. Revert to previous commit
git checkout <previous-commit-hash>

# 4. Restart services
sudo systemctl restart catscan-api
```

---

## Cost Summary

### Monthly Operating Costs

| Item | Cost |
|------|------|
| GCE e2-micro | $0-6 |
| 20GB SSD | $3.40 |
| Cloud Storage (backups) | ~$0.50 |
| Cloud Scheduler | $0 (free tier) |
| Domain (scan.rtb.cat) | ~$1 (annual/12) |
| **Total** | **~$6-10/month** |

### Optional Add-ons

| Item | Cost | Benefit |
|------|------|---------|
| UptimeRobot Pro | $7/month | 1-minute checks, more monitors |
| Sentry Team | $26/month | More error tracking |
| Custom domain email | $6/month | Professional email |

---

## Success Metrics

Track these to measure success:

| Metric | Target | How to Measure |
|--------|--------|----------------|
| **Uptime** | >99.5% | UptimeRobot |
| **Import Success** | 100% | Check import_history table |
| **Dashboard Load Time** | <2 seconds | Chrome DevTools |
| **Data Freshness** | <24 hours | Compare latest metric_date |
| **Win Rate Trend** | Improving | Weekly comparison |

---

## Getting Help

### Self-Help Resources
- Check logs: `sudo journalctl -u catscan-api -f`
- Database queries: `sqlite3 ~/.catscan/catscan.db`
- API docs: `https://scan.rtb.cat/api/docs`

### External Resources
- Google Authorized Buyers: https://support.google.com/authorizedbuyers
- FastAPI docs: https://fastapi.tiangolo.com
- Next.js docs: https://nextjs.org/docs

### If Stuck
1. Check existing documentation in `/docs/`
2. Review error messages carefully
3. Search the codebase for similar patterns
4. Check GCP status: https://status.cloud.google.com

---

## Final Notes

This platform has real value - it provides visibility into RTB performance that many buyers lack. With proper operation:

1. **Reliability** comes from automation (backups, monitoring, scheduled imports)
2. **Low cost** comes from right-sizing (e2-micro is enough for now)
3. **Professionalism** comes from documentation and consistent operation

The foundation is solid. Focus on:
1. Getting data flowing (Gmail import)
2. Keeping it running (monitoring, backups)
3. Making it useful (daily reports, alerts)

**You've got this. Start with Phase 1 today.**

---

*Plan created by Claude Code. Last updated: January 12, 2026*
