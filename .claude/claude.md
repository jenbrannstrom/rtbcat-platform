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

### Step 2: SSH to VM and pull
```bash
gcloud compute ssh catscan-production --zone=europe-west1-b --tunnel-through-iap
```

On the VM:
```bash
cd /opt/catscan
sudo -u catscan git fetch origin
sudo -u catscan git reset --hard origin/unified-platform
sudo docker-compose -f docker-compose.gcp.yml down --remove-orphans
sudo docker-compose -f docker-compose.gcp.yml up -d --build
```

### CRITICAL RULES

- **Code MUST go through GitHub** - Never skip `git push`
- **Never upload directly** - No tarballs, no scp of code files
- **One deployment at a time** - Wait for docker-compose to finish before starting another

### If Deploy Fails

1. Check container logs: `sudo docker-compose -f docker-compose.gcp.yml logs`
2. Fix the issue in code locally
3. Push fix to GitHub, then SSH and pull again