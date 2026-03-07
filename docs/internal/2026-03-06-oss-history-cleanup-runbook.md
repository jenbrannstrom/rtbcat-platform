# OSS History Cleanup Runbook

Date: 2026-03-06

## Scope

This runbook covers the remaining blockers before a public OSS release:

1. Verify the rotated Gmail OAuth desktop client in GCP is live and usable.
2. Rewrite git history to remove internal deployment artifacts and leaked credentials.
3. Verify the rewritten repo is clean and only then publish the rewritten refs.

## Confirmed Secret State

Verified on 2026-03-06 via `gcloud`:

- `catscan-oauth-client-secret`
  - Latest value does **not** match leaked historical secret.
  - Versions created on 2026-03-05.
- `catscan-oauth-client-secret-sg2`
  - Latest value does **not** match leaked historical secret.
  - Versions created on 2026-03-05.
- `catscan-gmail-oauth-client`
  - Version `2` created on 2026-03-07.
  - Latest JSON no longer matches the leaked historical Google OAuth client ID or client secret.
  - Latest payload is stored in `web` JSON shape; this is acceptable because `InstalledAppFlow.from_client_secrets_file(...)` accepts either `web` or `installed`.

Conclusion: SG1/SG2 OAuth proxy secrets and the Gmail OAuth client have all been rotated.

## History Rewrite Targets

Remove from history:

- `docs/ai_logs/`
- `docs/AWS_DEPLOYMENT.md`
- `docs/vm-rebuild-runbook.md`
- `creative-intelligence/venv/`
- all historical `*.tfstate`
- all historical `*.tfstate.backup`
- all historical `terraform.tfvars`

Scrub from any surviving blobs:

- old hardcoded Caddy auth token
- old synthetic test fixture `sk-test-1234567890`

## Rehearsal Script

The repository includes a safe rehearsal script:

```bash
./scripts/rehearse_oss_history_rewrite.sh /tmp/rtbcat-oss-origin-clean.git git@github.com:jenbrannstrom/rtbcat-platform.git
```

It will:

1. create a fresh mirror clone
2. run `git filter-repo`
3. run `gitleaks`
4. print the remaining findings

## Gmail OAuth Rotation

Rotate the Google Desktop OAuth client used for Gmail import.

Recommended sequence:

1. In Google Cloud Console, create a new Desktop OAuth client for the Gmail importer.
2. Download the new client JSON.
3. Replace the GCP Secret Manager payload:

```bash
gcloud secrets versions add catscan-gmail-oauth-client \
  --project=catscan-prod-202601 \
  --data-file=/path/to/new-gmail-oauth-client.json
```

4. Re-auth the Gmail importer if needed, because client rotation may invalidate the old token:
   - refresh or recreate `gmail-token.json`
5. Verify the importer still works.

Suggested validation:

```bash
gcloud secrets versions list catscan-gmail-oauth-client \
  --project=catscan-prod-202601 \
  --sort-by=~createTime
```

## Canonical Rewrite Sequence

Do **not** run the destructive rewrite in a dirty working tree.

Use a fresh mirror:

```bash
rm -rf /tmp/rtbcat-oss-origin-clean.git
git clone --mirror git@github.com:jenbrannstrom/rtbcat-platform.git /tmp/rtbcat-oss-origin-clean.git
cd /tmp/rtbcat-oss-origin-clean.git
```

Run the rewrite using the rehearsal script from the main repo:

```bash
/home/x1-7/Documents/rtbcat-platform/scripts/rehearse_oss_history_rewrite.sh \
  /tmp/rtbcat-oss-origin-clean.git \
  git@github.com:jenbrannstrom/rtbcat-platform.git
```

Note: after rewrite, fingerprint-based `gitleaks` findings will change because commit hashes change.

## Expected Rewrite Result

Expected remaining findings after rewrite:

- none

Rerun:

```bash
gitleaks detect --source=. --no-banner
```

## Force-Push Sequence

Only do this after:

1. Gmail OAuth client has been rotated
2. rewritten mirror is verified clean enough for release
3. collaborators are warned to stop pushing

Recommended sequence:

```bash
cd /tmp/rtbcat-oss-origin-clean.git
git remote -v
git -c remote.origin.mirror=false push --force origin 'refs/heads/*:refs/heads/*'
git -c remote.origin.mirror=false push --force origin 'refs/tags/*:refs/tags/*'
```

Note: avoid `git push --mirror` against GitHub here because the fresh mirror also contains `refs/pull/*`, which GitHub treats as hidden refs and rejects on push.

Validated on 2026-03-06 with `--dry-run`: the branch/tag refspec form works against GitHub.

## Collaboration Warning

This rewrite will change commit IDs across all rewritten refs.

Before the force-push:

1. freeze merges/pushes to the repo
2. notify anyone with local clones or worktrees
3. tell collaborators they must re-clone or hard-reset to the rewritten refs
4. plan to open a GitHub Support ticket to purge cached PR diffs / hidden refs if any leaked blobs remain visible via old pull request views

Suggested notice:

```text
Repository history is being rewritten to remove internal deployment artifacts and leaked credentials before OSS release.
Do not push until the rewrite is complete.
After the force-push, re-clone the repo or hard-reset your local branches to the new origin refs.
```

## Post-Push Verification

After force-push:

1. clone a fresh working copy from GitHub
2. rerun `gitleaks`
3. rerun `./scripts/oss_release_preflight.sh --quick`
4. rerun the full dependency audits

## Residual Manual Review

`gitleaks` did not flag every sensitive string. Historical AI logs also contained a plaintext password-like value, which is one reason `docs/ai_logs/` should be removed as a class rather than allowlisted line by line.
