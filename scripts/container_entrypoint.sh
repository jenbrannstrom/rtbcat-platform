#!/bin/sh
# Build the PostgreSQL DSN inside the container from a mounted password file.
# Existing deployments that already provide POSTGRES_DSN are unchanged.

set -eu

if [ -n "${POSTGRES_PASSWORD_FILE:-}" ]; then
  if [ -n "${POSTGRES_DSN:-}" ] || [ -n "${POSTGRES_SERVING_DSN:-}" ]; then
    echo "POSTGRES_PASSWORD_FILE cannot be combined with a prebuilt PostgreSQL DSN." >&2
    exit 1
  fi

  if [ -z "${POSTGRES_HOST:-}" ] || [ -z "${POSTGRES_PORT:-}" ] || \
     [ -z "${POSTGRES_DB:-}" ] || [ -z "${POSTGRES_USER:-}" ]; then
    echo "POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB and POSTGRES_USER are required." >&2
    exit 1
  fi

  if [ ! -r "$POSTGRES_PASSWORD_FILE" ]; then
    echo "PostgreSQL password file is not readable." >&2
    exit 1
  fi

  POSTGRES_SSLMODE="${POSTGRES_SSLMODE:-verify-full}"
  export POSTGRES_SSLMODE
  if { [ "$POSTGRES_SSLMODE" = "verify-full" ] || [ "$POSTGRES_SSLMODE" = "verify-ca" ]; } && \
     { [ -z "${POSTGRES_SSL_ROOT_CERT_FILE:-}" ] || [ ! -r "$POSTGRES_SSL_ROOT_CERT_FILE" ]; }; then
    echo "A readable PostgreSQL root certificate is required for ${POSTGRES_SSLMODE}." >&2
    exit 1
  fi

  generated_dsn="$(python3 - <<'PY'
import os
from pathlib import Path
from urllib.parse import quote, urlencode

password_path = Path(os.environ["POSTGRES_PASSWORD_FILE"])
password_bytes = password_path.read_bytes()
if password_bytes.endswith(b"\r\n"):
    password_bytes = password_bytes[:-2]
elif password_bytes.endswith(b"\n"):
    password_bytes = password_bytes[:-1]
if b"\n" in password_bytes or b"\r" in password_bytes:
    raise SystemExit("PostgreSQL password file must contain exactly one line.")
password = password_bytes.decode("utf-8")
if len(password) < 24:
    raise SystemExit("PostgreSQL password must be at least 24 characters.")

user = quote(os.environ["POSTGRES_USER"], safe="")
encoded_password = quote(password, safe="")
host = os.environ["POSTGRES_HOST"]
port = os.environ["POSTGRES_PORT"]
database = quote(os.environ["POSTGRES_DB"], safe="")
query = {
    "application_name": "rtbcat_hetzner",
    "connect_timeout": "10",
    "sslmode": os.environ.get("POSTGRES_SSLMODE", "verify-full"),
}
root_cert = os.environ.get("POSTGRES_SSL_ROOT_CERT_FILE", "")
if root_cert:
    query["sslrootcert"] = root_cert
print(f"postgresql://{user}:{encoded_password}@{host}:{port}/{database}?{urlencode(query)}")
PY
)"
  export POSTGRES_DSN="$generated_dsn"
  export POSTGRES_SERVING_DSN="$generated_dsn"
  unset generated_dsn
fi

exec "$@"
