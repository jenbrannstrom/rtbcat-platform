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
| Python dependency bundles free of known CVEs | `pip-audit` on `requirements.txt`, `requirements-ai.txt`, `requirements-dev.txt`, `requirements-mcp.txt` | Yes |
| Node deps have no reported vulnerabilities | `cd dashboard && npm run audit:release` | Yes |
| `SECURITY.md` present at root | file check | Yes |
| `LICENSE` present at root | file check | Yes |
| `.gitignore` covers `.env`, `*.db`, `*.tfstate`, `terraform.tfvars` | pattern check | Yes |
| `VERSION` is valid SemVer (`X.Y.Z`) | regex check | Yes |
| `pyproject.toml` version matches `VERSION` | metadata check | Yes |

CI equivalent: `.github/workflows/oss-release-preflight.yml` (runs on PRs and manual dispatch).
Run `npm ci` in `dashboard/` before the local preflight. The release gate runs
contract tests and standard `npm audit` for the complete dependency tree.
There are no dependency exceptions. Any finding or audit service error blocks
release. See [Dependency security](DEPENDENCY_MITIGATIONS.md).

The PR secret-scanner action checks the PR's commit range. Before tagging, also
run the local full-history scan and manually dispatch preflight on the exact
release ref. A green PR secret check does not clear historical findings.

---

## Runtime Configuration Gates

For a release represented as deployed, verify the exact deployed image digests,
health, auth boundary and an authenticated MCP call. Publishing source alone does
not replace the production containers. Record deployed and source SHAs separately.

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

Makes application startup fail when required secrets are missing. Keep it enabled
and run the host verifier; setting the flag does not validate every upstream permission.

### 3. Runtime verification

Run the maintained host verifier with the manifest, correct host posture and MCP
setting. `SECRETS_HEALTH_STRICT` is an application startup check;
`RUNTIME_HEALTH_STRICT` is not a substitute for the actual verifier.

```bash
sudo scripts/hetzner/verify_app_release.sh \
  --release-file /path/hetzner-release.env \
  --mode production --mcp-enabled true --with-google
```

Check `/health` for a healthy database and the expected `git_sha`, `/login` for
access, protected routes for rejection without authentication, and MCP tool calls
for both permitted and denied buyer access. Public MCP `/health` alone proves
availability, not authorization or data freshness.

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

- [ ] Review history matches for secret-bearing files, including deleted ones.
  Scripts with `credentials` in their name are not credentials by themselves.
  Every scanner finding has a documented disposition: verified non-secret, or
  revoked/rotated credential with coordinated history cleanup. Unresolved real
  credentials block publication; adding an ignore entry is not remediation.
- [ ] No private infrastructure/customer identifiers or secrets in the release
  diff. Documented public product endpoints and example/private-network defaults
  are permitted; private operational details belong outside tracked files.
- [ ] `docs/SECURITY.md` deployment guidance is up to date.
- [ ] `VERSION` value matches intended release tag (`v$(cat VERSION)`).
- [ ] CHANGELOG.md covers all user-facing changes since last release.
- [ ] The preflight and required security/regression workflows are green on the
  exact release commit. Evidence from an older commit is not sufficient.
- [ ] Grok instructions include secure token entry, seat scope, expiry, revocation,
  cloud-computer sharing and an authenticated tool-call acceptance check.
- [ ] Source publication, image build and production deployment are reported separately.

---

## Release sequence

Follow [VERSIONING.md](VERSIONING.md). Complete checks, update both version files
and the changelog, review/merge, then create the matching annotated tag and GitHub
Release. Sync the same approved refs to Gitee only with working authentication.
The image build and production deployment are separate manual actions; a tag
push does not trigger either.
