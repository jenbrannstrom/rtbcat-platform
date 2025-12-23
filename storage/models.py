"""Data models for RTBcat Creative Intelligence storage.

This module contains all dataclass definitions used across storage repositories.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Creative:
    """Creative record for database storage.

    Attributes:
        id: Unique creative identifier (from API creativeId).
        name: Full resource name (bidders/{account}/creatives/{id}).
        format: Creative format (HTML, VIDEO, NATIVE, UNKNOWN).
        account_id: Bidder account ID.
        buyer_id: Buyer seat ID (for multi-seat accounts).
        approval_status: Network policy compliance status.
        width: Creative width in pixels (for HTML/native image).
        height: Creative height in pixels (for HTML/native image).
        canonical_size: Normalized IAB standard size (e.g., "300x250 (Medium Rectangle)").
        size_category: Size category ("IAB Standard", "Video", "Adaptive", "Non-Standard").
        final_url: Primary destination URL.
        display_url: Display URL (may differ from final_url).
        utm_source: UTM source parameter.
        utm_medium: UTM medium parameter.
        utm_campaign: UTM campaign parameter.
        utm_content: UTM content parameter.
        utm_term: UTM term parameter.
        advertiser_name: Declared advertiser name.
        campaign_id: Assigned campaign ID (from clustering).
        cluster_id: Assigned cluster ID (from AI clustering).
        raw_data: Full API response and format-specific data as JSON.
        created_at: Record creation timestamp.
        updated_at: Last update timestamp.
    """

    id: str
    name: str
    format: str
    account_id: Optional[str] = None
    buyer_id: Optional[str] = None
    approval_status: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    canonical_size: Optional[str] = None
    size_category: Optional[str] = None
    final_url: Optional[str] = None
    display_url: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    utm_content: Optional[str] = None
    utm_term: Optional[str] = None
    advertiser_name: Optional[str] = None
    campaign_id: Optional[str] = None
    cluster_id: Optional[str] = None
    seat_name: Optional[str] = None
    raw_data: dict = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class Campaign:
    """Campaign record for database storage."""

    id: str
    name: str
    source: str = "google_ads"
    creative_count: int = 0
    metadata: dict = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class Cluster:
    """Cluster record for database storage."""

    id: str
    name: str
    description: Optional[str] = None
    creative_count: int = 0
    centroid: Optional[dict] = None
    created_at: Optional[datetime] = None


@dataclass
class ServiceAccount:
    """Service account record for multi-account support.

    Attributes:
        id: UUID for the service account.
        client_email: Service account email (unique identifier from Google).
        project_id: Google Cloud project ID.
        display_name: User-friendly name for the account.
        credentials_path: Path to the JSON credentials file.
        is_active: Whether the account is active.
        created_at: Record creation timestamp.
        last_used: Timestamp of last API call using this account.
    """

    id: str
    client_email: str
    project_id: Optional[str] = None
    display_name: Optional[str] = None
    credentials_path: str = ""
    is_active: bool = True
    created_at: Optional[datetime] = None
    last_used: Optional[datetime] = None


@dataclass
class BuyerSeat:
    """Buyer seat record for multi-seat account support.

    Attributes:
        buyer_id: Unique buyer account ID (e.g., "456" from buyers/456).
        bidder_id: Parent bidder account ID.
        service_account_id: Foreign key to service_accounts table.
        display_name: Human-readable name for the buyer seat.
        active: Whether the seat is active for syncing.
        creative_count: Number of creatives associated with this seat.
        last_synced: Timestamp of last successful sync.
        created_at: Record creation timestamp.
    """

    buyer_id: str
    bidder_id: str
    service_account_id: Optional[str] = None
    display_name: Optional[str] = None
    active: bool = True
    creative_count: int = 0
    last_synced: Optional[datetime] = None
    created_at: Optional[datetime] = None


@dataclass
class PerformanceMetric:
    """Performance metrics record for daily creative/campaign data.

    Attributes:
        id: Auto-increment primary key.
        creative_id: Foreign key to creatives table.
        campaign_id: Optional campaign association.
        metric_date: Date of the metrics (daily granularity).
        impressions: Number of ad impressions.
        clicks: Number of clicks (must be <= impressions).
        spend_micros: Spend in USD micros (1,000,000 = $1.00).
        cpm_micros: Cost per mille in micros.
        cpc_micros: Cost per click in micros.
        geography: ISO 3166-1 alpha-2 country code.
        device_type: Device category (DESKTOP, MOBILE, TABLET, CTV).
        placement: Publisher domain or app bundle.
        created_at: Record creation timestamp.
        updated_at: Last update timestamp.
    """

    creative_id: str
    metric_date: str  # YYYY-MM-DD format
    impressions: int = 0
    clicks: int = 0
    spend_micros: int = 0
    cpm_micros: Optional[int] = None
    cpc_micros: Optional[int] = None
    campaign_id: Optional[str] = None
    geography: Optional[str] = None
    device_type: Optional[str] = None
    placement: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class ThumbnailStatus:
    """Thumbnail generation status for a creative.

    Attributes:
        creative_id: Creative ID this status is for.
        status: Status string (pending, success, failed, skipped).
        error_reason: Error message if failed.
        video_url: URL of the video being thumbnailed.
        attempted_at: When thumbnail generation was attempted.
    """

    creative_id: str
    status: str
    error_reason: Optional[str] = None
    video_url: Optional[str] = None
    attempted_at: Optional[datetime] = None


@dataclass
class ImportHistory:
    """Import history record for CSV upload tracking.

    Attributes:
        id: Auto-increment primary key.
        batch_id: Unique batch identifier.
        filename: Name of the imported file.
        imported_at: When the import occurred.
        rows_read: Total rows read from file.
        rows_imported: Rows successfully imported.
        rows_skipped: Rows skipped (invalid data).
        rows_duplicate: Rows that were duplicates.
        date_range_start: Earliest date in the data.
        date_range_end: Latest date in the data.
        columns_found: JSON list of columns found.
        columns_missing: JSON list of expected columns missing.
        total_reached: Total reached queries.
        total_impressions: Total impressions.
        total_spend_usd: Total spend in USD.
        status: Import status (complete, partial, failed).
        error_message: Error message if failed.
        file_size_bytes: Size of the imported file.
    """

    batch_id: str
    filename: Optional[str] = None
    imported_at: Optional[datetime] = None
    rows_read: int = 0
    rows_imported: int = 0
    rows_skipped: int = 0
    rows_duplicate: int = 0
    date_range_start: Optional[str] = None
    date_range_end: Optional[str] = None
    columns_found: Optional[str] = None
    columns_missing: Optional[str] = None
    total_reached: int = 0
    total_impressions: int = 0
    total_spend_usd: float = 0.0
    status: str = "complete"
    error_message: Optional[str] = None
    file_size_bytes: int = 0
    id: Optional[int] = None


@dataclass
class DailyUploadSummary:
    """Daily upload summary for upload tracking UI.

    Attributes:
        id: Auto-increment primary key.
        upload_date: Date of uploads.
        total_uploads: Total number of uploads that day.
        successful_uploads: Number of successful uploads.
        failed_uploads: Number of failed uploads.
        total_rows_written: Total rows written across all uploads.
        total_file_size_bytes: Total size of all files.
        avg_rows_per_upload: Average rows per upload.
        min_rows: Minimum rows in a single upload.
        max_rows: Maximum rows in a single upload.
        has_anomaly: Whether anomaly was detected.
        anomaly_reason: Description of the anomaly.
    """

    upload_date: str
    total_uploads: int = 0
    successful_uploads: int = 0
    failed_uploads: int = 0
    total_rows_written: int = 0
    total_file_size_bytes: int = 0
    avg_rows_per_upload: float = 0.0
    min_rows: Optional[int] = None
    max_rows: Optional[int] = None
    has_anomaly: bool = False
    anomaly_reason: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
