# VM2 Post-Deploy Verification (2026-02-13)

Use this to verify the deployed fixes after cherry-picking security/stability commits.

## Run

```bash
cat >/tmp/verify_rtbcat_postdeploy.sh <<'BASH'
#!/usr/bin/env bash
set -u
set -o pipefail

APP_DIR="${APP_DIR:-/opt/catscan}"
API_URL="${API_URL:-http://127.0.0.1:8000}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.gcp.yml}"
DO_RESTART="${DO_RESTART:-1}"

PASS=0
FAIL=0
WARN=0
SKIP=0

ok()   { echo "[PASS] $*"; PASS=$((PASS+1)); }
bad()  { echo "[FAIL] $*"; FAIL=$((FAIL+1)); }
warn() { echo "[WARN] $*"; WARN=$((WARN+1)); }
skip() { echo "[SKIP] $*"; SKIP=$((SKIP+1)); }

if ! cd "$APP_DIR" 2>/dev/null; then
  echo "Cannot cd to $APP_DIR"
  exit 2
fi

if [[ ! -f "$COMPOSE_FILE" ]]; then
  if [[ -f docker-compose.production.yml ]]; then
    COMPOSE_FILE="docker-compose.production.yml"
  else
    echo "No compose file found."
    exit 2
  fi
fi

DOCKER=(docker)
if ! docker info >/dev/null 2>&1; then
  DOCKER=(sudo docker)
fi

dc() { "${DOCKER[@]}" compose -f "$COMPOSE_FILE" "$@"; }
dexec() { "${DOCKER[@]}" exec "$@"; }

read_env() {
  local key="$1"
  local val
  val="$(awk -F= -v k="$key" '$1==k{sub(/^[^=]*=/,""); print; exit}' .env 2>/dev/null || true)"
  val="${val%\"}"; val="${val#\"}"
  printf "%s" "$val"
}

echo "=== Step 1: apply/restart for UVICORN_WORKERS=2 ==="

if [[ -f .env ]]; then
  if grep -q '^UVICORN_WORKERS=' .env; then
    sed -i 's/^UVICORN_WORKERS=.*/UVICORN_WORKERS=2/' .env
  else
    printf '\nUVICORN_WORKERS=2\n' >> .env
  fi
  ok ".env has UVICORN_WORKERS=2"
else
  warn ".env not found in $APP_DIR (skipping local env edit)"
fi

if [[ "$DO_RESTART" == "1" ]]; then
  if dc up -d api dashboard >/dev/null 2>&1; then
    ok "docker compose up -d api dashboard"
  else
    bad "docker compose restart failed"
  fi
else
  warn "DO_RESTART=0, skipping restart"
fi

for _ in $(seq 1 60); do
  code="$(curl -s -o /tmp/rtbcat_health.json -w '%{http_code}' "$API_URL/health" || true)"
  [[ "$code" == "200" ]] && break
  sleep 2
done

if [[ "${code:-000}" == "200" ]]; then
  ver="$(python3 - <<'PY'
import json
try:
    d=json.load(open("/tmp/rtbcat_health.json"))
    print(d.get("version","unknown"))
except Exception:
    print("unknown")
PY
)"
  ok "/health = 200 (version=$ver)"
else
  bad "/health failed (status=${code:-000})"
fi

worker_env="$(dexec catscan-api sh -lc 'printf "%s" "${UVICORN_WORKERS:-}"' 2>/dev/null || true)"
if [[ "$worker_env" == "2" ]]; then
  ok "catscan-api env UVICORN_WORKERS=2"
else
  warn "catscan-api env UVICORN_WORKERS='$worker_env' (expected 2)"
fi

if dexec catscan-api sh -lc "ps -ef | grep -qE '[u]vicorn .*--workers[[:space:]]+2'" 2>/dev/null; then
  ok "uvicorn launched with --workers 2"
else
  warn "could not confirm '--workers 2' from process list"
fi

echo
echo "=== Step 2: migration marker audit ==="
if dexec catscan-api python scripts/postgres_migrate.py --audit-versions; then
  ok "schema_migrations marker audit clean"
else
  bad "schema_migrations marker audit reported anomalies"
fi

echo
echo "=== Step 3: smoke checks (/settings/endpoints, /sizes, login messages) ==="

AUTH_ARGS=()
API_KEY="$(read_env CATSCAN_API_KEY)"
if [[ -n "$API_KEY" ]]; then
  AUTH_ARGS=(-H "Authorization: Bearer $API_KEY")
  ok "Using CATSCAN_API_KEY auth"
else
  OAUTH2_ENABLED="$(read_env OAUTH2_PROXY_ENABLED | tr '[:upper:]' '[:lower:]')"
  if [[ "$OAUTH2_ENABLED" == "true" ]]; then
    SMOKE_EMAIL="$(dexec catscan-api python - <<'PY' 2>/dev/null || true
import asyncio
from services.auth_service import AuthService
async def main():
    users = await AuthService().get_users(active_only=True)
    print(users[0].email if users else "")
asyncio.run(main())
PY
)"
    if [[ -n "$SMOKE_EMAIL" ]]; then
      AUTH_ARGS=(-H "X-Email: $SMOKE_EMAIL" -H "X-User: $SMOKE_EMAIL")
      ok "Using trusted proxy header auth with existing user"
    else
      warn "No active user found for trusted proxy header auth"
    fi
  else
    warn "No CATSCAN_API_KEY and OAUTH2 proxy disabled"
  fi
fi

# /settings/endpoints
code="$(curl -sS "${AUTH_ARGS[@]}" -o /tmp/rtbcat_endpoints.json -w '%{http_code}' "$API_URL/settings/endpoints" || true)"
if [[ "$code" == "200" ]]; then
  if python3 - <<'PY'
import json,sys
d=json.load(open("/tmp/rtbcat_endpoints.json"))
v=d.get("qps_current")
if v is None:
    print("qps_current=null (no live metric)")
    sys.exit(0)
if isinstance(v, (int,float)) and not isinstance(v,bool):
    print(f"qps_current={float(v)} ({type(v).__name__})")
    sys.exit(0)
print(f"Invalid qps_current type: {type(v).__name__}")
sys.exit(1)
PY
  then
    ok "/settings/endpoints returned valid qps_current type"
  else
    bad "/settings/endpoints qps_current type check failed"
  fi
elif [[ "$code" == "401" || "$code" == "403" ]]; then
  skip "/settings/endpoints auth blocked (status $code)"
else
  bad "/settings/endpoints failed (status $code)"
fi

# /sizes
code="$(curl -sS "${AUTH_ARGS[@]}" -o /tmp/rtbcat_sizes.json -w '%{http_code}' "$API_URL/sizes" || true)"
if [[ "$code" == "200" ]]; then
  if python3 - <<'PY'
import json,sys
d=json.load(open("/tmp/rtbcat_sizes.json"))
sizes=d.get("sizes")
if not isinstance(sizes,list):
    print("sizes is not a list")
    sys.exit(1)
bad=[x for x in sizes if not isinstance(x,str)]
if bad:
    print(f"non-string entries: {len(bad)}")
    sys.exit(1)
print(f"sizes_count={len(sizes)} all strings")
sys.exit(0)
PY
  then
    ok "/sizes returned list[str]"
  else
    bad "/sizes type check failed"
  fi
elif [[ "$code" == "401" || "$code" == "403" ]]; then
  skip "/sizes auth blocked (status $code)"
else
  bad "/sizes failed (status $code)"
fi

# Login error messages in compiled dashboard bundle
MSG1="Server unavailable. Please try again in a moment."
MSG2="Login service is temporarily unavailable."
MSG3="Cannot reach server. Please check your connection and try again."

for msg in "$MSG1" "$MSG2" "$MSG3"; do
  if dexec catscan-dashboard sh -lc "grep -R --text -qF $(printf '%q' "$msg") /app/.next" 2>/dev/null; then
    ok "dashboard bundle contains: $msg"
  else
    bad "dashboard bundle missing: $msg"
  fi
done

echo
echo "=== Step 4: recurrence snapshot ==="

if [[ -r /var/log/nginx/access.log ]]; then
  c504="$(tail -n 5000 /var/log/nginx/access.log | awk '$9==504{c++} END{print c+0}')"
  if [[ "$c504" == "0" ]]; then
    ok "nginx access log tail: 0 recent 504s (last 5000 lines)"
  else
    warn "nginx access log tail: $c504 recent 504s (last 5000 lines)"
  fi
else
  warn "Cannot read /var/log/nginx/access.log (skipped 504 check)"
fi

restart_count="$("${DOCKER[@]}" inspect -f '{{.RestartCount}}' catscan-api 2>/dev/null || echo unknown)"
if [[ "$restart_count" == "0" ]]; then
  ok "catscan-api restart count = 0"
else
  warn "catscan-api restart count = $restart_count"
fi

echo
echo "=== Summary ==="
echo "PASS=$PASS  FAIL=$FAIL  WARN=$WARN  SKIP=$SKIP"

if [[ "$FAIL" -gt 0 ]]; then
  exit 1
fi
exit 0
BASH

chmod +x /tmp/verify_rtbcat_postdeploy.sh
/tmp/verify_rtbcat_postdeploy.sh
```

## Check-only mode (no restart)

```bash
DO_RESTART=0 /tmp/verify_rtbcat_postdeploy.sh
```
