# Git history cleanup — 2026-10-14

Historical credentials were removed from the repository history. The exposed
Google OAuth credentials were retired. Gmail access was verified after rotation.

## Use a new clone

If you have an old clone, keep a private copy of your local changes first.
Create a new clone of the GitHub repository. Copy only the changes that you need.
Review each change before you commit it.

Do not merge or push an old branch into the new history. Do not restore an old
backup to GitHub. These actions can restore the removed credentials.

## Branches

The active branches are `main` and `release/mcp-publisher-0.10.0`. The other 58
branches were archived before deletion. Some contain unmerged work. Their
removal does not mean that all their changes were accepted.

Maintainers retain a private archive and a branch index for recovery. Inspect an
archived change before you apply it to a new branch. Do not restore its full history.
Delete feature branches after merge. Keep release branches only while they are active.

## Commit and tag identities

Affected commits have new IDs. Existing version tags retain their names and
point to the cleaned history. Generated source archive checksums can change.
This cleanup does not create a new release or rebuild published images.

The deployed source commit `ffcf8a0736436d20e312d40e8f531b4e6e93b97b` maps to
`db1e815532c51cc4e564cb6cd30523ac998f50e0` in the cleaned history. Production
image digests and their original commit labels remain unchanged. Use the release
manifest to identify a deployed image.

The release candidate commit `ae8e557f47f3521d2199ea3ee9785dcd6380a2fc` maps to
`5cc50d504b71fe909a8081d145933f133802ce44`, before the cleanup documentation
and scanner fingerprint updates. Maintainers retain the full commit map.

## Remaining copies

GitHub can retain old pull-request references and cached commit views. These
require separate review with GitHub Support. Local clones and third-party mirrors
can also retain the old history. The Gitee mirror has not been updated.

A clean branch scan does not prove that all copies have been removed. Retired
credentials must remain disabled. The release candidate must pass its remaining
release checks before a stable version is published.
