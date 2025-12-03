# Cat-Scan Installation Guide

## System Requirements

| Requirement | Minimum Version | Check Command | Install Command (Ubuntu/Debian) |
|-------------|----------------|---------------|--------------------------------|
| Python | 3.11+ | `python3 --version` | `sudo apt install python3.11 python3.11-venv` |
| Node.js | 18+ | `node --version` | `curl -fsSL https://deb.nodesource.com/setup_20.x \| sudo -E bash - && sudo apt install nodejs` |
| npm | 9+ | `npm --version` | (included with Node.js) |
| ffmpeg | 4.0+ | `ffmpeg -version` | `sudo apt install ffmpeg` |
| SQLite | 3.35+ | `sqlite3 --version` | `sudo apt install sqlite3` |

### Optional but Recommended

| Tool | Purpose | Install Command |
|------|---------|-----------------|
| Git | Version control | `sudo apt install git` |
| curl | API testing | `sudo apt install curl` |

---

## Quick Start (5 minutes)

### 1. Clone the Repository

```bash
git clone https://github.com/yourorg/rtbcat-platform.git
cd rtbcat-platform
```

### 2. Run the Setup Script

```bash
./setup.sh
```

This will:
- Check all requirements
- Create Python virtual environment
- Install Python dependencies
- Install Node.js dependencies
- Initialize the database

### 3. Configure Google Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create or select a project
3. Enable the **Real-Time Bidding API**
4. Create a Service Account:
   - IAM & Admin → Service Accounts → Create
   - Name: `catscan`
   - Download JSON key
5. Authorize in [Authorized Buyers](https://authorized-buyers.google.com/):
   - Settings → API Access → Add the service account email

### 4. Start Cat-Scan

```bash
# Start the API
cd creative-intelligence
source venv/bin/activate
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000

# In another terminal, start the dashboard
cd dashboard
npm run dev
```

### 5. Open in Browser

Visit http://localhost:3000

---

## Manual Installation

If the setup script doesn't work for your system:

### Backend (Python)

```bash
cd creative-intelligence

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Initialize database
python -c "from storage.sqlite_store import SQLiteStore; SQLiteStore()"
```

### Frontend (Node.js)

```bash
cd dashboard

# Install dependencies
npm install

# Build for production (optional)
npm run build
```

---

## Running as a Service (Linux)

### Create systemd service for API

```bash
sudo tee /etc/systemd/system/catscan-api.service << EOF
[Unit]
Description=Cat-Scan API
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)/creative-intelligence
Environment=PATH=$(pwd)/creative-intelligence/venv/bin
ExecStart=$(pwd)/creative-intelligence/venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable catscan-api
sudo systemctl start catscan-api
```

### Check status

```bash
sudo systemctl status catscan-api
```

---

## Troubleshooting

### "Python not found"

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip

# Or use pyenv for version management
curl https://pyenv.run | bash
pyenv install 3.11.0
pyenv global 3.11.0
```

### "Node.js not found"

```bash
# Using NodeSource (recommended)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install nodejs

# Or use nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
nvm install 20
nvm use 20
```

### "ffmpeg not found"

```bash
sudo apt install ffmpeg
```

Video thumbnail generation won't work without ffmpeg, but all other features will.

### "Permission denied" on credentials

```bash
chmod 600 ~/.catscan/credentials/google-credentials.json
```

### "PERMISSION_DENIED" from Google API

1. Verify Real-Time Bidding API is enabled in Cloud Console
2. Verify service account email is added in Authorized Buyers UI
3. Check the account ID matches your Authorized Buyers account

### Database errors

```bash
# Reset database (WARNING: deletes all data)
rm ~/.catscan/catscan.db
python -c "from storage.sqlite_store import SQLiteStore; SQLiteStore()"
```

---

## Verify Installation

Run the health check:

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "configured": true,
  "has_credentials": true,
  "database_exists": true
}
```

---

## Directory Structure

After installation, Cat-Scan uses these directories:

```
~/.catscan/
├── catscan.db            # SQLite database
├── thumbnails/           # Generated video thumbnails
└── credentials/          # Google service account JSON
```

---

## Next Steps

1. Visit http://localhost:3000/connect to configure credentials
2. Discover and sync your buyer seats
3. Import CSV performance data from Authorized Buyers
4. Start analyzing QPS waste!

---

## Getting Help

- Check the [Troubleshooting](#troubleshooting) section above
- Open an issue on GitHub
- See [docs/](docs/) for detailed documentation
