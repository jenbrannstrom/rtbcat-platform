# OSS Audit Report — 2026-03-12

## Security Audit: No Leaked Secrets (Clean)

No hardcoded credentials, API keys, or sensitive files were found in the repo. The `.gitignore` is comprehensive, Docker containers run as non-root, CORS is properly scoped, and auth is well-implemented.

### SQL Injection Vulnerabilities to Fix

| Severity | Issue | Location |
|----------|-------|----------|
| **CRITICAL** | Dynamic table/column names in `ALTER TABLE` | `importers/unified_importer.py:229` |
| **HIGH** | f-string INTERVAL interpolation | `analytics/geo_waste_analyzer.py:113,122,127` |
| **HIGH** | f-string INTERVAL interpolation | `analytics/pretargeting_recommender.py:97,106,131,134` |
| **HIGH** | f-string INTERVAL interpolation | `storage/postgres_store.py:1748,2056` |

These use `f"INTERVAL '{days} days'"` instead of parameterized queries. While `days` is likely always an int internally, it's bad practice and dangerous in an OSS repo where others will fork/modify.

**Fix pattern:**
```python
# Instead of:
f"INTERVAL '{days} days'"

# Use parameterized:
"INTERVAL %s", (f"{days} days",)
```

For the `ALTER TABLE` in `unified_importer.py`, validate/whitelist column names or use `psycopg2.sql.Identifier()`.

### What Passed Security Review

- ✅ No hardcoded secrets, API keys, or passwords
- ✅ `.env.example` contains only placeholders
- ✅ `.gitignore` covers `.env`, `*.tfstate`, credentials, `*.db`
- ✅ API key auth uses `secrets.compare_digest()` (timing-safe)
- ✅ Password hashing uses bcrypt with SHA-256 prehashing
- ✅ Docker containers run as non-root users
- ✅ CORS configured with explicit origins (no wildcards with credentials)
- ✅ Bootstrap endpoint has IP-based rate limiting
- ✅ GCP startup script fetches secrets from Secret Manager at runtime
- ✅ OAuth2 config files have `chmod 600`

---

## Deployment Readiness: 8/10

### What's Strong

- **README.md** (242 lines): Clear project overview with quick start
- **INSTALL.md** (1,141 lines): Outstanding — covers system requirements, quick start, Gmail OAuth setup, production Nginx, VM provisioning, troubleshooting
- **.env.example** (186 lines): Every variable documented with sections and defaults
- **setup.sh / run.sh**: Clean automation for local dev
- **Makefile**: Extensive test/validation targets
- **Docker**: Multi-stage builds, non-root, health checks, 3 compose variants (simple/production/GCP)
- **Migrations**: 60+ numbered SQL files with a sophisticated migration runner (dry-run, rollback, version auditing)
- **CI/CD**: 15+ GitHub Actions workflows including OSS-specific preflight
- **Community**: LICENSE (MIT), CONTRIBUTING.md, CODE_OF_CONDUCT.md, CHANGELOG.md, PR template

### High Priority Gaps

1. **No local dev Docker Compose with Postgres** — biggest friction point for new contributors. A `docker-compose.local.yml` that bundles Postgres + API + Dashboard with seed data would cut setup time in half. Currently requires external Postgres.

2. **No GitHub issue templates** — missing `.github/ISSUE_TEMPLATE/` (bug report, feature request)

3. **No secret generation commands in INSTALL.md** — should include:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   # or
   openssl rand -hex 32
   ```

4. **Auth login loop not in public docs** — this is a known recurring issue (DB failure → `/auth/check` returns false → redirect loop) with a 3-layer fix already implemented, but it's only documented internally, not in troubleshooting docs.

### Medium Priority Gaps

5. **No backup/recovery guide** — no `pg_dump` examples, no restore procedures, no retention policy
6. **No upgrade guide** — no "how to upgrade from v0.9.3 to v0.9.4", no breaking change warnings, no rollback procedures
7. **No first-deployment checklist** — a simple checklist confirming Python, Node, Postgres, .env, migrations, health check, dashboard, admin user, test upload
8. **Incomplete troubleshooting** — covers basics but missing API 503s, dashboard load failures, DB connection pool exhaustion

### Lower Priority Gaps

9. **No monitoring/observability guide** — health check endpoints, metrics, log aggregation, alert thresholds
10. **No performance tuning guide** — batch size tuning, Postgres optimization, caching strategy
11. **No multi-platform deployment docs** — GCP is well-covered, but no AWS/Azure/k8s guidance

---

## Recommended Next Steps

### Immediate (security)
- [x] Fix SQL injection in `importers/unified_importer.py:229` (6439e283)
- [x] Fix INTERVAL interpolation in `analytics/geo_waste_analyzer.py` (6439e283)
- [x] Fix INTERVAL interpolation in `analytics/pretargeting_recommender.py` (6439e283)
- [x] Fix INTERVAL interpolation in `storage/postgres_store.py` (6439e283)

### Short-term (deployment friction)
- [x] Create `docker-compose.local.yml` with bundled Postgres + seed data
- [ ] Add `.github/ISSUE_TEMPLATE/` (bug report, feature request)
- [ ] Add secret generation commands to INSTALL.md
- [ ] Document auth login loop diagnosis in troubleshooting section

### Medium-term (operational confidence)
- [ ] Create `docs/BACKUP_RECOVERY.md`
- [ ] Create `docs/UPGRADING.md`
- [ ] Create `docs/FIRST_DEPLOYMENT_CHECKLIST.md`
- [ ] Expand troubleshooting coverage
