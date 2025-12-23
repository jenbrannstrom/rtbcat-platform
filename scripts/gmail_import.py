#!/usr/bin/env python3
"""
Gmail Auto-Import for Cat-Scan
Downloads scheduled reports from Google Authorized Buyers emails.
Handles both:
  - Large reports (>=10MB): Download from GCS URL in email body
  - Small reports (<10MB): Extract CSV attachment from email

Features:
  - Archives all imported CSVs to S3 with gzip compression
  - Tracks import status in ~/.catscan/gmail_import_status.json
"""

import os
import re
import sys
import json
import gzip
import base64
import urllib.request
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

# Add parent directory for imports when running as script
sys.path.insert(0, str(Path(__file__).parent.parent))

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Configuration
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
CATSCAN_DIR = Path.home() / '.catscan'
CREDENTIALS_DIR = CATSCAN_DIR / 'credentials'
IMPORTS_DIR = CATSCAN_DIR / 'imports'
LOGS_DIR = CATSCAN_DIR / 'logs'
TOKEN_PATH = CREDENTIALS_DIR / 'gmail-token.json'
CLIENT_SECRET_PATH = CREDENTIALS_DIR / 'gmail-oauth-client.json'
STATUS_PATH = CATSCAN_DIR / 'gmail_import_status.json'

# S3 Archive Configuration (Frankfurt region)
S3_BUCKET = os.environ.get('CATSCAN_S3_BUCKET', 'rtbcat-csv-archive-frankfurt-328614522524')
S3_REGION = os.environ.get('CATSCAN_S3_REGION', 'eu-central-1')
S3_ARCHIVE_ENABLED = os.environ.get('CATSCAN_S3_ARCHIVE', 'true').lower() == 'true'

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
        "history": []
    }


def save_status(status: Dict[str, Any]):
    """Save the import status to disk."""
    STATUS_PATH.write_text(json.dumps(status, indent=2, default=str))


def update_status(
    success: bool,
    files_imported: int = 0,
    error: Optional[str] = None,
    emails_processed: int = 0
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
    return {
        "configured": CLIENT_SECRET_PATH.exists(),
        "authorized": TOKEN_PATH.exists(),
        "last_run": status.get("last_run"),
        "last_success": status.get("last_success"),
        "last_error": status.get("last_error"),
        "total_imports": status.get("total_imports", 0),
        "recent_history": status.get("history", [])[:10]
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
    """Authenticate and return Gmail API service."""
    creds = None

    # Load existing token
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

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

    return build('gmail', 'v1', credentials=creds)


def find_report_emails(service):
    """Find unread emails from Google Authorized Buyers."""
    query = (
        'from:noreply-google-display-ads-managed-reports@google.com '
        'is:unread'
    )

    results = service.users().messages().list(
        userId='me',
        q=query,
        maxResults=10
    ).execute()

    return results.get('messages', [])


def extract_download_url(body: str) -> Optional[str]:
    """Extract the GCS download URL from email body."""
    pattern = r'https://storage\.cloud\.google\.com/buyside-scheduled-report-export/[\w-]+'
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


def download_from_url(url: str, message_id: str) -> List[Path]:
    """Download CSV from GCS URL (for reports >= 10MB)."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"report_{timestamp}_{message_id[:8]}.csv"
    filepath = IMPORTS_DIR / filename

    print(f"  Downloading from URL: {url[:60]}...")
    urllib.request.urlretrieve(url, filepath)

    # Verify it's a valid CSV
    with open(filepath, 'r') as f:
        first_line = f.readline()
        if not first_line or '\x00' in first_line:
            filepath.unlink()  # Delete invalid file
            raise ValueError("Downloaded file doesn't appear to be a valid CSV")

    print(f"  Saved: {filepath.name}")
    return [filepath]


def mark_as_read(service, message_id: str):
    """Mark email as read after processing."""
    service.users().messages().modify(
        userId='me',
        id=message_id,
        body={'removeLabelIds': ['UNREAD']}
    ).execute()


def import_to_catscan(filepath: Path) -> bool:
    """
    Import the CSV into Cat-Scan database via API.
    Returns True if successful.
    """
    import requests

    try:
        with open(filepath, 'rb') as f:
            response = requests.post(
                'http://localhost:8000/performance/import',
                files={'file': (filepath.name, f, 'text/csv')}
            )

        if response.status_code == 200:
            result = response.json()
            print(f"  Imported: {result.get('imported', 0)} rows")
            return True
        else:
            print(f"  Import failed: {response.text}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"  Warning: Cat-Scan API not running. File saved to {filepath}")
        return False
    except Exception as e:
        print(f"  Import error: {e}")
        return False


def process_message(service, message_id: str) -> List[Path]:
    """Process a single email - extract attachment OR download from URL."""
    message = service.users().messages().get(
        userId='me',
        id=message_id,
        format='full'
    ).execute()

    payload = message.get('payload', {})
    downloaded_files = []

    # First, try to extract CSV attachments (reports < 10MB)
    downloaded_files = extract_attachments(service, message_id, payload)

    # If no attachments, look for download URL (reports >= 10MB)
    if not downloaded_files:
        body = get_email_body(payload)
        # Also check snippet as fallback
        if not body:
            body = message.get('snippet', '')

        url = extract_download_url(body)
        if url:
            downloaded_files = download_from_url(url, message_id)

    return downloaded_files


def run_import(verbose: bool = True) -> Dict[str, Any]:
    """
    Run the Gmail import process.
    Returns a dict with results for API use.
    """
    result = {
        "success": False,
        "emails_processed": 0,
        "files_imported": 0,
        "errors": [],
        "files": []
    }

    if verbose:
        print("=" * 60)
        print(f"Cat-Scan Gmail Import - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

    try:
        service = get_gmail_service()
    except FileNotFoundError as e:
        error_msg = str(e)
        if verbose:
            print(f"ERROR: {error_msg}")
        result["errors"].append(error_msg)
        update_status(False, error=error_msg)
        return result
    except Exception as e:
        error_msg = f"Gmail authentication failed: {e}"
        if verbose:
            print(f"ERROR: {error_msg}")
        result["errors"].append(error_msg)
        update_status(False, error=error_msg)
        return result

    messages = find_report_emails(service)

    if not messages:
        if verbose:
            print("No new report emails found.")
        result["success"] = True
        update_status(True, files_imported=0, emails_processed=0)
        return result

    if verbose:
        print(f"Found {len(messages)} unread report email(s)\n")

    total_imported = 0

    for msg in messages:
        message_id = msg['id']
        if verbose:
            print(f"Processing email: {message_id}")

        try:
            downloaded_files = process_message(service, message_id)

            if not downloaded_files:
                if verbose:
                    print("  No CSV found (attachment or URL)")
                continue

            result["emails_processed"] += 1

            for filepath in downloaded_files:
                result["files"].append(str(filepath))

                # Archive to S3 before importing to database
                archive_to_s3(filepath, verbose=verbose)

                if import_to_catscan(filepath):
                    total_imported += 1

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
        emails_processed=result["emails_processed"]
    )

    return result


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

    result = run_import(verbose=not args.quiet)

    if not result["success"]:
        sys.exit(1)


if __name__ == '__main__':
    main()
