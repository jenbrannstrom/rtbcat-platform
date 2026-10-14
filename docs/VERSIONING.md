# Versioning and publication

RTBcat uses a SemVer source release and an independent deployed build identity.

- `VERSION` and `[project].version` in `pyproject.toml` must agree.
- A published source release has an annotated `vX.Y.Z` tag pointing to the reviewed commit.
- `CHANGELOG.md` marks a candidate as unreleased until the release gates pass.
- Images use immutable `sha-<40-character-commit>` tags and are deployed by digest.
  The current workflow does not publish `latest` or SemVer image tags.
- `/health` exposes `release_version`, `version` and `git_sha`; the dashboard footer
  shows the human version and build identity. A source tag does not change production.

## Prepare and review

1. Work in a clean branch from the current upstream commit. Preserve unrelated local work.
2. Update version metadata, changelog, client instructions and relevant READMEs.
3. Run the [OSS release checklist](OSS_RELEASE_CHECKLIST.md), including dependency
   audits and history scanning. Resolve findings; do not hide real credentials.
4. Open a pull request. Wait for required security and regression checks on its
   exact head, then merge only the reviewed change. Recheck after changes.

## Tag and publish source

After the gates pass, replace the candidate changelog heading with its date and
version, commit it, and create an annotated tag on that exact commit:

```bash
git tag -a vX.Y.Z REVIEWED_COMMIT -m "RTBcat vX.Y.Z"
git push origin vX.Y.Z
gh release create vX.Y.Z --verify-tag --title 'RTBcat vX.Y.Z' --notes-file /path/release-notes.md
```

Use the same reviewed commit and annotated tag on Gitee. Fetch its branch first,
verify that it is an ancestor, and use a normal fast-forward push. Do not use
`--mirror` or a force push: either could overwrite independent refs or history.
Authenticate separately to Gitee. Public source publication never includes app
credentials, customer reports, private runbooks or a user's connector token.

## Build and deploy separately

`build-and-push-ghcr.yml` is **manual-only**. Pushing a tag does not build images
or deploy. Dispatch it on the reviewed branch/tag with `confirm=PUBLISH_HETZNER`.
It tests and builds API, dashboard and MCP images from one exact commit and emits
`hetzner-release.env` plus the matching compose file. Preserve those artifacts and
verify their commit and image digests before deployment.

The host deployment is another explicit step using
`scripts/hetzner/deploy_app_release.sh`. The mode must match the current host's
posture, and MCP must be explicitly enabled if intended. Confirm backups and wait
for active imports/precompute work to finish before replacing containers.
Run `scripts/hetzner/verify_app_release.sh` with the matching mode and MCP setting,
then validate an authenticated client query. Rollback uses the previous manifest
and digest-pinned images. Never hot-patch running containers.

Production runs on Hetzner. The retired GCP writer remains stopped; historical
GCP deployment material is not a release procedure. See [CLAUDE.md](../CLAUDE.md)
and [Hetzner tooling](../scripts/hetzner/README.md) for deployment invariants.
