#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MIRROR_DIR="${1:-/tmp/rtbcat-oss-rewrite.git}"
SOURCE_REPO="${2:-$REPO_ROOT}"
REPLACE_FILE="/tmp/rtbcat-oss-rewrite.replace-text"

rm -rf "$MIRROR_DIR"
git clone --mirror "$SOURCE_REPO" "$MIRROR_DIR"

cat > "$REPLACE_FILE" <<'EOF'
REMOVED_CADDY_AUTH_TOKEN==>REMOVED_CADDY_AUTH_TOKEN
demo-maskable-value-1234567890==>demo-maskable-value-1234567890
EOF

cp "$REPO_ROOT/.gitleaksignore" "$MIRROR_DIR/.gitleaksignore"

(
  cd "$MIRROR_DIR"
  git filter-repo --force \
    --path-regex '^docs/ai_logs/.*$' \
    --path docs/AWS_DEPLOYMENT.md \
    --path docs/vm-rebuild-runbook.md \
    --path-regex '^creative-intelligence/venv/.*$' \
    --path-regex '(^|/).*\.tfstate(\.backup)?$' \
    --path-regex '(^|/)terraform\.tfvars$' \
    --invert-paths \
    --replace-text "$REPLACE_FILE"

  gitleaks detect \
    --source=. \
    --no-banner \
    --report-format json \
    --report-path /tmp/rtbcat-oss-rewrite-gitleaks.json \
    >/tmp/rtbcat-oss-rewrite-gitleaks.txt 2>&1 || true

  python3 - <<'PY'
import json
from pathlib import Path

report = Path("/tmp/rtbcat-oss-rewrite-gitleaks.json")
if report.exists() and report.stat().st_size:
    findings = json.loads(report.read_text())
    print(f"Remaining gitleaks findings after rewrite: {len(findings)}")
    print("Remaining fingerprints:")
    for finding in findings:
        print(f"  {finding['Fingerprint']}")
else:
    print("Remaining gitleaks findings after rewrite: 0")
PY

  echo "Mirror rewrite complete: $MIRROR_DIR"
  echo "Source repo: $SOURCE_REPO"
  echo "Gitleaks report: /tmp/rtbcat-oss-rewrite-gitleaks.json"
  echo "Gitleaks console: /tmp/rtbcat-oss-rewrite-gitleaks.txt"
)
