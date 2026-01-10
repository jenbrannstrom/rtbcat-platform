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

After pushing to GitHub, deploy to `scan.rtb.cat`:

```bash
gcloud compute ssh catscan-production --zone=europe-west1-b --tunnel-through-iap -- \
  "cd /opt/catscan && sudo -u catscan git pull && sudo docker-compose -f docker-compose.gcp.yml down && sudo docker-compose -f docker-compose.gcp.yml up -d --build"
```

Or step by step:
1. `gcloud compute ssh catscan-production --zone=europe-west1-b --tunnel-through-iap`
2. `cd /opt/catscan && sudo -u catscan git pull`
3. `sudo docker-compose -f docker-compose.gcp.yml down && sudo docker-compose -f docker-compose.gcp.yml up -d --build`

Verify deployment:
```bash
sudo docker ps  # Both containers should be running
curl -s http://localhost:8000/health  # Should return healthy status
```

There is a Deploy key on github, so never make a tarball and upload directly from local to github