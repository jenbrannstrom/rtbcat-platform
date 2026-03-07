#!/usr/bin/env bash
# oss_release_preflight.sh — OSS publication preflight gate
#
# Run all security / hygiene checks required before an open-source release.
# Exit 0 only if every check passes.
#
# Usage:
#   ./scripts/oss_release_preflight.sh          # all checks
#   ./scripts/oss_release_preflight.sh --quick   # skip slow network audits

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
QUICK=false
FAIL=0

[[ "${1:-}" == "--quick" ]] && QUICK=true

red()   { printf '\033[1;31m%s\033[0m\n' "$*"; }
green() { printf '\033[1;32m%s\033[0m\n' "$*"; }
info()  { printf '\033[0;36m[check]\033[0m %s\n' "$*"; }
fail()  { red "FAIL: $*"; FAIL=1; }

# ── 1. Forbidden tracked files ──────────────────────────────────────

info "Scanning git-tracked files for forbidden patterns"

FORBIDDEN_PATTERNS=(
  '\.env$'
  '\.env\.local$'
  '\.env\.production$'
  'terraform\.tfvars$'
  '\.tfstate$'
  '\.tfstate\.backup$'
  'catscan-ci-key\.json$'
  'service.account.*\.json$'
  'credentials\.json$'
  '\.pem$'
  '\.p12$'
  'id_rsa$'
  'id_ed25519$'
  '\.sqlite$'
  '\.sqlite3$'
)

PATTERN=$(IFS='|'; echo "${FORBIDDEN_PATTERNS[*]}")
FOUND=$(git -C "$REPO_ROOT" ls-files | grep -iE "$PATTERN" || true)

if [[ -n "$FOUND" ]]; then
  fail "Forbidden files are tracked in git:"
  echo "$FOUND" | sed 's/^/  /'
else
  green "  No forbidden files tracked"
fi

# ── 2. Gitleaks secret scan ─────────────────────────────────────────

info "Running gitleaks secret scan"

if command -v gitleaks &>/dev/null; then
  if gitleaks detect --source="$REPO_ROOT" --no-banner --exit-code 1 2>&1; then
    green "  gitleaks: clean"
  else
    fail "gitleaks found secrets — review output above"
  fi
else
  red "  SKIP: gitleaks not installed (install: https://github.com/gitleaks/gitleaks#install)"
  FAIL=1
fi

# ── 3. pip-audit (Python dependencies) ──────────────────────────────

if [[ "$QUICK" == false ]]; then
  info "Running pip-audit on Python requirements files"

  if command -v pip-audit &>/dev/null; then
    for req in requirements.txt requirements-ai.txt requirements-dev.txt; do
      if pip-audit -r "$REPO_ROOT/$req" 2>&1; then
        green "  pip-audit: $req is clean"
      else
        fail "pip-audit found vulnerabilities in $req"
      fi
    done
  else
    red "  SKIP: pip-audit not installed (pip install pip-audit)"
    FAIL=1
  fi
else
  info "Skipping pip-audit (--quick)"
fi

# ── 4. npm audit (dashboard) ────────────────────────────────────────

if [[ "$QUICK" == false ]]; then
  info "Running npm audit on dashboard/"

  if command -v npm &>/dev/null; then
    if (cd "$REPO_ROOT/dashboard" && npm audit --audit-level=high 2>&1); then
      green "  npm audit: no high/critical vulnerabilities"
    else
      fail "npm audit found high/critical vulnerabilities"
    fi
  else
    red "  SKIP: npm not installed"
    FAIL=1
  fi
else
  info "Skipping npm audit (--quick)"
fi

# ── 5. Required root files ──────────────────────────────────────────

info "Checking required OSS root files"

for f in SECURITY.md LICENSE; do
  if [[ -f "$REPO_ROOT/$f" ]]; then
    green "  $f exists"
  else
    fail "$f missing from repository root"
  fi
done

# ── 6. .gitignore coverage ──────────────────────────────────────────

info "Verifying .gitignore covers critical patterns"

REQUIRED_IGNORES=('.env' '*.db' 'terraform.tfstate' 'terraform.tfvars' 'catscan-ci-key.json')
for pat in "${REQUIRED_IGNORES[@]}"; do
  if grep -qF "$pat" "$REPO_ROOT/.gitignore"; then
    green "  .gitignore covers: $pat"
  else
    fail ".gitignore missing pattern: $pat"
  fi
done

# ── 7. VERSION format ────────────────────────────────────────────────

info "Validating VERSION format"

VERSION_VALUE="$(tr -d '[:space:]' < "$REPO_ROOT/VERSION" 2>/dev/null || true)"
if [[ -z "$VERSION_VALUE" ]]; then
  fail "VERSION file missing or empty"
elif [[ "$VERSION_VALUE" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  green "  VERSION is valid SemVer: $VERSION_VALUE"
else
  fail "VERSION must be SemVer (X.Y.Z), got: $VERSION_VALUE"
fi

# ── 8. pyproject metadata sync ──────────────────────────────────────

info "Checking pyproject.toml release metadata"

PYPROJECT_VERSION="$(
  cd "$REPO_ROOT"
  python3 - <<'PY'
from pathlib import Path
import tomllib

data = tomllib.loads(Path("pyproject.toml").read_text())
print(data["project"]["version"])
PY
)"
if [[ "$PYPROJECT_VERSION" == "$VERSION_VALUE" ]]; then
  green "  pyproject.toml version matches VERSION"
else
  fail "pyproject.toml version ($PYPROJECT_VERSION) does not match VERSION ($VERSION_VALUE)"
fi

# ── Summary ─────────────────────────────────────────────────────────

echo ""
if [[ "$FAIL" -eq 0 ]]; then
  green "All preflight checks passed."
  exit 0
else
  red "One or more preflight checks failed — see above."
  exit 1
fi
