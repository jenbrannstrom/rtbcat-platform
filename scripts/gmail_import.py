#!/usr/bin/env python3
"""
Gmail Auto-Import for Cat-Scan
Downloads scheduled reports from Google Authorized Buyers emails.
Handles both:
  - Large reports (>=10MB): Download from GCS URL in email body
  - Small reports (<10MB): Extract CSV attachment from email

Features:
  - Optionally archives imported CSVs to S3 with gzip compression
  - Tracks import status in ~/.catscan/gmail_import_status.json
"""

import os
import re
import sys
import json
import gzip
import base64
import html
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
import uuid
import time

# Add parent directory for imports when running as script
sys.path.insert(0, str(Path(__file__).parent.parent))

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Optional: GCS client for service account authenticated downloads
try:
    from google.cloud import storage as gcs_storage
    HAS_GCS_CLIENT = True
except ImportError:
    HAS_GCS_CLIENT = False

# Configuration
# gmail.modify: read emails + mark as read after import
# devstorage.read_only: download reports from GCS (buyside-scheduled-report-export bucket)
SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/devstorage.read_only',
]
CATSCAN_DIR = Path.home() / '.catscan'
CREDENTIALS_DIR = CATSCAN_DIR / 'credentials'
IMPORTS_DIR = CATSCAN_DIR / 'imports'
LOGS_DIR = CATSCAN_DIR / 'logs'
DB_PATH = None  # Legacy SQLite removed — import tracking is in Postgres import_history
TOKEN_PATH = CREDENTIALS_DIR / 'gmail-token.json'
CLIENT_SECRET_PATH = CREDENTIALS_DIR / 'gmail-oauth-client.json'
STATUS_PATH = CATSCAN_DIR / 'gmail_import_status.json'
LOCK_PATH = CATSCAN_DIR / 'gmail_import.lock'
LOCK_STALE_SECONDS = 6 * 60 * 60

# S3 Archive Configuration (disabled by default)
S3_BUCKET = os.environ.get('CATSCAN_S3_BUCKET', '')
S3_REGION = os.environ.get('CATSCAN_S3_REGION', 'eu-central-1')
S3_ARCHIVE_ENABLED = os.environ.get('CATSCAN_S3_ARCHIVE', 'false').lower() == 'true'
GMAIL_LABEL = os.environ.get('CATSCAN_GMAIL_LABEL', '').strip()
GMAIL_QUERY = os.environ.get('CATSCAN_GMAIL_QUERY', '').strip()
INCLUDE_READ = os.environ.get('CATSCAN_GMAIL_INCLUDE_READ', 'false').lower() == 'true'
SEAT_ID_ALLOWLIST = {
    seat_id.strip()
    for seat_id in os.environ.get('CATSCAN_GMAIL_SEAT_IDS', '').split(',')
    if seat_id.strip()
}

# Pipeline integration - run after successful CSV import
PIPELINE_ENABLED = os.environ.get("CATSCAN_PIPELINE_ENABLED", "false").lower() == "true"

def run_pipeline_for_file(filepath: Path, seat_id: Optional[str], verbose: bool = True) -> bool:
    """Run the data pipeline for an imported CSV file.
    
    This exports the CSV to Parquet, loads to BigQuery, and aggregates to Postgres.
    Only runs if CATSCAN_PIPELINE_ENABLED=true environment variable is set.
    """
    if not PIPELINE_ENABLED:
        return True  # Skip silently if not enabled
    
    try:
        from scripts.run_pipeline import run_pipeline
        
        # Extract date from CSV content
        metric_date = None
        try:
            import csv as csv_module
            with open(filepath, "r", encoding="utf-8-sig") as f:
                reader = csv_module.reader(f)
                headers = next(reader)
                date_col_idx = None
                for i, h in enumerate(headers):
                    if h.strip() in ("#Day", "Day", "Date"):
                        date_col_idx = i
                        break
                if date_col_idx is not None:
                    first_row = next(reader)
                    date_val = first_row[date_col_idx].strip()
                    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
                        try:
                            metric_date = datetime.strptime(date_val, fmt).date().isoformat()
                            break
                        except ValueError:
                            continue
        except Exception:
            pass
        
        if not metric_date:
            from datetime import date as date_type
            metric_date = date_type.today().isoformat()
        
        buyer_id = seat_id or "unknown"
        
        if verbose:
            print(f"  Running pipeline for {filepath.name}...")
        
        result = run_pipeline(
            csv_path=str(filepath),
            buyer_id=buyer_id,
            metric_date=metric_date,
        )
        
        if result.get("success"):
            if verbose:
                print("  Pipeline completed successfully")
            return True
        else:
            if verbose:
                errors = result.get("errors", [])
                print(f"  Pipeline errors: {errors}")
            return False
            
    except ImportError as e:
        if verbose:
            print(f"  Pipeline not available: {e}")
        return False
    except Exception as e:
        if verbose:
            print(f"  Pipeline error: {e}")
        return False

# Create directories
IMPORTS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)


def load_status() -> Dict[str, Any]:
    """Load the import status from disk."""
    if STATUS_PATH.exists():
        try:
            return json.loads(STATUS_PATH.read_text())
        except json.JSONDecodeError:
            pass
    return {
        "last_run": None,
        "last_success": None,
        "last_error": None,
        "total_imports": 0,
        "history": [],
        "running": False,
        "current_job_id": None,
    }


def _is_lock_active() -> bool:
    if not LOCK_PATH.exists():
        return False
    try:
        return (time.time() - LOCK_PATH.stat().st_mtime) <= LOCK_STALE_SECONDS
    except Exception:
        return False


def save_status(status: Dict[str, Any]):
    """Save the import status to disk."""
    STATUS_PATH.write_text(json.dumps(status, indent=2, default=str))


def update_status(
    success: bool,
    files_imported: int = 0,
    error: Optional[str] = None,
    emails_processed: int = 0,
    running: bool = False,
    current_job_id: Optional[str] = None,
):
    """Update the import status after a run."""
    status = load_status()
    now = datetime.now().isoformat()

    status["last_run"] = now
    if success:
        status["last_success"] = now
        status["last_error"] = None
    else:
        status["last_error"] = error

    status["total_imports"] += files_imported
    status["running"] = running
    status["current_job_id"] = current_job_id

    # Keep last 50 history entries
    status["history"].insert(0, {
        "timestamp": now,
        "success": success,
        "files_imported": files_imported,
        "emails_processed": emails_processed,
        "error": error
    })
    status["history"] = status["history"][:50]

    save_status(status)


def get_status() -> Dict[str, Any]:
    """Get the current import status (for API endpoint)."""
    status = load_status()
    running = _is_lock_active()
    return {
        "configured": CLIENT_SECRET_PATH.exists(),
        "authorized": TOKEN_PATH.exists(),
        "last_run": status.get("last_run"),
        "last_success": status.get("last_success"),
        "last_error": status.get("last_error"),
        "total_imports": status.get("total_imports", 0),
        "recent_history": status.get("history", [])[:10],
        "running": running,
        "current_job_id": status.get("current_job_id"),
    }


def detect_report_type(filepath: Path) -> str:
    """
    Detect the report type from the CSV filename or content.

    Returns one of: 'performance', 'funnel-geo', 'funnel-publishers'
    """
    filename_lower = filepath.name.lower()

    # Check filename patterns
    if 'funnel' in filename_lower and 'geo' in filename_lower:
        return 'funnel-geo'
    elif 'funnel' in filename_lower and 'pub' in filename_lower:
        return 'funnel-publishers'
    elif 'performance' in filename_lower or 'rtb' in filename_lower:
        return 'performance'

    # Default to performance if can't determine
    try:
        with open(filepath, 'r') as f:
            header = f.readline().lower()
            if 'country' in header or 'region' in header:
                return 'funnel-geo'
            elif 'publisher' in header or 'domain' in header:
                return 'funnel-publishers'
    except Exception:
        pass

    return 'performance'


def detect_report_kind(filename: str) -> str:
    """Return the canonical report kind name from filename."""
    name = filename.lower()
    if "catscan-bid-filtering" in name:
        return "catscan-bid-filtering"
    if "catscan-bidsinauction" in name:
        return "catscan-bidsinauction"
    if "catscan-pipeline-geo" in name:
        return "catscan-pipeline-geo"
    if "catscan-pipeline" in name:
        return "catscan-pipeline"
    if "catscan-quality" in name:
        return "catscan-quality"
    return "unknown"


def extract_report_date(filename: str) -> Optional[str]:
    """Extract report date as YYYY-MM-DD from filename."""
    match = re.search(r"(20\\d{6})", filename)
    if not match:
        return None
    raw = match.group(1)
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"


def _get_sync_connection():
    """Get a sync psycopg connection for gmail import tracking."""
    import psycopg
    from psycopg.rows import dict_row

    dsn = (
        os.getenv("POSTGRES_SERVING_DSN")
        or os.getenv("POSTGRES_DSN")
        or os.getenv("DATABASE_URL")
        or ""
    )
    if not dsn:
        return None
    return psycopg.connect(dsn, row_factory=dict_row)


def record_import_run(
    *,
    seat_id: Optional[str],
    report_kind: str,
    filename: str,
    success: bool,
    rows_imported: int = 0,
    rows_duplicate: int = 0,
    rows_read: int = 0,
    file_size_bytes: int = 0,
    batch_id: Optional[str] = None,
    date_range_start: Optional[str] = None,
    date_range_end: Optional[str] = None,
    columns_found: Optional[str] = None,
    error: Optional[str] = None,
) -> None:
    """Record import run in ingestion_runs and import_history.

    Uses sync psycopg in a single transaction. buyer_id is set from seat_id
    (explicit, not filename-parsed). Inserts ingestion_runs as 'running'
    then immediately updates to final status — import completes before
    recording, so this is intentional.
    """
    conn = _get_sync_connection()
    if conn is None:
        return
    try:
        run_id = str(uuid.uuid4())
        status = "success" if success else "failed"
        with conn:
            conn.execute(
                """INSERT INTO ingestion_runs
                   (run_id, source_type, buyer_id, bidder_id, status,
                    report_type, filename, row_count, error_summary)
                   VALUES (%s, 'csv', %s, %s, 'running', %s, %s, 0, NULL)""",
                (run_id, seat_id, seat_id, report_kind, filename),
            )
            conn.execute(
                """UPDATE ingestion_runs
                   SET status = %s, row_count = %s, error_summary = %s,
                       finished_at = CURRENT_TIMESTAMP
                   WHERE run_id = %s AND finished_at IS NULL""",
                (status, rows_imported, error, run_id),
            )
            if batch_id:
                conn.execute(
                    """INSERT INTO import_history
                       (batch_id, filename, rows_read, rows_imported,
                        rows_skipped, rows_duplicate, date_range_start,
                        date_range_end, columns_found, status,
                        error_message, file_size_bytes, buyer_id, bidder_id)
                       VALUES (%s,%s,%s,%s,0,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        batch_id, filename, rows_read, rows_imported,
                        rows_duplicate, date_range_start, date_range_end,
                        columns_found,
                        "complete" if success else "failed",
                        error, file_size_bytes, seat_id, seat_id,
                    ),
                )
    except Exception as exc:
        print(f"  Warning: failed to record import run: {exc}")
    finally:
        conn.close()


def archive_to_s3(filepath: Path, report_type: Optional[str] = None, verbose: bool = True) -> Optional[str]:
    """
    Archive CSV to S3 with gzip compression.

    Args:
        filepath: Local path to CSV file
        report_type: One of 'performance', 'funnel-geo', 'funnel-publishers'.
                     If None, will auto-detect from filename/content.

    Returns:
        S3 URI of archived file, or None if archival failed/disabled
    """
    if not S3_ARCHIVE_ENABLED:
        if verbose:
            print("  S3 archival disabled, skipping...")
        return None
    if not S3_BUCKET:
        if verbose:
            print("  S3 bucket not configured, skipping archival")
        return None

    if report_type is None:
        report_type = detect_report_type(filepath)

    # Extract date from filename or use today
    date_match = re.search(r'(\d{4})[-_]?(\d{2})[-_]?(\d{2})', filepath.name)
    if date_match:
        year, month, day = date_match.groups()
    else:
        today = datetime.now()
        year, month, day = today.strftime('%Y'), today.strftime('%m'), today.strftime('%d')

    # Build S3 key with date-based structure
    s3_filename = f"catscan-{report_type}-{year}-{month}-{day}.csv.gz"
    s3_key = f"{report_type}/{year}/{month}/{day}/{s3_filename}"

    try:
        # Create S3 client (uses IAM role on EC2, or local credentials)
        s3_client = boto3.client('s3', region_name=S3_REGION)

        # Compress and upload
        compressed_path = filepath.with_suffix('.csv.gz')
        with open(filepath, 'rb') as f_in:
            with gzip.open(compressed_path, 'wb') as f_out:
                f_out.writelines(f_in)

        # Upload to S3
        s3_client.upload_file(str(compressed_path), S3_BUCKET, s3_key)

        # Clean up local compressed file
        compressed_path.unlink()

        s3_uri = f"s3://{S3_BUCKET}/{s3_key}"
        if verbose:
            print(f"  Archived to S3: {s3_uri}")

        return s3_uri

    except NoCredentialsError:
        if verbose:
            print("  Warning: No AWS credentials found, skipping S3 archival")
        return None
    except ClientError as e:
        if verbose:
            print(f"  Warning: S3 upload failed: {e}")
        return None
    except Exception as e:
        if verbose:
            print(f"  Warning: S3 archival error: {e}")
        return None


def get_gmail_service():
    """Authenticate and return Gmail API service and credentials.

    Returns:
        tuple: (Gmail API service, OAuth credentials)
    """
    creds = None

    # Load existing token (don't enforce scopes - token may have extra scopes)
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH))

    # Refresh or get new token
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CLIENT_SECRET_PATH.exists():
                raise FileNotFoundError(
                    f"Gmail OAuth client not found at {CLIENT_SECRET_PATH}\n"
                    "Download from Google Cloud Console -> APIs & Services -> Credentials"
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_PATH), SCOPES)
            creds = flow.run_local_server(port=0)

        # Save token for next run
        TOKEN_PATH.write_text(creds.to_json())

    return build('gmail', 'v1', credentials=creds), creds


def find_report_emails(service):
    """Find all unread emails from Google Authorized Buyers (with pagination)."""
    if GMAIL_QUERY:
        query = GMAIL_QUERY
    else:
        query_parts = [
            'from:noreply-google-display-ads-managed-reports@google.com',
        ]
        if not INCLUDE_READ:
            query_parts.append('is:unread')
        if GMAIL_LABEL:
            query_parts.append(f"label:{GMAIL_LABEL}")
        query = " ".join(query_parts)

    all_messages = []
    page_token = None

    while True:
        results = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=100,
            pageToken=page_token
        ).execute()

        messages = results.get('messages', [])
        all_messages.extend(messages)

        page_token = results.get('nextPageToken')
        if not page_token:
            break

    return all_messages


def extract_download_url(body: str) -> Optional[str]:
    """Extract the GCS download URL from email body."""
    body = html.unescape(body)
    pattern = (
        r"https://storage\.cloud\.google\.com/"
        r"buyside-scheduled-report-export/[^\s\"'>]+"
    )
    match = re.search(pattern, body)
    return match.group(0) if match else None


def get_email_body(payload: Dict) -> str:
    """Extract plain text body from email payload."""
    body = ''

    if 'parts' in payload:
        for part in payload['parts']:
            if part.get('mimeType') == 'text/plain':
                data = part.get('body', {}).get('data', '')
                if data:
                    body = base64.urlsafe_b64decode(data).decode('utf-8')
                    break
            # Recurse into nested parts
            if 'parts' in part:
                body = get_email_body(part)
                if body:
                    break
    else:
        data = payload.get('body', {}).get('data', '')
        if data:
            body = base64.urlsafe_b64decode(data).decode('utf-8')

    return body


def get_email_subject(payload: Dict) -> str:
    """Extract the subject from the email payload headers."""
    for header in payload.get("headers", []):
        if header.get("name", "").lower() == "subject":
            return header.get("value", "")
    return ""


def extract_seat_id(subject: str) -> Optional[str]:
    """Extract seat ID from report subject lines."""
    if not subject:
        return None

    match = re.search(r"catscan-[a-z-]+-(\d{6,})-", subject.lower())
    if match:
        return match.group(1)

    fallback = re.search(r"\b\d{6,}\b", subject)
    return fallback.group(0) if fallback else None


def extract_attachments(service, message_id: str, payload: Dict) -> List[Path]:
    """Extract CSV attachments from email (for reports < 10MB)."""
    attachments = []

    def find_attachments(parts):
        for part in parts:
            filename = part.get('filename', '')
            if filename.endswith('.csv'):
                attachment_id = part.get('body', {}).get('attachmentId')
                if attachment_id:
                    attachments.append({
                        'filename': filename,
                        'attachment_id': attachment_id
                    })
            # Recurse into nested parts
            if 'parts' in part:
                find_attachments(part['parts'])

    if 'parts' in payload:
        find_attachments(payload['parts'])

    # Download each attachment
    downloaded_files = []
    for att in attachments:
        attachment = service.users().messages().attachments().get(
            userId='me',
            messageId=message_id,
            id=att['attachment_id']
        ).execute()

        data = attachment.get('data', '')
        if data:
            file_data = base64.urlsafe_b64decode(data)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            # Use original filename but add timestamp
            safe_filename = re.sub(r'[^\w\-.]', '_', att['filename'])
            filepath = IMPORTS_DIR / f"{timestamp}_{safe_filename}"
            filepath.write_bytes(file_data)
            downloaded_files.append(filepath)
            print(f"  Extracted attachment: {filepath.name}")

    return downloaded_files


def parse_gcs_url(url: str) -> tuple[Optional[str], Optional[str]]:
    """Parse bucket and object name from a GCS URL.

    Handles URLs like:
    - https://storage.cloud.google.com/bucket-name/object-path
    - https://storage.googleapis.com/bucket-name/object-path

    Returns:
        Tuple of (bucket_name, object_name) or (None, None) if not a valid GCS URL
    """
    parsed = urllib.parse.urlparse(url)
    if parsed.netloc not in ('storage.cloud.google.com', 'storage.googleapis.com'):
        return None, None

    # Path is /bucket-name/object-path
    path_parts = parsed.path.strip('/').split('/', 1)
    if len(path_parts) < 2:
        return None, None

    return path_parts[0], path_parts[1]


def download_via_gcs_client(bucket_name: str, object_name: str, filepath: Path) -> bool:
    """Download a file from GCS using the google-cloud-storage client.

    Uses service account credentials from GOOGLE_APPLICATION_CREDENTIALS env var.

    Returns:
        True if download succeeded, False if failed (caller should try fallback)
    """
    if not HAS_GCS_CLIENT:
        print("  GCS client not available, skipping service account download", flush=True)
        return False

    creds_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    if not creds_path:
        print("  GOOGLE_APPLICATION_CREDENTIALS not set, skipping service account download", flush=True)
        return False

    try:
        client = gcs_storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(object_name)

        print(f"  Attempting GCS client download (service account)...", flush=True)
        blob.download_to_filename(str(filepath))
        print(f"  GCS client download succeeded", flush=True)
        return True

    except Exception as e:
        error_msg = str(e)
        if 'does not have storage.objects.get access' in error_msg:
            print(f"  GCS client failed: Service account lacks storage.objects.get permission on bucket '{bucket_name}'", flush=True)
        elif '403' in error_msg or 'Forbidden' in error_msg:
            print(f"  GCS client failed: Access denied to bucket '{bucket_name}' - check IAM permissions", flush=True)
        elif '404' in error_msg or 'Not Found' in error_msg:
            print(f"  GCS client failed: Object not found (may be expired)", flush=True)
        else:
            print(f"  GCS client failed: {error_msg[:100]}", flush=True)

        # Clean up partial file if it exists
        if filepath.exists():
            filepath.unlink()
        return False


def download_from_url(url: str, message_id: str, access_token: str = None, seat_id: str = None) -> List[Path]:
    """Download CSV from GCS URL (for reports >= 10MB).

    Authentication methods (tried in order):
    1. GCS client with service account (GOOGLE_APPLICATION_CREDENTIALS env var)
       - Requires storage.objects.get IAM permission on the bucket
    2. OAuth access token (Bearer token in Authorization header)
    3. Pre-signed URL (no auth needed if URL contains signature params)

    Includes retry with exponential backoff for transient errors.
    """
    import requests

    # Retry configuration
    MAX_RETRIES = 3
    BACKOFF_BASE = 2  # seconds
    TIMEOUT = 120  # seconds
    RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    # Include seat_id in filename so the importer can identify the account
    if seat_id:
        filename = f"catscan-report-{seat_id}-{timestamp}.csv"
    else:
        filename = f"report_{timestamp}_{message_id[:8]}.csv"
    filepath = IMPORTS_DIR / filename

    print(f"  Downloading from URL: {url[:60]}...", flush=True)

    # Parse URL to check for signed parameters and extract bucket/object
    parsed_url = urllib.parse.urlparse(url)
    is_signed = any(
        key in parsed_url.query
        for key in ("X-Goog-Signature", "GoogleAccessId", "X-Goog-Algorithm")
    )

    # Try GCS client with service account first (for non-signed URLs)
    if not is_signed:
        bucket_name, object_name = parse_gcs_url(url)
        if bucket_name and object_name:
            if download_via_gcs_client(bucket_name, object_name, filepath):
                # GCS client download succeeded - verify and return
                with open(filepath, 'r') as f:
                    first_line = f.readline()
                    if not first_line or '\x00' in first_line or first_line.startswith('<!doctype'):
                        filepath.unlink()
                        raise ValueError("Downloaded file doesn't appear to be a valid CSV")
                print(f"  Saved: {filepath.name}", flush=True)
                return [filepath]
            # GCS client failed, continue to fallback methods

    # Convert browser URL to API URL for fallback methods
    # https://storage.cloud.google.com/bucket/object -> https://storage.googleapis.com/bucket/object
    api_url = url.replace('storage.cloud.google.com', 'storage.googleapis.com', 1)

    # Prepare headers for fallback download
    headers = {}
    if not is_signed:
        if access_token:
            headers = {'Authorization': f'Bearer {access_token}'}
        else:
            raise ValueError("GCS download failed: Service account download failed and no OAuth access token available. "
                           "Ensure GOOGLE_APPLICATION_CREDENTIALS is set and the service account has "
                           "storage.objects.get permission on the bucket.")

    # Download with retry
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            with requests.get(api_url, headers=headers, stream=True, timeout=TIMEOUT) as response:
                if response.status_code == 200:
                    # Success - write to file
                    with open(filepath, "wb") as f:
                        for chunk in response.iter_content(chunk_size=1024 * 1024):
                            if chunk:
                                f.write(chunk)
                    break  # Success, exit retry loop
                elif response.status_code in RETRYABLE_STATUS_CODES:
                    # Retryable error - clean up partial file
                    if filepath.exists():
                        filepath.unlink()
                    last_error = f"HTTP {response.status_code}"
                    if attempt < MAX_RETRIES - 1:
                        sleep_time = BACKOFF_BASE * (2 ** attempt)
                        print(f"  Retry {attempt + 1}/{MAX_RETRIES} after {sleep_time}s ({last_error})", flush=True)
                        time.sleep(sleep_time)
                        continue
                    else:
                        raise ValueError(f"GCS download failed after {MAX_RETRIES} retries: {last_error}")
                else:
                    # Non-retryable error (4xx except 429) - fail fast, clean up
                    if filepath.exists():
                        filepath.unlink()
                    raise ValueError(f"GCS download failed: {response.status_code} - {response.text[:200]}")

        except requests.exceptions.Timeout as e:
            # Clean up partial file on timeout
            if filepath.exists():
                filepath.unlink()
            last_error = f"Timeout after {TIMEOUT}s"
            if attempt < MAX_RETRIES - 1:
                sleep_time = BACKOFF_BASE * (2 ** attempt)
                print(f"  Retry {attempt + 1}/{MAX_RETRIES} after {sleep_time}s ({last_error})", flush=True)
                time.sleep(sleep_time)
                continue
            else:
                raise ValueError(f"GCS download failed after {MAX_RETRIES} retries: {last_error}") from e

        except requests.exceptions.RequestException as e:
            # Clean up partial file on request error
            if filepath.exists():
                filepath.unlink()
            last_error = str(e)
            if attempt < MAX_RETRIES - 1:
                sleep_time = BACKOFF_BASE * (2 ** attempt)
                print(f"  Retry {attempt + 1}/{MAX_RETRIES} after {sleep_time}s ({last_error})", flush=True)
                time.sleep(sleep_time)
                continue
            else:
                raise ValueError(f"GCS download failed after {MAX_RETRIES} retries: {last_error}") from e

    # Verify it's a valid CSV
    with open(filepath, 'r') as f:
        first_line = f.readline()
        if not first_line or '\x00' in first_line or first_line.startswith('<!doctype'):
            filepath.unlink()  # Delete invalid file
            raise ValueError("Downloaded file doesn't appear to be a valid CSV")

    print(f"  Saved: {filepath.name}", flush=True)
    return [filepath]


def mark_as_read(service, message_id: str):
    """Mark email as read after processing."""
    service.users().messages().modify(
        userId='me',
        id=message_id,
        body={'removeLabelIds': ['UNREAD']}
    ).execute()


@dataclass
class CatscanImportResult:
    """Result from import_to_catscan with full metadata for observability."""
    success: bool = False
    report_type: str = ""
    rows_imported: int = 0
    rows_duplicate: int = 0
    error: Optional[str] = None
    rows_read: int = 0
    batch_id: str = ""
    date_range_start: Optional[str] = None
    date_range_end: Optional[str] = None
    columns_found: Optional[str] = None
    file_size_bytes: int = 0


def import_to_catscan(filepath: Path) -> CatscanImportResult:
    """
    Import the CSV into Cat-Scan database directly using the unified importer.
    Returns CatscanImportResult with full metadata for observability.
    """
    file_size = filepath.stat().st_size if filepath.exists() else 0
    try:
        from importers.unified_importer import unified_import

        result = unified_import(str(filepath))
        columns_str = ",".join(result.columns_mapped.values()) if result.columns_mapped else None

        if result.success:
            print(f"  Imported: {result.rows_imported} rows ({result.report_type})")
        else:
            print(f"  Import failed: {result.error_message}")

        return CatscanImportResult(
            success=result.success,
            report_type=result.report_type,
            rows_imported=result.rows_imported,
            rows_duplicate=result.rows_duplicate,
            error=result.error_message or None,
            rows_read=result.rows_read,
            batch_id=result.batch_id,
            date_range_start=result.date_range_start,
            date_range_end=result.date_range_end,
            columns_found=columns_str,
            file_size_bytes=file_size,
        )
    except ImportError:
        # Fall back to HTTP API if running standalone
        import requests
        try:
            with open(filepath, 'rb') as f:
                response = requests.post(
                    'http://localhost:8000/performance/import-csv',
                    files={'file': (filepath.name, f, 'text/csv')}
                )
            if response.status_code == 200:
                data = response.json()
                print(f"  Imported: {data.get('rows_imported', 0)} rows")
                return CatscanImportResult(
                    success=True,
                    report_type="api_import",
                    rows_imported=data.get("rows_imported", 0),
                    rows_duplicate=data.get("rows_duplicate", 0),
                    batch_id=data.get("batch_id", ""),
                    file_size_bytes=file_size,
                )
            else:
                print(f"  Import failed: {response.text}")
                return CatscanImportResult(
                    report_type="api_import", error=response.text,
                    file_size_bytes=file_size,
                )
        except requests.exceptions.ConnectionError:
            print(f"  Warning: Cat-Scan API not running. File saved to {filepath}")
            return CatscanImportResult(
                report_type="api_import", error="API not running",
                file_size_bytes=file_size,
            )
    except Exception as e:
        print(f"  Import error: {e}")
        return CatscanImportResult(
            report_type="import_error", error=str(e),
            file_size_bytes=file_size,
        )


def process_message(
    service,
    message_id: str,
    access_token: str = None,
    allowed_seat_ids: Optional[set[str]] = None,
) -> tuple[List[Path], Optional[str], str, bool]:
    """Process a single email - extract attachment OR download from URL.

    Args:
        service: Gmail API service
        message_id: Email message ID
        access_token: OAuth access token for authenticated GCS downloads
    """
    message = service.users().messages().get(
        userId='me',
        id=message_id,
        format='full'
    ).execute()

    payload = message.get('payload', {})
    subject = get_email_subject(payload)
    seat_id = extract_seat_id(subject)
    if allowed_seat_ids:
        if not seat_id or seat_id not in allowed_seat_ids:
            return [], seat_id, subject, True
    downloaded_files = []

    # First, try GCS URL download (always has latest report template).
    # Google RTB emails may include an older cached attachment AND a GCS link
    # pointing to the freshly-generated report.  The GCS version reflects
    # template changes (e.g. added Country column) while the attachment may not.
    body = get_email_body(payload)
    if not body:
        body = message.get('snippet', '')
    url = extract_download_url(body)
    if url:
        try:
            downloaded_files = download_from_url(url, message_id, access_token, seat_id)
        except Exception as e:
            print(f"  GCS download failed ({e}), falling back to attachment", flush=True)

    # Fall back to email attachment if GCS download unavailable or failed
    if not downloaded_files:
        downloaded_files = extract_attachments(service, message_id, payload)

    return downloaded_files, seat_id, subject, False


def _lock_is_stale() -> bool:
    if not LOCK_PATH.exists():
        return False
    try:
        data = json.loads(LOCK_PATH.read_text())
        started_at = data.get("started_at")
        if started_at:
            started_time = datetime.fromisoformat(started_at)
            return (datetime.now() - started_time).total_seconds() > LOCK_STALE_SECONDS
    except Exception:
        pass
    try:
        return (time.time() - LOCK_PATH.stat().st_mtime) > LOCK_STALE_SECONDS
    except Exception:
        return False


def _try_acquire_lock(job_id: str) -> bool:
    lock_payload = json.dumps(
        {"pid": os.getpid(), "job_id": job_id, "started_at": datetime.now().isoformat()}
    )
    try:
        fd = os.open(str(LOCK_PATH), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w") as lock_file:
            lock_file.write(lock_payload)
        return True
    except FileExistsError:
        return False


def acquire_lock(job_id: str) -> bool:
    """Acquire a lock for a Gmail import run."""
    if _try_acquire_lock(job_id):
        return True
    if _lock_is_stale():
        try:
            LOCK_PATH.unlink()
        except FileNotFoundError:
            pass
        return _try_acquire_lock(job_id)
    return False


def release_lock():
    """Release the Gmail import lock."""
    try:
        LOCK_PATH.unlink()
    except FileNotFoundError:
        pass


def run_import(verbose: bool = True, job_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Run the Gmail import process.
    Returns a dict with results for API use.
    """
    result = {
        "success": False,
        "emails_processed": 0,
        "files_imported": 0,
        "emails_skipped": 0,
        "skipped_seat_ids": [],
        "errors": [],
        "files": []
    }
    job_id = job_id or str(datetime.now().timestamp()).replace(".", "")

    if not acquire_lock(job_id):
        error_msg = "Import already running"
        result["errors"].append(error_msg)
        return result

    update_status(False, running=True, current_job_id=job_id)

    try:
        if verbose:
            print("=" * 60)
            print(f"Cat-Scan Gmail Import - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("=" * 60)

        try:
            service, creds = get_gmail_service()
            access_token = creds.token  # For authenticated GCS downloads
        except FileNotFoundError as e:
            error_msg = str(e)
            if verbose:
                print(f"ERROR: {error_msg}")
            result["errors"].append(error_msg)
            update_status(False, error=error_msg, running=False, current_job_id=None)
            return result
        except Exception as e:
            error_msg = f"Gmail authentication failed: {e}"
            if verbose:
                print(f"ERROR: {error_msg}")
            result["errors"].append(error_msg)
            update_status(False, error=error_msg, running=False, current_job_id=None)
            return result

        messages = find_report_emails(service)

        if not messages:
            if verbose:
                print("No new report emails found.")
            result["success"] = True
            update_status(True, files_imported=0, emails_processed=0, running=False, current_job_id=None)
            return result

        if verbose:
            print(f"Found {len(messages)} unread report email(s)\n")

        total_imported = 0

        for msg in messages:
            message_id = msg['id']
            if verbose:
                print(f"Processing email: {message_id}")

            try:
                downloaded_files, seat_id, subject, skipped = process_message(
                    service,
                    message_id,
                    access_token,
                    SEAT_ID_ALLOWLIST or None,
                )
                if skipped:
                    result["emails_skipped"] += 1
                    if seat_id:
                        result["skipped_seat_ids"].append(seat_id)
                    if verbose:
                        print(f"  Skipped seat_id={seat_id or 'unknown'} subject='{subject}'")
                    mark_as_read(service, message_id)
                    continue

                if not downloaded_files:
                    if verbose:
                        print("  No CSV found (attachment or URL)")
                    continue

                result["emails_processed"] += 1

                for filepath in downloaded_files:
                    result["files"].append(str(filepath))

                    # Archive to S3 before importing to database
                    archive_to_s3(filepath, verbose=verbose)

                    imp = import_to_catscan(filepath)
                    report_kind = detect_report_kind(filepath.name)
                    record_import_run(
                        seat_id=seat_id,
                        report_kind=report_kind,
                        filename=filepath.name,
                        success=imp.success,
                        rows_imported=imp.rows_imported,
                        rows_duplicate=imp.rows_duplicate,
                        rows_read=imp.rows_read,
                        file_size_bytes=imp.file_size_bytes,
                        batch_id=imp.batch_id,
                        date_range_start=imp.date_range_start,
                        date_range_end=imp.date_range_end,
                        columns_found=imp.columns_found,
                        error=imp.error,
                    )
                    if imp.success:
                        total_imported += 1
                        # Run pipeline for BigQuery/Postgres
                        run_pipeline_for_file(filepath, seat_id, verbose=verbose)

                mark_as_read(service, message_id)
                if verbose:
                    print("  Marked as read")

            except Exception as e:
                error_msg = f"Error processing {message_id}: {e}"
                if verbose:
                    print(f"  ERROR: {e}")
                result["errors"].append(error_msg)
                continue

            if verbose:
                print()

        result["files_imported"] = total_imported
        result["success"] = True

        if verbose:
            print("=" * 60)
            print(f"Done! Imported {total_imported} file(s) to ~/.catscan/imports/")
            print("=" * 60)

        update_status(
            True,
            files_imported=total_imported,
            emails_processed=result["emails_processed"],
            running=False,
            current_job_id=None,
        )

        if result["skipped_seat_ids"]:
            result["skipped_seat_ids"] = sorted(set(result["skipped_seat_ids"]))

        return result
    except Exception as e:
        error_msg = f"Gmail import failed: {e}"
        if verbose:
            print(f"ERROR: {error_msg}")
        result["errors"].append(error_msg)
        update_status(False, error=error_msg, running=False, current_job_id=None)
        return result
    finally:
        release_lock()


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Import reports from Gmail')
    parser.add_argument('--status', action='store_true', help='Show import status')
    parser.add_argument('--quiet', '-q', action='store_true', help='Suppress output')
    args = parser.parse_args()

    if args.status:
        status = get_status()
        print(json.dumps(status, indent=2))
        return

    result = run_import(verbose=not args.quiet, job_id=None)

    if not result["success"]:
        sys.exit(1)


if __name__ == '__main__':
    main()
