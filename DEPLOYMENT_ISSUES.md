# Deployment Issues - 2025-12-29

Issues encountered during fresh server deployment to `52.58.210.20`.

## Critical Issues (Fixed on server, need sync to repo)

### 1. Wrong API build context in docker-compose.production.yml
- **File:** `docker-compose.production.yml`
- **Problem:** Build context was `./creative-intelligence` but Dockerfile is in root
- **Error:** `failed to read dockerfile: open Dockerfile: no such file or directory`
- **Fix:** Change `context: ./creative-intelligence` to `context: .`
- **Status:** Fixed on server only, needs commit

### 2. Obsolete docker-compose version attribute
- **File:** `docker-compose.production.yml`
- **Problem:** `version: '3.8'` is obsolete in modern Docker Compose
- **Warning:** `the attribute 'version' is obsolete, it will be ignored`
- **Fix:** Remove the `version: '3.8'` line entirely
- **Status:** Needs fix

---

## Medium Issues

### 3. Health check fails - curl not in container
- **File:** `Dockerfile`
- **Problem:** Health check uses `curl` but it's not installed in slim Python image
- **Error:** `exec: "curl": executable file not found in $PATH`
- **Current healthcheck:**
  ```dockerfile
  HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
      CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1
  ```
- **Note:** The Python healthcheck should work but seems to fail. Container shows "unhealthy" but API works.
- **Fix options:**
  1. Add `curl` to runtime image: `RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*`
  2. Or use wget: `CMD wget -q --spider http://localhost:8000/health || exit 1`
- **Status:** Needs fix

### 4. FastAPI deprecation warning
- **File:** `api/routers/analytics/rtb_funnel.py:413`
- **Problem:** Using deprecated `regex` parameter
- **Warning:** `FastAPIDeprecationWarning: 'regex' has been deprecated, please use 'pattern' instead`
- **Current code:** `by: str = Query("size", regex="^(size|geo|publisher|creative)$")`
- **Fix:** Change `regex=` to `pattern=`
- **Status:** Needs fix

---

## Low Priority

### 5. ECS agent container exits
- **Problem:** Amazon ECS agent container starts and immediately exits
- **Note:** This is expected - ECS agent is not needed for standalone EC2 deployment
- **Status:** Can be ignored or removed from AMI

---

## Fixes Applied

| Fix | Location | Date |
|-----|----------|------|
| API build context | Server only | 2025-12-29 |
| New auth credentials | Server + local | 2025-12-29 |
| Deploy key via Secrets Manager | Terraform + AWS | 2025-12-29 |

---

## Fixes Applied to Repository

All fixes have been applied locally. Ready to commit:

```bash
git add -A
git commit -m "Fix deployment issues: docker-compose context, healthcheck, deprecation"
git push origin unified-platform
```

### Changes Made:
1. `docker-compose.production.yml` - Removed obsolete `version` line
2. `docker-compose.production.yml` - Fixed API build context from `./creative-intelligence` to `.`
3. `docker-compose.production.yml` - Changed healthcheck from `curl` to `python urllib`
4. `api/routers/analytics/rtb_funnel.py` - Changed `regex=` to `pattern=`
5. `login.html` - Updated auth hash for new credentials
6. `terraform/terraform.tfvars` - Updated auth cookie hash
