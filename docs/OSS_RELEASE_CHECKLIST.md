# OSS Release Checklist

Every public release must pass **all** gates below. Do not skip any.

---

## Automated Gates (CI + local preflight)

Run locally before pushing:

```bash
./scripts/oss_release_preflight.sh
```

| Gate | Tool | Blocks release? |
|------|------|:---------------:|
| No secrets in repo history | `gitleaks detect` | Yes |
| No forbidden tracked files | git ls-files pattern scan | Yes |
| Python deps free of known CVEs | `pip-audit -r requirements.txt` | Yes |
| Node deps free of high/critical CVEs | `npm audit --audit-level=high` | Yes |
| `SECURITY.md` present at root | file check | Yes |
| `LICENSE` present at root | file check | Yes |
| `.gitignore` covers `.env`, `*.db`, `*.tfstate`, `terraform.tfvars` | pattern check | Yes |

CI equivalent: `.github/workflows/oss-release-preflight.yml` (runs on PRs and manual dispatch).

---

## Runtime Configuration Gates

These must be set in the production `.env` / environment **before** the release
is tagged. Verify with the runtime health endpoint (`/api/system/health`).

### 1. Disable public OpenAPI docs

```
DISABLE_OPENAPI_DOCS=true
```

Ensures `/docs` and `/redoc` are not exposed on the public API. The
application strips these routes at startup when this variable is set.

### 2. Strict secrets health

```
SECRETS_HEALTH_STRICT=true
```

Forces the `/api/system/secrets-health` endpoint to return a non-200 status
if any required secret is missing or invalid. Prevents deploying with
placeholder credentials.

### 3. Runtime health strict pass

```
RUNTIME_HEALTH_STRICT=true
```

Makes the startup health-check fail hard if any critical subsystem
(database, Cloud SQL Proxy, secrets) is unreachable. Prevents a
"looks-green-but-broken" deploy.

Verify all three:

```bash
curl -sf https://YOUR_DOMAIN/api/system/health | jq .
# configured: true, database_exists: true, status: "healthy"
```

### 4. Runtime strict latency budget (time-boxed waiver policy)

Baseline policy:

```
CATSCAN_RUNTIME_HEALTH_MAX_HOME_ENDPOINT_EFFICIENCY_LATENCY_MS=12000
```

If a temporary override is used for historical-rollup aging, it must include:

- explicit expiry date in `ROADMAP.md`
- reason + run evidence link
- rollback action/date to restore `12000` and rerun strict with `--since-hours 168`
- workflow expiry guard via `CATSCAN_RUNTIME_HEALTH_ENDPOINT_EFFICIENCY_BUDGET_WAIVER_EXPIRES_ON`

---

## Manual Review Gates

Before tagging a release, a maintainer must confirm:

- [ ] `git log --oneline --all -- '*.env' '*.tfstate' '*credentials*'` returns empty.
- [ ] No hardcoded IPs, project IDs, or real domains outside `docs/` examples.
- [ ] `docs/SECURITY.md` deployment guidance is up to date.
- [ ] CHANGELOG.md covers all user-facing changes since last release.
- [ ] The preflight workflow is green on the release branch.

---

## Release Tag Sequence

```bash
# 1. Ensure preflight passes
./scripts/oss_release_preflight.sh

# 2. Bump VERSION file
echo "1.0.0" > VERSION

# 3. Commit and tag
git add VERSION CHANGELOG.md
git commit -m "release: v1.0.0"
git tag -a v1.0.0 -m "v1.0.0"

# 4. Push (tag triggers build-and-push workflow)
git push origin unified-platform --tags
```
