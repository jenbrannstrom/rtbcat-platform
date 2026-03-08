#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT_REPO="${1:-/tmp/rtbcat-public-snapshot.git}"
SOURCE_REF="${2:-HEAD}"
PUBLIC_BRANCH="${PUBLIC_BRANCH:-main}"
PUBLIC_TAG="${PUBLIC_TAG:-}"
COMMIT_MESSAGE="${PUBLIC_COMMIT_MESSAGE:-Public OSS snapshot}"
AUTHOR_NAME="${PUBLIC_AUTHOR_NAME:-Cat-Scan OSS}"
AUTHOR_EMAIL="${PUBLIC_AUTHOR_EMAIL:-oss@example.invalid}"

rm -rf "$OUT_REPO"
git init --bare "$OUT_REPO" >/dev/null

git -C "$OUT_REPO" fetch --quiet "$REPO_ROOT" "$SOURCE_REF"
TREE_ID="$(git -C "$OUT_REPO" rev-parse FETCH_HEAD^{tree})"

export GIT_AUTHOR_NAME="$AUTHOR_NAME"
export GIT_AUTHOR_EMAIL="$AUTHOR_EMAIL"
export GIT_COMMITTER_NAME="$AUTHOR_NAME"
export GIT_COMMITTER_EMAIL="$AUTHOR_EMAIL"

COMMIT_ID="$(
  printf '%s\n' "$COMMIT_MESSAGE" | git -C "$OUT_REPO" commit-tree "$TREE_ID"
)"

git -C "$OUT_REPO" update-ref "refs/heads/${PUBLIC_BRANCH}" "$COMMIT_ID"
git -C "$OUT_REPO" symbolic-ref HEAD "refs/heads/${PUBLIC_BRANCH}"

if [[ -n "$PUBLIC_TAG" ]]; then
  git -C "$OUT_REPO" tag -a "$PUBLIC_TAG" -m "$PUBLIC_TAG" "$COMMIT_ID"
fi

git -C "$OUT_REPO" update-ref -d FETCH_HEAD >/dev/null 2>&1 || true
git -C "$OUT_REPO" reflog expire --expire=now --all
git -C "$OUT_REPO" gc --prune=now >/dev/null

echo "Public snapshot repo created: $OUT_REPO"
echo "Source ref: $SOURCE_REF"
echo "Branch: $PUBLIC_BRANCH"
if [[ -n "$PUBLIC_TAG" ]]; then
  echo "Tag: $PUBLIC_TAG"
fi
echo "Commit: $COMMIT_ID"
echo
echo "Refs:"
git -C "$OUT_REPO" show-ref
