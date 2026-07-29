# Security Audit Assessment

The Codex Security scan is serious, and its highest-risk findings look credible from the cited source paths.

## Scan status

The captured “unsealed draft” message is outdated. The scan was subsequently finalized at **2026-07-29 21:03:58 SAST**:

- Status: `completed`
- Sealed: yes
- Revision: current clean `HEAD` (`99b292e3670ebb2ec697b79dcb41f8db32750dc5`)
- Findings: 112
- Severity mix: 22 high, 60 medium, 30 low
- Confidence mix: 88 high, 24 medium
- SARIF results: 112
- Manifest hashes match the canonical artifacts
- `report.md` and derived finding IDs exist

## High-risk findings

The 22 high findings reduce to two systemic defects.

### 1. Authorization and tenant isolation

Nineteen high findings concern authorization or tenant isolation:

- “Admin of any seat” is accepted where admin of the target seat is required.
- Read access is used for optimizer mutations and live application.
- Several campaign reads lack object-level authorization entirely.
- The affected areas include live Google configuration, imports, optimizer controls, campaign data, and recommendations.

### 2. Optimizer SSRF and data exfiltration

Three high findings concern optimizer SSRF and exfiltration:

- Arbitrary optimizer URLs reach `urllib.request.urlopen` directly.
- Stored authorization headers and buyer performance features can be sent to attacker-selected or internal destinations.
- Redirects, private addresses, metadata endpoints, and DNS rebinding are not controlled.

## Recommended immediate containment

- Temporarily sudo-gate live pretargeting and QPS actions, as well as cross-buyer imports.
- Disable or sudo-gate optimizer model creation, modification, validation, scoring, and score-and-propose.
- Block application egress to loopback, private, link-local, and cloud-metadata networks.
- Implement target-object ownership checks and a centralized safe outbound HTTP client.

## Next-priority findings

The next medium-priority cluster includes:

- Campaign mutation IDORs
- Unsigned conversion callbacks that fail open
- Browser-based SSRF
- GitHub Actions shell injection
- Production and customer information committed to documentation

## Validation caveat

The scan metadata contains an inconsistency: the captured response says runtime tests were unavailable, while the sealed manifest says targeted tests were used. Treat this as a primarily static review until the findings are reproduced using the project’s real test environment.

## Artifacts

- [Security report](/home/jen/.codex/state/plugins/codex-security/scans/rtbcat-platform/codex-security-rtbcat-platform-7XuyDZ/report.md)
- [Canonical findings](/home/jen/.codex/state/plugins/codex-security/scans/rtbcat-platform/codex-security-rtbcat-platform-7XuyDZ/findings.json)
- [SARIF export](/home/jen/.codex/state/plugins/codex-security/scans/rtbcat-platform/codex-security-rtbcat-platform-7XuyDZ/exports/results.sarif)

No application code was changed during this assessment.
