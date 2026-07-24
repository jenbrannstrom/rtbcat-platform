#!/usr/bin/env bash
# Install Part 3 runtime configuration without putting values in git, Terraform,
# shell arguments, or Docker image layers.

set -euo pipefail

RUNTIME_ENV_SOURCE=""
POSTGRES_PASSWORD_SOURCE=""
POSTGRES_CA_SOURCE=""
GOOGLE_CREDENTIALS_SOURCE=""
ALLOW_SERVICE_ACCOUNT_KEY="false"
MARKER_FILE="/etc/rtbcat/app-host.env"
SECRET_DIR="/etc/rtbcat/secrets"
CONTAINER_UID=10001
CONTAINER_GID=10001

usage() {
  cat <<'EOF'
Usage: sudo scripts/hetzner/install_app_secrets.sh [options]

Required:
  --runtime-env <path>           Completed non-secret runtime env file.
  --postgres-password <path>     One-line database password file.
  --postgres-ca <path>           PostgreSQL server/root certificate.
  --google-credentials <path>    ADC JSON (prefer external_account WIF).

Optional:
  --allow-service-account-key    Explicitly permit a service_account key JSON.
  --help

Source secret files must not be group/world accessible. Values are copied to
/etc/rtbcat and are never printed.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --runtime-env) RUNTIME_ENV_SOURCE="${2:?missing path}"; shift 2 ;;
    --postgres-password) POSTGRES_PASSWORD_SOURCE="${2:?missing path}"; shift 2 ;;
    --postgres-ca) POSTGRES_CA_SOURCE="${2:?missing path}"; shift 2 ;;
    --google-credentials) GOOGLE_CREDENTIALS_SOURCE="${2:?missing path}"; shift 2 ;;
    --allow-service-account-key) ALLOW_SERVICE_ACCOUNT_KEY="true"; shift ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ ${EUID} -ne 0 ]]; then
  echo "Run this script as root on the marked Hetzner app host." >&2
  exit 1
fi
if [[ ! -f "$MARKER_FILE" ]]; then
  echo "Hetzner app-host marker is absent." >&2
  exit 1
fi

for source_path in \
  "$RUNTIME_ENV_SOURCE" \
  "$POSTGRES_PASSWORD_SOURCE" \
  "$POSTGRES_CA_SOURCE" \
  "$GOOGLE_CREDENTIALS_SOURCE"; do
  if [[ -z "$source_path" || ! -f "$source_path" || -L "$source_path" ]]; then
    echo "Every input must be a regular non-symlink file." >&2
    exit 1
  fi
done

for secret_source in "$POSTGRES_PASSWORD_SOURCE" "$GOOGLE_CREDENTIALS_SOURCE"; do
  source_mode="$(stat -c '%a' "$secret_source")"
  if [[ "$source_mode" != "400" && "$source_mode" != "600" ]]; then
    echo "Input secret files must have mode 0400 or 0600." >&2
    exit 1
  fi
done

python3 - "$POSTGRES_PASSWORD_SOURCE" <<'PY'
from pathlib import Path
import sys

raw = Path(sys.argv[1]).read_bytes()
if raw.endswith(b"\r\n"):
    raw = raw[:-2]
elif raw.endswith(b"\n"):
    raw = raw[:-1]
if b"\r" in raw or b"\n" in raw or len(raw.decode("utf-8")) < 24:
    raise SystemExit("Database password must be one UTF-8 line of at least 24 characters.")
PY

openssl x509 -in "$POSTGRES_CA_SOURCE" -noout >/dev/null
adc_type="$(jq -er '.type' "$GOOGLE_CREDENTIALS_SOURCE")"
case "$adc_type" in
  external_account)
    if ! jq -e '
      (.audience | type == "string" and length > 0) and
      (.subject_token_type | type == "string" and length > 0) and
      (.token_url | type == "string" and length > 0) and
      (.credential_source | type == "object")
    ' "$GOOGLE_CREDENTIALS_SOURCE" >/dev/null; then
      echo "external_account ADC JSON is incomplete." >&2
      exit 1
    fi
    ;;
  service_account)
    if [[ "$ALLOW_SERVICE_ACCOUNT_KEY" != "true" ]]; then
      echo "A service-account key requires --allow-service-account-key; prefer WIF." >&2
      exit 1
    fi
    if ! jq -e '
      (.client_email | type == "string" and length > 0) and
      (.private_key | type == "string" and length > 0) and
      (.token_uri | type == "string" and length > 0)
    ' "$GOOGLE_CREDENTIALS_SOURCE" >/dev/null; then
      echo "service_account ADC JSON is incomplete." >&2
      exit 1
    fi
    ;;
  *)
    echo "ADC JSON must be external_account or service_account, found ${adc_type}." >&2
    exit 1
    ;;
esac

if grep -nE '^.*=replace-' "$RUNTIME_ENV_SOURCE" >/dev/null; then
  echo "Runtime env still contains replace-* placeholders." >&2
  exit 1
fi
python3 - "$RUNTIME_ENV_SOURCE" <<'PY'
from pathlib import Path
import sys

allowed_sensitive_names = {
    "CATSCAN_REQUIRE_BOOTSTRAP_TOKEN",
    "CATSCAN_REQUIRE_OAUTH_CLIENT_SECRET_IN_API",
}
for raw_line in Path(sys.argv[1]).read_text().splitlines():
    line = raw_line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    key = key.strip()
    if not value or key in allowed_sensitive_names:
        continue
    if key in {"POSTGRES_DSN", "POSTGRES_SERVING_DSN", "DATABASE_URL", "GOOGLE_APPLICATION_CREDENTIALS"} or key.endswith(
        ("_SECRET", "_PASSWORD", "_TOKEN", "_API_KEY", "_CREDENTIALS")
    ):
        raise SystemExit(f"Secret-like value is forbidden in runtime env: {key}")
PY
for scheduler_flag in \
  CATSCAN_ENABLE_GMAIL_IMPORT_SCHEDULER \
  CATSCAN_ENABLE_PRECOMPUTE_SCHEDULER \
  CATSCAN_ENABLE_CREATIVE_CACHE_SCHEDULER; do
  if ! grep -qx "${scheduler_flag}=false" "$RUNTIME_ENV_SOURCE"; then
    echo "Shadow runtime must set ${scheduler_flag}=false." >&2
    exit 1
  fi
done
if ! grep -Eq '^SECRETS_NAME_PREFIX=[A-Za-z0-9_-]+$' "$RUNTIME_ENV_SOURCE" || \
   ! grep -Eq '^GCP_PROJECT_ID=[A-Za-z0-9._:-]+$' "$RUNTIME_ENV_SOURCE"; then
  echo "Runtime env is missing the Google project or secret prefix." >&2
  exit 1
fi

install -d -o root -g "$CONTAINER_GID" -m 0750 "$SECRET_DIR"
install -o root -g "$CONTAINER_GID" -m 0440 \
  "$POSTGRES_PASSWORD_SOURCE" "$SECRET_DIR/postgres-password"
install -o root -g "$CONTAINER_GID" -m 0440 \
  "$POSTGRES_CA_SOURCE" "$SECRET_DIR/postgres-ca.crt"
install -o root -g "$CONTAINER_GID" -m 0440 \
  "$GOOGLE_CREDENTIALS_SOURCE" "$SECRET_DIR/google-adc.json"
install -o root -g root -m 0600 "$RUNTIME_ENV_SOURCE" /etc/rtbcat/runtime.env
install -d -o "$CONTAINER_UID" -g "$CONTAINER_GID" -m 0750 /var/lib/rtbcat/app-data

cat > /etc/rtbcat/app-runtime-installed.env <<EOF
RTBCAT_RUNTIME_CONTAINER_UID=${CONTAINER_UID}
RTBCAT_RUNTIME_CONTAINER_GID=${CONTAINER_GID}
RTBCAT_GOOGLE_ADC_TYPE=${adc_type}
EOF
chmod 0644 /etc/rtbcat/app-runtime-installed.env

echo "Installed Part 3 runtime files; no secret values were printed."
