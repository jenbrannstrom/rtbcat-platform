# Versioning Policy

Cat-Scan uses two version identifiers on purpose:

## 1) Release Version (human-facing)

- Source of truth: root `VERSION` file
- Format: SemVer (`MAJOR.MINOR.PATCH`, example `0.9.2`)
- Git tag format: annotated tag `vMAJOR.MINOR.PATCH` (example `v0.9.2`)
- Purpose: public release communication and changelog alignment

## 2) Build ID (machine/deploy-facing)

- Format: `sha-<short_commit_sha>` (example `sha-a4c50dc`)
- Produced by CI for every image build
- Used for deploy pinning, rollback, and runtime verification

## Runtime Surfaces

- `/health` returns:
  - `release_version`: SemVer from `RELEASE_VERSION` or `VERSION`
  - `version`: build ID (`sha-...`)
  - `git_sha`: short commit SHA
- Dashboard footer shows `v<release_version> (<build_id>)`

## CI Enforcement

- CI build workflow validates that:
  - `VERSION` is valid SemVer
  - On tag builds, pushed tag exactly matches `v$(cat VERSION)`
- Images are always tagged with:
  - `sha-<short_sha>`
  - `latest`
  - `vX.Y.Z` (only on release tag builds)

## Release Procedure

1. Update `VERSION` to the new SemVer.
2. Update `CHANGELOG.md` with user-facing changes.
3. Commit: `git commit -m "release: vX.Y.Z"`.
4. Create annotated tag: `git tag -a vX.Y.Z -m "vX.Y.Z"`.
5. Push branch and tag: `git push origin unified-platform && git push origin vX.Y.Z`.
