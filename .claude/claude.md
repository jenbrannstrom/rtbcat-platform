# Cat-Scan Project Context

## CRITICAL: Browser Testing with MCP

**ALWAYS USE CHROMIUM, NEVER CHROME!**

When using MCP chrome-devtools for browser interaction:
1. First launch Chromium with remote debugging:
   ```bash
   chromium-browser --remote-debugging-port=9222 --no-first-run "URL_HERE" &
   ```
2. Wait 2-3 seconds for it to start
3. Then use mcp__chrome-devtools__* tools

**DO NOT** try to connect to Chrome - it won't work. Only Chromium is configured.

## URLs
- Production: https://scan.rtb.cat
- Local Dashboard: http://localhost:3000
- Local API: http://localhost:8000

## Deploying Updates to Production

**Deployment flow: Local → GitHub → VM (via SSH pull)**

### Step 1: Push to GitHub
```bash
git add -A && git commit -m "Your message"
git push origin unified-platform
```

### Step 2: Deploy via helper script
```bash
gcloud compute ssh catscan-production --zone=europe-west1-b -- "catscan-deploy"
```

Or for a specific branch:
```bash
gcloud compute ssh catscan-production --zone=europe-west1-b -- "catscan-deploy main"
```

### CRITICAL RULES

- **Code MUST go through GitHub** - Never skip `git push`
- **Never upload directly** - No tarballs, no scp of code files
- **One deployment at a time** - Wait for docker-compose to finish before starting another

### If Deploy Fails

1. Check container logs: `gcloud compute ssh catscan-production --zone=europe-west1-b -- "catscan-logs 100 error"`
2. Fix the issue in code locally
3. Push fix to GitHub, then deploy again


## Server Helper Commands

**ALWAYS use these helper scripts instead of constructing raw commands with complex quoting.**

### Database Queries: catscan-db
```bash
gcloud compute ssh catscan-production --zone=europe-west1-b -- "catscan-db 'YOUR SQL QUERY'"
```

Examples:
```bash
# List all tables
gcloud compute ssh catscan-production --zone=europe-west1-b -- "catscan-db '.tables'"

# Show table schema
gcloud compute ssh catscan-production --zone=europe-west1-b -- "catscan-db '.schema rtb_bidstream'"

# Query data
gcloud compute ssh catscan-production --zone=europe-west1-b -- "catscan-db 'SELECT * FROM rtb_bidstream LIMIT 10'"

# Aggregations
gcloud compute ssh catscan-production --zone=europe-west1-b -- "catscan-db 'SELECT COUNT(*) FROM creatives'"
```

### View Logs: catscan-logs
```bash
# Last 50 lines (default)
gcloud compute ssh catscan-production --zone=europe-west1-b -- "catscan-logs"

# Last 100 lines
gcloud compute ssh catscan-production --zone=europe-west1-b -- "catscan-logs 100"

# Filter for errors
gcloud compute ssh catscan-production --zone=europe-west1-b -- "catscan-logs 200 error"

# Filter for specific term
gcloud compute ssh catscan-production --zone=europe-west1-b -- "catscan-logs 100 rtb-funnel"
```

### Test API Endpoints: catscan-api
```bash
# Health check
gcloud compute ssh catscan-production --zone=europe-west1-b -- "catscan-api /health"

# Get analytics (note: may require auth)
gcloud compute ssh catscan-production --zone=europe-west1-b -- "catscan-api /analytics/rtb-funnel?days=7"
```

### Deploy: catscan-deploy
```bash
# Deploy unified-platform branch (default)
gcloud compute ssh catscan-production --zone=europe-west1-b -- "catscan-deploy"

# Deploy specific branch
gcloud compute ssh catscan-production --zone=europe-west1-b -- "catscan-deploy main"
```

## DO NOT DO THIS

Never construct raw sqlite3/docker commands with complex quoting like:
```bash
# BAD - quoting nightmare, will fail
gcloud compute ssh catscan-production -- "sudo sqlite3 /path/to/db 'SELECT * FROM table WHERE x = \"value\"'"
```

Always use the helper scripts instead - they handle quoting internally.