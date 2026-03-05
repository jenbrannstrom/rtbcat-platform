# Chapter 12: Deployment

*Audience: DevOps, platform engineers*

## CI/CD pipeline

```
Push to unified-platform
         │
         ▼
build-and-push.yml (automatic)
  ├── Run contract & recovery tests
  ├── Build API image
  ├── Build Dashboard image
  └── Push to Artifact Registry
         │
         ▼ (manual trigger)
deploy.yml (workflow_dispatch)
  ├── SSH into VM via IAP tunnel
  ├── git pull on VM
  ├── docker compose pull (prebuilt images)
  ├── docker compose up -d --force-recreate
  ├── Health check (60s wait + curl localhost:8000/health)
  └── Post-deploy contract check
```

### Why deploy is manual

Auto-deploy on push was disabled after a January 2026 incident where
automatic deploys competed with manual SSH deployments, corrupting containers
and causing data loss. The deploy workflow now requires:

1. Manual trigger via GitHub Actions UI ("Run workflow")
2. Explicit target selection (staging or production)
3. Typing `DEPLOY` as confirmation
4. Optional reason field for audit trail

### Image tags

Images are tagged with the short git SHA: `sha-XXXXXXX`. The deploy step
uses `GITHUB_SHA` to construct the tag, so the deployed version always maps
to a specific commit.

## How to deploy

1. Verify the build passed: `gh run list --workflow=build-and-push.yml --limit=1`
2. Trigger deploy:
   ```bash
   gh workflow run deploy.yml \
     --ref unified-platform \
     -f target=production \
     -f confirm=DEPLOY \
     -f reason="your reason here"
   ```
3. Monitor: `gh run watch <run_id> --exit-status`
4. Verify: `curl -sS https://your-deployment.example.com/api/health | jq -r '.git_sha,.version'`

## Verifying a deploy

The `/api/health` endpoint returns:

```json
{
  "git_sha": "94e9cbb0",
  "version": "sha-94e9cbb"
}
```

Compare `git_sha` against the commit you intended to deploy.

## Post-deploy contract check

After deployment, the workflow runs `scripts/contracts_check.py` inside the
API container. This validates that data contracts (non-negotiable rules from
import through API output) are holding. If the check fails:

- With `ALLOW_CONTRACT_FAILURE=false` (default): deploy is marked as failed.
- With `ALLOW_CONTRACT_FAILURE=true` (temporary bypass): deploy succeeds with
  a warning. This bypass must be removed after investigation.

## Staging vs. production

| Environment | VM name | Domain |
|-------------|---------|--------|
| Staging | `catscan-vm` | (internal) |
| Production | `catscan-vm` | `your-deployment.example.com` |

Deploy to staging first, verify, then deploy to production.

## Rollback

To roll back, deploy a previous known-good commit:

1. Identify the last good SHA from git log or previous deploy runs.
2. Check out that SHA on unified-platform (or use `--ref` with the commit).
3. Trigger the deploy workflow.

There is no dedicated rollback mechanism. It's just deploying an older
version.

## Related

- [Architecture Overview](11-architecture.md): what gets deployed
- [Health Monitoring](13-health-monitoring.md): verifying the deploy worked
