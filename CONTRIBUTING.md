# Contributing

Thanks for contributing to Cat-Scan.

## Development Setup

1. Install prerequisites from `INSTALL.md`.
2. Install the contributor Python/tooling bundle:
   - `CATSCAN_PYTHON_REQUIREMENTS=requirements-dev.txt ./setup.sh`
   - or `./venv/bin/pip install -r requirements-dev.txt` if the app is already set up
3. Copy `.env.example` to `.env` and configure local values.
4. Start backend/frontend and verify basic health:
   - API: `http://localhost:8000/health`
   - Dashboard: `http://localhost:3000`

## Pull Request Rules

1. Keep PRs focused and small.
2. Include tests for behavioral changes.
3. Update docs for user-visible or operational changes.
4. Do not include secrets, credentials, customer data, or infrastructure-private details.

## Security Requirements

1. Follow `docs/SECURITY.md`.
2. Never commit:
   - `.env`, `terraform.tfvars`, `*.tfstate`
   - service-account JSON keys
   - database dumps, customer CSVs, or private logs
3. If you find a vulnerability, follow the security reporting section in `docs/SECURITY.md` instead of opening a public exploit issue.

## Quality Checklist

Before opening a PR:

1. Run unit/integration tests relevant to your change.
2. Run lint/format checks for touched languages.
3. Ensure workflows still pass (`security.yml` and project CI).
4. Verify no sensitive content is present in commits.
5. Run `./scripts/oss_release_preflight.sh --quick` before changing release-facing docs or dependencies.
