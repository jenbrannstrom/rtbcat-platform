#!/usr/bin/env python3
"""
Gmail OAuth Setup for Cat-Scan

This script helps you set up Gmail OAuth credentials for importing
scheduled reports from Google Authorized Buyers.

Prerequisites:
1. Go to https://console.cloud.google.com/apis/credentials
2. Create OAuth 2.0 Client ID (Desktop app)
3. Download the JSON file
4. Save it as ~/.catscan/credentials/gmail-oauth-client.json

Then run this script to complete the authorization.
"""

import os
import sys
from pathlib import Path

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Configuration
SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/devstorage.read_only',
]
CATSCAN_DIR = Path.home() / '.catscan'
CREDENTIALS_DIR = CATSCAN_DIR / 'credentials'
TOKEN_PATH = CREDENTIALS_DIR / 'gmail-token.json'
CLIENT_SECRET_PATH = CREDENTIALS_DIR / 'gmail-oauth-client.json'


def print_setup_instructions():
    """Print instructions for setting up Gmail OAuth."""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                        Gmail OAuth Setup for Cat-Scan                         ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  This script will authorize Cat-Scan to read emails from your Gmail         ║
║  account to import Google Authorized Buyers reports.                         ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

STEP 1: Create OAuth Client (if not done already)
─────────────────────────────────────────────────

1. Go to: https://console.cloud.google.com/apis/credentials

2. Click "+ CREATE CREDENTIALS" → "OAuth client ID"

3. If prompted to configure consent screen:
   - User Type: External
   - App name: Cat-Scan
   - User support email: your email
   - Developer contact: your email
   - Scopes: Add 'gmail.readonly'
   - Test users: Add the Gmail that receives AB reports

4. Create the OAuth client:
   - Application type: "Desktop app"
   - Name: "Cat-Scan Gmail Import"

5. Download the JSON file

6. Save it as:
   ~/.catscan/credentials/gmail-oauth-client.json


STEP 2: Authorize (this script handles this)
────────────────────────────────────────────

Once you have the OAuth client JSON file in place, this script will:
1. Open a browser for you to log in
2. Ask you to grant Gmail read access
3. Save the authorization token for future use

""")


def check_client_secret():
    """Check if OAuth client secret exists."""
    if not CLIENT_SECRET_PATH.exists():
        print(f"❌ OAuth client not found at: {CLIENT_SECRET_PATH}")
        print()
        print("Please complete Step 1 above first, then run this script again.")
        return False

    print(f"✓ OAuth client found at: {CLIENT_SECRET_PATH}")
    return True


def check_existing_token():
    """Check if we already have a valid token."""
    if TOKEN_PATH.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
            if creds and creds.valid:
                print(f"✓ Valid token exists at: {TOKEN_PATH}")
                return creds
            elif creds and creds.expired and creds.refresh_token:
                print("⟳ Token expired, refreshing...")
                creds.refresh(Request())
                TOKEN_PATH.write_text(creds.to_json())
                print(f"✓ Token refreshed and saved")
                return creds
        except Exception as e:
            print(f"⚠ Existing token invalid: {e}")

    return None


def authorize():
    """Run the OAuth authorization flow."""
    print()
    print("Starting OAuth authorization flow...")
    print("A browser window will open. Please log in with the Gmail account")
    print("that receives Google Authorized Buyers reports.")
    print()

    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            str(CLIENT_SECRET_PATH),
            SCOPES
        )
        creds = flow.run_local_server(port=0)

        # Save the token
        CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
        TOKEN_PATH.write_text(creds.to_json())

        print()
        print(f"✓ Authorization successful!")
        print(f"✓ Token saved to: {TOKEN_PATH}")

        return creds

    except Exception as e:
        print(f"❌ Authorization failed: {e}")
        return None


def test_gmail_access(creds):
    """Test that we can access Gmail."""
    print()
    print("Testing Gmail API access...")

    try:
        service = build('gmail', 'v1', credentials=creds)

        # Get user profile
        profile = service.users().getProfile(userId='me').execute()
        email = profile.get('emailAddress', 'unknown')
        print(f"✓ Connected as: {email}")

        # Check for AB report emails
        query = 'from:noreply-google-display-ads-managed-reports@google.com'
        results = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=5
        ).execute()

        messages = results.get('messages', [])
        if messages:
            print(f"✓ Found {len(messages)} Authorized Buyers report emails")
        else:
            print("⚠ No Authorized Buyers report emails found yet")
            print("  (This is normal if you haven't set up scheduled reports)")

        return True

    except Exception as e:
        print(f"❌ Gmail API test failed: {e}")
        return False


def main():
    """Main setup flow."""
    # Create directories
    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)

    # Print instructions
    print_setup_instructions()

    # Check for OAuth client
    if not check_client_secret():
        return 1

    # Check for existing valid token
    creds = check_existing_token()

    if not creds:
        # Need to authorize
        creds = authorize()
        if not creds:
            return 1

    # Test Gmail access
    if not test_gmail_access(creds):
        return 1

    print()
    print("═" * 60)
    print("  Gmail OAuth setup complete!")
    print("═" * 60)
    print()
    print("Next steps:")
    print("  1. Run: python scripts/gmail_import.py")
    print("  2. Check the dashboard for imported data")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
