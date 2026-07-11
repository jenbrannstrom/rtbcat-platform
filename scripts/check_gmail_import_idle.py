#!/usr/bin/env python3
"""Exit non-zero when a Gmail report import owns the production lock."""

from __future__ import annotations

import sys
from pathlib import Path

APP_ROOT = Path("/app")
if APP_ROOT.exists():
    sys.path.insert(0, str(APP_ROOT))

from scripts.gmail_import import get_status  # noqa: E402


def main() -> int:
    running = bool(get_status().get("running"))
    print(f"gmail_import_running={str(running).lower()}")
    return 1 if running else 0


if __name__ == "__main__":
    raise SystemExit(main())
