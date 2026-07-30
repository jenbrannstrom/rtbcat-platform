#!/usr/bin/env python3
"""Fail when tracked files contain private identifiers.

This repository is public. A standing redaction boundary keeps a small set of
identifiers out of tracked files: the pgBackRest repository bucket, the private
finance role/controller names, and client spend figures newer than the already
published handover sections.

The patterns themselves are private, so they are never stored here. They are
read from a denylist outside the tracked tree — `docs/internal/` locally (which
is gitignored) or a CI secret materialized at runtime. Each non-empty,
non-comment line is one fixed string or, when prefixed with `re:`, one regular
expression.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DENYLIST = Path("docs/internal/redaction-denylist.txt")
DENYLIST_ENV = "RTBCAT_REDACTION_DENYLIST"

# Paths that legitimately describe the boundary itself.
SKIP_PATHS = {
    "scripts/check_redaction_boundary.py",
}


@dataclass(frozen=True)
class DenyPattern:
    fingerprint: str
    expression: re.Pattern[str]
    literal: bytes | None


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--denylist",
        type=Path,
        help=(
            "Denylist file. Defaults to the "
            f"{DENYLIST_ENV} environment variable, then {DEFAULT_DENYLIST}."
        ),
    )
    parser.add_argument(
        "--require-denylist",
        action="store_true",
        help="Fail when the denylist is absent. Use this in CI.",
    )
    parser.add_argument(
        "--paths",
        nargs="*",
        help="Limit the scan to these paths. The default is every tracked file.",
    )
    return parser


def _resolve_denylist(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit
    from_env = os.environ.get(DENYLIST_ENV, "").strip()
    if from_env:
        return Path(from_env)
    return DEFAULT_DENYLIST


def _load_patterns(path: Path) -> list[DenyPattern]:
    patterns: list[DenyPattern] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fingerprint = hashlib.sha256(line.encode("utf-8")).hexdigest()[:12]
        if line.startswith("re:"):
            expression = line[3:].strip()
            patterns.append(
                DenyPattern(
                    fingerprint=fingerprint,
                    expression=re.compile(expression, re.IGNORECASE),
                    literal=None,
                )
            )
        else:
            patterns.append(
                DenyPattern(
                    fingerprint=fingerprint,
                    expression=re.compile(re.escape(line), re.IGNORECASE),
                    literal=line.encode("utf-8"),
                )
            )
    return patterns


def _tracked_files(paths: list[str] | None) -> list[str]:
    command = ["git", "ls-files", "-z"]
    if paths:
        command.extend(["--"] + paths)
    result = subprocess.run(command, capture_output=True, check=True, text=True)
    return [entry for entry in result.stdout.split("\0") if entry]


def _scan(
    files: list[str], patterns: list[DenyPattern]
) -> list[tuple[str, int, str]]:
    hits: list[tuple[str, int, str]] = []
    for name in files:
        if name in SKIP_PATHS:
            continue
        try:
            content = Path(name).read_bytes()
        except OSError:
            continue
        for number, raw_line in enumerate(content.split(b"\n"), start=1):
            folded_line = raw_line.lower()
            decoded_line: str | None = None
            for pattern in patterns:
                matched = False
                if pattern.literal is not None:
                    # Fixed entries are checked as raw bytes so disclosures in
                    # images, PDFs, archives, or metadata are not skipped.
                    matched = pattern.literal.lower() in folded_line
                if not matched:
                    # Regex entries, and non-ASCII case folding for fixed
                    # entries, run over a loss-tolerant extraction. Printable
                    # strings in binary files remain visible around bad bytes.
                    if decoded_line is None:
                        decoded_line = raw_line.decode("utf-8", errors="replace")
                    matched = bool(pattern.expression.search(decoded_line))
                if matched:
                    hits.append((name, number, pattern.fingerprint))
    return hits


def main() -> int:
    args = _parser().parse_args()
    denylist = _resolve_denylist(args.denylist)

    if not denylist.is_file():
        message = f"redaction denylist not found at {denylist}"
        if args.require_denylist:
            print(f"FAIL: {message}", file=sys.stderr)
            return 2
        print(f"SKIP: {message}; boundary not enforced in this run")
        return 0

    patterns = _load_patterns(denylist)
    if not patterns:
        print(f"FAIL: {denylist} contains no patterns", file=sys.stderr)
        return 2

    hits = _scan(_tracked_files(args.paths), patterns)
    if hits:
        # Report the location and which pattern matched, never the matched text,
        # so CI logs stay publishable.
        print(
            f"FAIL: {len(hits)} redaction-boundary violation(s) in tracked files:",
            file=sys.stderr,
        )
        for name, number, fingerprint in hits:
            print(
                f"  {name}:{number} matched denylist entry [{fingerprint}]",
                file=sys.stderr,
            )
        print(
            "\nRemove the identifier or move the detail into docs/internal/.",
            file=sys.stderr,
        )
        return 1

    print(f"OK: {len(patterns)} pattern(s) checked, no violations in tracked files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
