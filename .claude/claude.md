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

**GitHub Actions handles ALL deployments automatically on push to `unified-platform` branch.**

Simply push your changes:
```bash
git push origin unified-platform
```

Check deployment status:
```bash
gh run list --repo jenbrannstrom/rtbcat-platform --limit 1
```

Trigger manual deploy (if needed):
```bash
gh workflow run deploy.yml --repo jenbrannstrom/rtbcat-platform
```

### CRITICAL: DO NOT

- **DO NOT** SSH into the VM for deployment
- **DO NOT** run docker commands manually on the server
- **DO NOT** try to "fix" failed deployments via SSH

Manual SSH interference WILL break the deployment and cause downtime.

### If Deploy Fails

1. Check the error in GitHub Actions logs
2. Fix the issue in code
3. Push the fix - GitHub Actions will retry automatically

There is a Deploy key on GitHub, so never make a tarball and upload directly from local to server