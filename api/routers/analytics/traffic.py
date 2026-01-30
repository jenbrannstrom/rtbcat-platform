"""Traffic Import Router.

Handles RTB traffic data import and mock traffic generation endpoints.
"""

import csv
import io
import logging
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, Depends

from .common import ImportTrafficResponse
from api.dependencies import get_store, get_current_user, resolve_buyer_id, get_allowed_buyer_ids
from storage import SQLiteStore
from storage.postgres_store import PostgresStore

# Store type can be either SQLite or Postgres
StoreType = Union[SQLiteStore, PostgresStore]
from storage.repositories.user_repository import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Traffic Import"])


@router.post("/analytics/import-traffic", response_model=ImportTrafficResponse)
async def import_traffic_data(
    file: UploadFile = File(..., description="CSV file with traffic data"),
    store: StoreType = Depends(get_store),
    user: User = Depends(get_current_user),
):
    """Import RTB traffic data from CSV file.

    The CSV file should have the following columns:
    - **canonical_size**: Normalized size category (e.g., "300x250 (Medium Rectangle)")
    - **raw_size**: Original requested size (e.g., "300x250")
    - **request_count**: Number of bid requests
    - **date**: Date in YYYY-MM-DD format
    - **buyer_id** (optional): Buyer seat ID

    Example CSV:
    ```
    canonical_size,raw_size,request_count,date,buyer_id
    "300x250 (Medium Rectangle)",300x250,50000,2024-01-15,456
    "Non-Standard (320x481)",320x481,12000,2024-01-15,456
    ```
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    try:
        # Read and parse CSV
        contents = await file.read()
        text = contents.decode("utf-8")
        reader = csv.DictReader(io.StringIO(text))

        # Validate required columns
        required_columns = {"canonical_size", "raw_size", "request_count", "date"}
        if reader.fieldnames is None:
            raise HTTPException(status_code=400, detail="CSV file is empty or malformed")

        missing = required_columns - set(reader.fieldnames)
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"CSV missing required columns: {', '.join(missing)}",
            )

        allowed_buyer_ids = await get_allowed_buyer_ids(store=store, user=user)
        if allowed_buyer_ids is not None and not allowed_buyer_ids:
            raise HTTPException(status_code=403, detail="No buyer accounts assigned.")

        # Parse records
        records = []
        for row in reader:
            try:
                buyer_id = row.get("buyer_id") or None
                if allowed_buyer_ids is not None:
                    if buyer_id is None:
                        if len(allowed_buyer_ids) == 1:
                            buyer_id = allowed_buyer_ids[0]
                        else:
                            raise HTTPException(
                                status_code=400,
                                detail="buyer_id is required for your account access.",
                            )
                    elif buyer_id not in allowed_buyer_ids:
                        raise HTTPException(
                            status_code=403,
                            detail="You don't have access to this buyer account.",
                        )
                records.append(
                    {
                        "canonical_size": row["canonical_size"],
                        "raw_size": row["raw_size"],
                        "request_count": int(row["request_count"]),
                        "date": row["date"],
                        "buyer_id": buyer_id,
                    }
                )
            except (ValueError, KeyError) as e:
                logger.warning(f"Skipping invalid row: {row}, error: {e}")
                continue

        if not records:
            raise HTTPException(status_code=400, detail="No valid records found in CSV")

        # Store traffic data - use db_execute for inserts
        from storage.database import db_execute
        count = 0
        for r in records:
            await db_execute(
                """INSERT OR REPLACE INTO rtb_traffic
                (canonical_size, raw_size, request_count, traffic_date, buyer_id)
                VALUES (?, ?, ?, ?, ?)""",
                (r["canonical_size"], r["raw_size"], r["request_count"], r["date"], r["buyer_id"])
            )
            count += 1

        return ImportTrafficResponse(
            status="completed",
            records_imported=count,
            message=f"Successfully imported {count} traffic records.",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Traffic import failed: {e}")
        raise HTTPException(status_code=500, detail=f"Traffic import failed: {str(e)}")


@router.post("/analytics/generate-mock-traffic", response_model=ImportTrafficResponse)
async def generate_mock_traffic_endpoint(
    days: int = Query(7, ge=1, le=30, description="Days of traffic to generate"),
    buyer_id: Optional[str] = Query(None, description="Buyer ID to associate"),
    base_daily_requests: int = Query(100000, ge=1000, le=1000000, description="Base daily request volume"),
    waste_bias: float = Query(0.3, ge=0.0, le=1.0, description="Bias towards waste traffic (0-1)"),
    store: StoreType = Depends(get_store),
    user: User = Depends(get_current_user),
):
    """Generate mock RTB traffic data for testing and demos.

    Creates synthetic bid request data with realistic distributions including:
    - IAB standard sizes (high volume)
    - Non-standard sizes (configurable waste)
    - Video sizes
    - Day-over-day variance

    Use `waste_bias` to control how much non-standard (waste) traffic is generated:
    - 0.0 = minimal waste, mostly standard sizes
    - 0.5 = balanced mix
    - 1.0 = heavy waste traffic
    """
    from analytics import generate_mock_traffic
    from storage.database import db_execute

    try:
        buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
        # Generate mock traffic
        traffic_records = generate_mock_traffic(
            days=days,
            buyer_id=buyer_id,
            base_daily_requests=base_daily_requests,
            waste_bias=waste_bias,
        )

        # Store traffic data
        count = 0
        for r in traffic_records:
            await db_execute(
                """INSERT OR REPLACE INTO rtb_traffic
                (canonical_size, raw_size, request_count, traffic_date, buyer_id)
                VALUES (?, ?, ?, ?, ?)""",
                (r.canonical_size, r.raw_size, r.request_count, r.date, r.buyer_id)
            )
            count += 1

        return ImportTrafficResponse(
            status="completed",
            records_imported=count,
            message=f"Generated and imported {count} mock traffic records for {days} days.",
        )

    except Exception as e:
        logger.error(f"Mock traffic generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Mock traffic generation failed: {str(e)}")
