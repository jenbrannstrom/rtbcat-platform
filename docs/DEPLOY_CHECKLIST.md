# Deploy Checklist

## Architecture

| Environment | VM Name | Zone | Purpose |
|-------------|---------|------|---------|
| **Staging** | `catscan-production-sg2` | `asia-southeast1-b` | Test before production |
| **Production** | `catscan-production-sg` | `asia-southeast1-b` | Live |

Both VMs pull prebuilt images from `asia-southeast1-docker.pkg.dev/catscan-prod-202601/catscan`.
Images are built by the CI workflow (`build-and-push.yml`) on every push and tagged `sha-<commit>`.

## Deploy Steps

All deploys go through one workflow: **CD Manual Deploy to GCP** (`deploy.yml`).

1. Go to **Actions > CD Manual Deploy to GCP > Run workflow**
2. Pick **staging** from the target dropdown
3. Type `DEPLOY` in the confirm field
4. Add a reason (optional but encouraged)
5. Click **Run workflow**
6. Wait for green — verify health check and contract check pass
7. Spot-check staging (`vm2.scan.rtb.cat` or SSH)
8. Repeat steps 1-6 with **production** target

**Always deploy to staging first.** That's the whole point of having two VMs.

## What the Workflow Does

1. Checks out the code at the triggering SHA
2. Authenticates to GCP via service account
3. SSHs to the target VM via IAP tunnel
4. Pulls latest code on the VM (`git reset --hard origin/unified-platform`)
5. Pulls prebuilt Docker images from Artifact Registry (`docker compose pull`)
6. Recreates containers (`docker compose up -d --force-recreate`)
7. Cleans up old images
8. Waits 60s, then runs a health check (`/health` endpoint)
9. Runs post-deploy contract check (`contracts_check.py`)
10. Uploads contract check artifact (90-day retention)

## Contract Check Failures

The contract check validates data integrity post-deploy. If it fails:

- Check the annotations on the failed run for the specific contract (e.g. `C-EPT-001`)
- If the failure is pre-existing and unrelated to your deploy, you can temporarily bypass:
  ```
  gh variable set ALLOW_CONTRACT_FAILURE --body "true"
  ```
- **Remove the bypass after investigation:**
  ```
  gh variable delete ALLOW_CONTRACT_FAILURE
  ```

## Post-deploy Verification

### Health
- API responds at `http://localhost:8000/health` on the VM
- `docker ps` shows all containers running

### Data
```sql
-- Check recent data coverage
SELECT 'home_funnel_daily' AS tbl, COUNT(*) AS rows, MAX(metric_date) AS latest
FROM home_funnel_daily WHERE metric_date >= CURRENT_DATE - 7
UNION ALL
SELECT 'rtb_daily', COUNT(*), MAX(metric_date)
FROM rtb_daily WHERE metric_date >= CURRENT_DATE - 7;
```

### Precompute Refresh (if needed)
```bash
python scripts/refresh_precompute.py --days 90 --validate
```

## Rollback

Re-run the workflow on a previous commit. The workflow uses `GITHUB_SHA` for the image tag,
so picking an older ref deploys the older image.

## GitHub Variables

Set via `gh variable set <name> --body "<value>"` or in Settings > Secrets and variables > Actions.

| Variable | Purpose | Current |
|----------|---------|---------|
| `GCP_PROJECT` | GCP project ID | (set in repo) |
| `GCP_ZONE` | VM zone | `asia-southeast1-b` |
| `IMAGE_REGISTRY` | Artifact Registry path | `asia-southeast1-docker.pkg.dev/catscan-prod-202601/catscan` |
| `GIT_BRANCH` | Branch to deploy | `unified-platform` |
| `ALLOW_CONTRACT_FAILURE` | Temporary bypass for contract gate | remove when not needed |

`VM_NAME` is **not** a variable — it's determined by the target dropdown in the workflow.
