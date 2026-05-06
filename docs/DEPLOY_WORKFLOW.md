# Deploy Workflow

GitHub is the deployment source of truth. Production deploys come from a GitHub
commit, prebuilt Artifact Registry images, and the manual GitHub Actions deploy
workflow.

Staging has been retired. Do not use `vm2` as a promotion gate.

## Rule

Deploy only code that is committed to GitHub.

The production release path is:

1. merge or commit to `main`
2. `build-and-push.yml` builds API/dashboard images tagged `sha-<shortsha>`
3. run `.github/workflows/deploy.yml` manually
4. the workflow deploys the exact SHA to the production GCE VM
5. the workflow verifies health, deployed SHA, secrets health, and contracts

## GitHub Workflow

Use:

- `.github/workflows/build-and-push.yml`
- `.github/workflows/deploy.yml`

The deploy workflow is manual only.

Inputs:

- `target = production`
- `confirm = DEPLOY`
- `reason`
- `health_wait_seconds`
- `image_wait_seconds`
- `run_contract_check`

## Expected Release Sequence

### 1. Build Images

Push to `main`.

This produces image tags of the form:

- `catscan-api:sha-<shortsha>`
- `catscan-dashboard:sha-<shortsha>`

### 2. Deploy Production

Run the deploy workflow with:

```bash
gh workflow run deploy.yml \
  --ref main \
  -f target=production \
  -f confirm=DEPLOY \
  -f reason="<ticket or incident>"
```

### 3. Verify Production

Minimum checks:

1. `https://scan.rtb.cat/health`
2. `https://scan.rtb.cat/api/health`
3. login flow
4. the changed UI/API path
5. one critical buyer-seat workflow
6. contract check result, if enabled

The health payload must report the intended `git_sha` or `version`.

## Rollback

Rollback is a production deploy of a previous known-good GitHub SHA.

```bash
gh workflow run deploy.yml \
  --ref <known-good-sha> \
  -f target=production \
  -f confirm=DEPLOY \
  -f reason="rollback to <known-good-sha>"
```

## Recommended GitHub Settings

In GitHub UI, configure the `production` environment with required reviewer
approval. That keeps production changes explicit while keeping GitHub as the
single release source.

## Required Repo Variables

- `GCP_PROJECT`
- `GCP_REGION`
- `GCP_ZONE`
- `GCP_VM_PRODUCTION`
- `CLOUDSQL_INSTANCE`
- `CLOUDSQL_CONNECTION_NAME`
- `IMAGE_REGISTRY`
- `GCP_REPOSITORY`
- `GCP_REGISTRY_HOST`
- `PRODUCTION_API_BASE_URL`

Required GitHub secret:

- `GCP_SA_KEY`

## Recovery

Production rebuild and recovery steps live in
[PRODUCTION_RECOVERY.md](PRODUCTION_RECOVERY.md).
