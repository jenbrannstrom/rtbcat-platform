"""Durable PostgreSQL-backed queue for precompute refresh jobs.

A full precompute refresh can run for hours, far past Cloud Scheduler's
30-minute attempt deadline and any sane edge proxy timeout. Trigger endpoints
therefore enqueue a row in ``precompute_jobs`` and return immediately; a
single worker claims jobs one at a time and runs the refresh chain.

Concurrency contract:
- At most one job runs across the whole deployment. Claims are serialized
  with a transaction-scoped advisory lock, and a claim is refused while any
  live ``running`` job exists.
- Retries of the same scheduled execution collapse onto the active job via
  the ``dedupe_key`` partial unique index.
- A worker that dies mid-job (deploy, crash) leaves a ``running`` row with a
  stale heartbeat; the next claim cycle re-queues it, or fails it once its
  attempts are exhausted.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
from typing import Any, Optional

from storage.postgres_database import pg_query_one, pg_transaction_async

logger = logging.getLogger(__name__)

# Arbitrary but stable application-wide advisory lock id for claim
# serialization. Must not collide with other advisory locks in this codebase.
_CLAIM_LOCK_ID = 84_299_137_001

POLL_INTERVAL_SECONDS = 30
HEARTBEAT_INTERVAL_SECONDS = 60
STALE_HEARTBEAT_MINUTES = 15
MAX_ATTEMPTS = 3


def _worker_identity() -> str:
    return os.getenv("HOSTNAME") or socket.gethostname() or "unknown"


async def enqueue_precompute_job(
    *,
    source: str,
    start_date: str,
    end_date: str,
    dedupe_key: str,
    include_legacy_performance: bool = False,
    run_validation: bool = True,
) -> dict[str, Any]:
    """Insert a refresh job, or return the active job for the same dedupe key.

    Returns a dict with ``job_id``, ``status`` and ``deduplicated``.
    """

    def _enqueue(conn) -> dict[str, Any]:
        row = conn.execute(
            """
            INSERT INTO precompute_jobs (
                source, dedupe_key, start_date, end_date,
                include_legacy_performance, run_validation
            ) VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (dedupe_key) WHERE status IN ('queued', 'running')
            DO NOTHING
            RETURNING id, status
            """,
            (
                source,
                dedupe_key,
                start_date,
                end_date,
                include_legacy_performance,
                run_validation,
            ),
        ).fetchone()
        if row is not None:
            return {"job_id": row["id"], "status": row["status"], "deduplicated": False}
        existing = conn.execute(
            """
            SELECT id, status FROM precompute_jobs
            WHERE dedupe_key = %s AND status IN ('queued', 'running')
            LIMIT 1
            """,
            (dedupe_key,),
        ).fetchone()
        if existing is None:
            # The active job finished between our INSERT and SELECT; retrying
            # from scratch would enqueue duplicate work for a window that was
            # just refreshed, so surface the race instead.
            raise RuntimeError(
                f"Enqueue conflict for dedupe_key={dedupe_key} but no active job found"
            )
        return {
            "job_id": existing["id"],
            "status": existing["status"],
            "deduplicated": True,
        }

    result = await pg_transaction_async(_enqueue)
    logger.info(
        "Precompute job enqueue source=%s window=%s..%s dedupe_key=%s -> job_id=%s deduplicated=%s",
        source,
        start_date,
        end_date,
        dedupe_key,
        result["job_id"],
        result["deduplicated"],
    )
    return result


def _claim_next(conn) -> Optional[dict[str, Any]]:
    """Reclaim abandoned jobs, then claim the oldest queued one.

    Runs inside a single transaction. Returns the claimed job row or None.
    """
    locked = conn.execute(
        "SELECT pg_try_advisory_xact_lock(%s) AS locked", (_CLAIM_LOCK_ID,)
    ).fetchone()
    if not locked or not locked["locked"]:
        return None

    # Jobs abandoned by a restart: fail them once attempts are exhausted,
    # otherwise put them back in the queue.
    conn.execute(
        """
        UPDATE precompute_jobs
        SET status = 'failed',
            error_text = 'abandoned: heartbeat stale after ' || attempts || ' attempt(s)',
            finished_at = CURRENT_TIMESTAMP
        WHERE status = 'running'
          AND heartbeat_at < CURRENT_TIMESTAMP - make_interval(mins => %s)
          AND attempts >= %s
        """,
        (STALE_HEARTBEAT_MINUTES, MAX_ATTEMPTS),
    )
    conn.execute(
        """
        UPDATE precompute_jobs
        SET status = 'queued', claimed_by = NULL, started_at = NULL, heartbeat_at = NULL
        WHERE status = 'running'
          AND heartbeat_at < CURRENT_TIMESTAMP - make_interval(mins => %s)
        """,
        (STALE_HEARTBEAT_MINUTES,),
    )

    live = conn.execute(
        "SELECT 1 FROM precompute_jobs WHERE status = 'running' LIMIT 1"
    ).fetchone()
    if live is not None:
        return None

    return conn.execute(
        """
        UPDATE precompute_jobs
        SET status = 'running',
            attempts = attempts + 1,
            claimed_by = %s,
            started_at = CURRENT_TIMESTAMP,
            heartbeat_at = CURRENT_TIMESTAMP
        WHERE id = (
            SELECT id FROM precompute_jobs
            WHERE status = 'queued'
            ORDER BY enqueued_at
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        )
        RETURNING id, source, start_date::text, end_date::text,
                  include_legacy_performance, run_validation, attempts
        """,
        (_worker_identity(),),
    ).fetchone()


async def _heartbeat_loop(job_id: int) -> None:
    from storage.postgres_database import pg_execute

    while True:
        await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
        try:
            await pg_execute(
                "UPDATE precompute_jobs SET heartbeat_at = CURRENT_TIMESTAMP "
                "WHERE id = %s AND status = 'running'",
                (job_id,),
            )
        except Exception:
            logger.warning("Heartbeat update failed for precompute job %s", job_id)


async def _run_refresh_chain(job: dict[str, Any]) -> dict[str, Any]:
    """Run the same refresh sequence the scheduled endpoint used to run inline."""
    from services.config_precompute import refresh_config_breakdowns
    from services.endpoints_service import EndpointsService
    from services.home_precompute import refresh_home_summaries
    from services.precompute_validation import run_precompute_validation
    from services.rtb_precompute import refresh_rtb_summaries

    start_date = job["start_date"]
    end_date = job["end_date"]

    result: dict[str, Any] = {}
    result["home_summaries"] = await refresh_home_summaries(
        start_date=start_date, end_date=end_date
    )
    result["config_breakdowns"] = await refresh_config_breakdowns(
        start_date=start_date, end_date=end_date
    )
    result["rtb_summaries"] = await refresh_rtb_summaries(start_date, end_date)

    if job.get("include_legacy_performance"):
        from scripts.backfill_performance_metrics import backfill_range

        await asyncio.to_thread(backfill_range, start_date, end_date)
        result["legacy_performance"] = {"refreshed": True}

    result["endpoints_current_rows"] = await EndpointsService().refresh_endpoints_current()

    if job.get("run_validation"):
        result["validation"] = await run_precompute_validation(start_date, end_date)

    return result


async def _execute_job(job: dict[str, Any]) -> None:
    from storage.postgres_database import pg_execute

    job_id = job["id"]
    heartbeat = asyncio.create_task(_heartbeat_loop(job_id))
    try:
        logger.info(
            "Precompute job %s starting (source=%s window=%s..%s attempt=%s)",
            job_id,
            job["source"],
            job["start_date"],
            job["end_date"],
            job["attempts"],
        )
        result = await _run_refresh_chain(job)
        await pg_execute(
            """
            UPDATE precompute_jobs
            SET status = 'succeeded', result = %s, error_text = NULL,
                finished_at = CURRENT_TIMESTAMP, heartbeat_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (json.dumps(result, default=str), job_id),
        )
        logger.info("Precompute job %s succeeded", job_id)
    except asyncio.CancelledError:
        # Shutdown mid-job: leave the row 'running'; the stale-heartbeat
        # reclaim re-queues it after restart.
        logger.warning("Precompute job %s interrupted by shutdown", job_id)
        raise
    except Exception as exc:
        logger.exception("Precompute job %s failed", job_id)
        failed_terminally = job["attempts"] >= MAX_ATTEMPTS
        await pg_execute(
            """
            UPDATE precompute_jobs
            SET status = %s, error_text = %s, finished_at = CASE WHEN %s THEN CURRENT_TIMESTAMP END,
                claimed_by = NULL, heartbeat_at = NULL, started_at = NULL
            WHERE id = %s
            """,
            (
                "failed" if failed_terminally else "queued",
                str(exc)[:2000],
                failed_terminally,
                job_id,
            ),
        )
    finally:
        heartbeat.cancel()


async def process_queue_once() -> bool:
    """One poll cycle: defer to an active Gmail import, else claim and run.

    Returns True when a job was executed.
    """
    # The Gmail worker's import must never compete with a refresh for
    # database and BigQuery capacity; wait for it to finish.
    from scripts.gmail_import import get_status as get_gmail_import_status

    if get_gmail_import_status().get("running"):
        return False

    job = await pg_transaction_async(_claim_next)
    if job is None:
        return False
    await _execute_job(dict(job))
    return True


async def run_precompute_queue_worker() -> None:
    """Poll the queue until cancelled. Started from the app lifespan."""
    logger.info(
        "Precompute queue worker started (poll=%ss, stale_heartbeat=%smin)",
        POLL_INTERVAL_SECONDS,
        STALE_HEARTBEAT_MINUTES,
    )
    while True:
        try:
            ran = await process_queue_once()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Precompute queue poll cycle failed")
            ran = False
        if not ran:
            await asyncio.sleep(POLL_INTERVAL_SECONDS)


async def get_job(job_id: int) -> Optional[dict[str, Any]]:
    """Fetch one job row for observability endpoints and tests."""
    return await pg_query_one(
        """
        SELECT id, source, dedupe_key, start_date::text, end_date::text,
               include_legacy_performance, run_validation, status, attempts,
               claimed_by, error_text, result, enqueued_at, started_at,
               heartbeat_at, finished_at
        FROM precompute_jobs
        WHERE id = %s
        """,
        (job_id,),
    )
