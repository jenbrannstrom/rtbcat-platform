# Deploy Workflow

This repo now uses a staging-first promotion flow.

## Rule

Never deploy directly to `scan.rtb.cat`.

Every change must go through:

1. `main`
2. deploy to `vm2.scan.rtb.cat`
3. verify on staging
4. promote the same SHA to `scan.rtb.cat`

## Why

`vm2` is the last safe place to catch:

- frontend regressions
- schema drift
- auth/proxy regressions
- runtime config mistakes
- bad deploy assumptions

Production should only receive a SHA that already ran cleanly on staging.

## GitHub workflow

Use:

- `.github/workflows/deploy.yml`

It is manual only.

Inputs:

- `target = staging | production`
- `confirm = DEPLOY`
- `reason`
- `health_wait_seconds`
- `run_contract_check`
- `staging_verification_notes`

## Enforced promotion guard

Production deploys are blocked unless:

1. `vm2.scan.rtb.cat/api/health` is healthy
2. staging is already running the exact same SHA being promoted
3. `staging_verification_notes` is filled in

That means production is now a promotion step, not a fresh deploy gamble.

## Expected release sequence

### 1. Build images

Push to `main`.

This should produce image tags of the form:

- `catscan-api:sha-<shortsha>`
- `catscan-dashboard:sha-<shortsha>`

### 2. Deploy to staging

Run the deploy workflow with:

- `target=staging`
- `confirm=DEPLOY`
- `reason=<ticket or incident>`

### 3. Verify on vm2

Minimum checks:

1. `https://vm2.scan.rtb.cat/api/health`
2. login flow
3. the changed UI/API path
4. one critical seat workflow
5. contract check result, if enabled

Write a short note describing what was verified.

### 4. Promote to production

Run the same deploy workflow again with:

- `target=production`
- `confirm=DEPLOY`
- `reason=<same change context>`
- `staging_verification_notes=<what was tested on vm2>`

If staging is not on the same SHA, production promotion will fail.

## Recommended GitHub settings

In GitHub UI, configure environment protection:

- `staging`: optional reviewers
- `production`: required reviewer approval

That gives you:

1. workflow-level SHA guard
2. human approval gate for production

## Repo variables

Optional repo variables for deploy clarity:

- `STAGING_API_BASE_URL`
- `PRODUCTION_API_BASE_URL`

Defaults are:

- `https://vm2.scan.rtb.cat/api`
- `https://scan.rtb.cat/api`

## Operational note

If staging and production intentionally diverge at the infrastructure layer, that is a separate problem.

This workflow only works well if `vm2` is treated as a real pre-production environment, not an experimental side lane.
