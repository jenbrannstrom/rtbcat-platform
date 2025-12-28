# Gmail OAuth Setup for Cat-Scan

This guide explains how to set up Gmail OAuth credentials for automated CSV imports from **cat-scan@rtb.cat**.

---

## Prerequisites

- Access to [Google Cloud Console](https://console.cloud.google.com/)
- The Gmail account: `cat-scan@rtb.cat`

---

## Step 1: Create or Select a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click the project dropdown at the top
3. Either select an existing project or click **New Project**
   - Project name: `Cat-Scan` (or similar)
   - Click **Create**

---

## Step 2: Enable Gmail API

1. Go to **APIs & Services** → **Library**
   - Direct link: https://console.cloud.google.com/apis/library
2. Search for **"Gmail API"**
3. Click on **Gmail API**
4. Click **Enable**

---

## Step 3: Configure OAuth Consent Screen

1. Go to **APIs & Services** → **OAuth consent screen**
   - Direct link: https://console.cloud.google.com/apis/credentials/consent
2. Choose user type:
   - **Internal** (if using Google Workspace and only internal users)
   - **External** (for regular Gmail accounts)
3. Click **Create**

4. Fill in the **App information**:
   | Field | Value |
   |-------|-------|
   | App name | `Cat-Scan Gmail Import` |
   | User support email | `cat-scan@rtb.cat` |
   | App logo | (optional) |
   | Developer contact email | Your email address |

5. Click **Save and Continue**

6. **Scopes** page:
   - Click **Add or Remove Scopes**
   - Find and check: `https://www.googleapis.com/auth/gmail.modify`
   - Or manually add: `https://www.googleapis.com/auth/gmail.modify`
   - Click **Update**
   - Click **Save and Continue**

7. **Test users** page:
   - Click **+ Add Users**
   - Add: `cat-scan@rtb.cat`
   - Click **Add**
   - Click **Save and Continue**

8. Review the summary and click **Back to Dashboard**

---

## Step 4: Create OAuth Client ID

1. Go to **APIs & Services** → **Credentials**
   - Direct link: https://console.cloud.google.com/apis/credentials
2. Click **+ Create Credentials** → **OAuth client ID**
3. Fill in:
   | Field | Value |
   |-------|-------|
   | Application type | **Desktop app** |
   | Name | `Cat-Scan Gmail Import` |

4. Click **Create**

5. A dialog will appear with your credentials
   - Click **Download JSON**
   - Save the file as: `gmail-oauth-client.json`

---

## Step 5: Upload Credentials to Server

```bash
# Copy the OAuth client file to the server
scp ~/Downloads/gmail-oauth-client.json ec2-user@63.176.52.250:~/.catscan/credentials/
```

---

## Step 6: Complete OAuth Flow on Server

```bash
# SSH to the server
ssh ec2-user@63.176.52.250

# Activate the virtual environment
cd /opt/catscan && source venv/bin/activate

# Run the Gmail import script
python scripts/gmail_import.py
```

The script will:
1. Print a URL - copy and open it in your browser
2. Sign in as `cat-scan@rtb.cat`
3. Grant permission to the app
4. Copy the authorization code shown
5. Paste it back into the terminal

The token will be saved to `~/.catscan/credentials/gmail-token.json`

---

## Step 7: Verify Setup

```bash
# Check import status
python scripts/gmail_import.py --status

# Or via API
curl http://localhost:8000/gmail/status
```

Expected output:
```json
{
  "configured": true,
  "authorized": true,
  "last_run": null,
  "total_imports": 0
}
```

---

## Troubleshooting

### "Access blocked: This app's request is invalid"

- Make sure you added `cat-scan@rtb.cat` as a test user in the OAuth consent screen
- If using External user type, the app must be in "Testing" mode

### "Error 403: access_denied"

- The user declined the permission request
- Run the import script again and accept all permissions

### "Token has been expired or revoked"

```bash
# Delete the old token and re-authenticate
rm ~/.catscan/credentials/gmail-token.json
python scripts/gmail_import.py
```

### "File not found: gmail-oauth-client.json"

```bash
# Check if the file exists
ls -la ~/.catscan/credentials/

# Make sure it's named correctly
mv ~/.catscan/credentials/client_secret_*.json ~/.catscan/credentials/gmail-oauth-client.json
```

---

## File Locations

| File | Path | Purpose |
|------|------|---------|
| OAuth Client | `~/.catscan/credentials/gmail-oauth-client.json` | App credentials (from Google Console) |
| OAuth Token | `~/.catscan/credentials/gmail-token.json` | User authorization (created after OAuth flow) |

---

## Security Notes

- **Never commit** these credential files to git
- The OAuth client JSON contains your app's client ID and secret
- The token JSON contains refresh tokens that grant access to the Gmail account
- Both files should have restricted permissions: `chmod 600 ~/.catscan/credentials/*.json`

---

*Last updated: December 21, 2025*
