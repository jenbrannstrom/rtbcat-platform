"""Policy for mutable caches that can only invalidate within one process."""

import os


def mutable_process_cache_enabled() -> bool:
    """Only cache mutable control state when the API runs a single worker.

    The container uses UVICORN_WORKERS (default 1) to start Uvicorn. With
    multiple workers, a write cannot invalidate another worker's Python dict,
    so pretargeting reads must go to Postgres. Invalid settings fail closed.
    """
    try:
        return int(os.environ.get("UVICORN_WORKERS", "1")) == 1
    except ValueError:
        return False
