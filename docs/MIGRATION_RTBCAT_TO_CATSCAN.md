# Migration Plan: Standardize Naming from `rtbcat` to `catscan`

**Status:** Planned
**Priority:** Pre-OSS release
**Breaking Change:** Yes (path changes affect existing deployments)

---

## Problem Statement

The codebase has inconsistent naming between `rtbcat` (company name) and `catscan` (app name):

| Location | Current User | Current Path |
|----------|--------------|--------------|
| VM (host) | `catscan` | `/home/catscan/.catscan/` |
| Docker container | `rtbcat` | `/home/rtbcat/.catscan/` |

This causes:
1. **Human error** - Easy to misread paths when debugging or writing scripts
2. **Cognitive overhead** - Developers must remember which context uses which name
3. **OSS confusion** - External contributors will see "rtbcat" and wonder what it means
4. **Documentation burden** - Must explain the mapping in docs

### Example of Current Confusion

```yaml
# docker-compose.production.yml
volumes:
  - ${DATA_DIR:-/home/catscan/.catscan}:/home/rtbcat/.catscan
#                      ↑                        ↑
#                 host (catscan)         container (rtbcat)
```

---

## Target State

Standardize on `catscan` everywhere:

| Location | Target User | Target Path |
|----------|-------------|-------------|
| VM (host) | `catscan` | `/home/catscan/.catscan/` |
| Docker container | `catscan` | `/home/catscan/.catscan/` |

After migration:
```yaml
# docker-compose.production.yml
volumes:
  - ${DATA_DIR:-/home/catscan/.catscan}:/home/catscan/.catscan
```

---

## Files Requiring Changes

### Docker (Core Changes)

| File | Changes Required |
|------|------------------|
| `Dockerfile` | Change user `rtbcat` → `catscan`, update all paths |
| `docker-compose.gcp.yml` | Update container paths |
| `docker-compose.production.yml` | Update container paths |
| `docker-compose.simple.yml` | Update container paths |

### Terraform

| File | Changes Required |
|------|------------------|
| `terraform/user_data.sh` | Update container mount paths |
| `terraform/gcp/startup.sh` | Already uses `catscan` - verify consistency |

### Scripts

| File | Changes Required |
|------|------------------|
| `scripts/fix_credentials.sh` | Update path references |
| `scripts/restore_backup.sh` | Verify path defaults |
| `scripts/migrate_sqlite_to_postgres.py` | Update default paths |

### Documentation

| File | Changes Required |
|------|------------------|
| `docs/GCP_CREDENTIALS_SETUP.md` | Update all path references |
| `DATA_MODEL.md` | Update container path references |
| `INSTALL.md` | Update path references |
| `prompts/deploy-catscan.example.md` | Update path references |

---

## Migration Steps

### Phase 1: Update Dockerfile

```dockerfile
# Before
ARG USERNAME=rtbcat
RUN mkdir -p /home/rtbcat/.catscan && chown rtbcat:rtbcat /home/rtbcat/.catscan
ENV DATABASE_PATH=/home/rtbcat/.catscan/catscan.db
USER rtbcat

# After
ARG USERNAME=catscan
RUN mkdir -p /home/catscan/.catscan && chown catscan:catscan /home/catscan/.catscan
ENV DATABASE_PATH=/home/catscan/.catscan/catscan.db
USER catscan
```

### Phase 2: Update Docker Compose Files

```yaml
# Before
volumes:
  - "${DATA_DIR:-~/.catscan}:/home/rtbcat/.catscan"
environment:
  - GOOGLE_APPLICATION_CREDENTIALS=/home/rtbcat/.catscan/credentials/google-credentials.json

# After
volumes:
  - "${DATA_DIR:-~/.catscan}:/home/catscan/.catscan"
environment:
  - GOOGLE_APPLICATION_CREDENTIALS=/home/catscan/.catscan/credentials/google-credentials.json
```

### Phase 3: Update Terraform

```bash
# Before (terraform/user_data.sh)
- /home/catscan/.catscan:/home/rtbcat/.catscan

# After
- /home/catscan/.catscan:/home/catscan/.catscan
```

### Phase 4: Update Documentation

Search and replace in all docs:
- `/home/rtbcat/` → `/home/catscan/`
- `user rtbcat` → `user catscan`

### Phase 5: Update Scripts

Review and update path defaults in:
- `scripts/fix_credentials.sh`
- `scripts/restore_backup.sh`
- `scripts/migrate_sqlite_to_postgres.py`

---

## Deployment Procedure

### For Existing Deployments

Existing VMs will continue to work because:
- The host path `/home/catscan/.catscan/` is unchanged
- Only the container-internal path changes

Deploy new container image:

```bash
# 1. Pull new images (after CI builds them)
cd /opt/catscan
sudo docker-compose -f docker-compose.gcp.yml pull

# 2. Restart containers
sudo docker-compose -f docker-compose.gcp.yml up -d

# 3. Verify
sudo docker exec catscan-api whoami
# Expected: catscan (was: rtbcat)
```

### For New Deployments

No special steps required.

---

## Rollback Plan

If issues occur:

1. Revert the Dockerfile and docker-compose changes in git
2. Rebuild images via CI
3. Redeploy: `docker-compose pull && docker-compose up -d`

The host filesystem is unchanged, so data is safe.

---

## Testing Checklist

- [ ] Build new Docker image locally
- [ ] Verify container user is `catscan`: `docker exec catscan-api whoami`
- [ ] Verify credentials path works
- [ ] Verify API starts: `curl http://localhost:8000/health`
- [ ] Verify BigQuery access works
- [ ] Test on staging VM before production

---

## Related Cleanup (Optional)

While standardizing naming, consider also:

1. **Repository name** - Currently `rtbcat-platform`, could become `catscan` for OSS
2. **Package names** - Check if any Python packages reference `rtbcat`
3. **Environment variables** - Standardize any that mention `rtbcat`
