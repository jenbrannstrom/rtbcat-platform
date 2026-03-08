# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in Cat-Scan, **please do not open a public issue**.

Instead, report it privately:

1. **Email**: Send details to the repository maintainer (see GitHub profile).
2. **GitHub Private Advisory**: Use the "Report a vulnerability" button under the Security tab of this repository if available.

Include:
- A description of the vulnerability and its potential impact.
- Steps to reproduce or a proof-of-concept.
- Any suggested fix (optional but appreciated).

We will acknowledge receipt within **72 hours** and aim to provide a fix or mitigation within **14 days** for critical issues.

## Scope

This policy covers the Cat-Scan application code in this repository.
It does **not** cover your own deployment infrastructure, cloud credentials, or
data — those are your responsibility to secure.

## Deployment Security

For guidance on securing your own deployment (credentials, secrets management,
GCP hardening), see [docs/SECURITY.md](docs/SECURITY.md).

## Supported Versions

Only the latest release on the `main` branch receives security
updates. If you are running an older checkout, pull the latest before
reporting.
