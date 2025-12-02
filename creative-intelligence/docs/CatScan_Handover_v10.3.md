# Cat-Scan Handover v10.3

**Date:** December 2, 2025
**Status:** Phase 9.7 - Onboarding Flow Complete
**Author:** [Session with Claude]

---

## Executive Summary

Cat-Scan is a privacy-first QPS optimization platform for Google Authorized Buyers.
Today's session focused on user onboarding and creative display improvements.

Key accomplishments:
- Fixed critical sync button bug (Docker path issue)
- Built complete /connect onboarding flow
- Implemented video thumbnail extraction from VAST
- Improved creative card UX (copy button, native icons)
- Added CLI thumbnail generator with ffmpeg

---

## What Changed Today (December 2, 2025)

### Bugs Fixed

| Bug | Root Cause | Fix |
|-----|------------|-----|
| Sync button error | Config stored Docker path `/credentials/...` instead of local `~/.catscan/...` | Updated ConfigManager to use local paths |
| Single-seat showed dropdown | Always rendered dropdown regardless of seat count | Conditional rendering: 1 seat = title, 2+ = dropdown |
| Video/HTML cards blank | Video element with preload=none rendered transparent | Gradient placeholder + VAST thumbnail extraction |
| API 500 error | Used `creative.creative_id` instead of `creative.id` | Fixed attribute name in main.py |

### New Features

| Feature | Files Changed | Description |
|---------|---------------|-------------|
| /connect page | `dashboard/src/app/connect/page.tsx` | Complete credential management flow |
| JSON upload | API: `/config/credentials` | Drag-drop service account JSON, secure storage |
| Setup guide | `docs/SETUP_GUIDE.md` | Comprehensive guide with GCP instructions |
| VAST thumbnails | `api/main.py` lines 654-672 | Extract companion images from VAST XML |
| Copy button | `creative-card.tsx` | Copy creative ID inline next to ID |
| CLI thumbnails | `cli/qps_analyzer.py` | Generate video thumbnails with ffmpeg |
| Thumbnail endpoint | `/thumbnails/{id}.jpg` | Serve locally-generated thumbnails |
| Help section | `/connect` page | Collapsible 'How to get a JSON key' |

### Files Created

- `dashboard/src/app/connect/page.tsx` (new, replaced /collect)
- `docs/SETUP_GUIDE.md` (new)
- `docs/CatScan_Handover_v10.3.md` (this file)

### Files Modified

- `dashboard/src/components/sidebar.tsx` - Conditional seat display
- `dashboard/src/components/creative-card.tsx` - Video thumbnails, copy button, native icons
- `dashboard/src/components/preview-modal.tsx` - Dimension-aware sizing with labels
- `dashboard/src/types/api.ts` - Added thumbnail_url to VideoPreview
- `creative-intelligence/api/main.py` - Credential endpoints, VAST parser, thumbnail serving
- `creative-intelligence/cli/qps_analyzer.py` - generate-thumbnails command
- `README.md` - Updated to v10.3 with new features and troubleshooting

---

## Current Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    USER'S MACHINE                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Browser → http://localhost:3000                             │
│     │                                                        │
│     ├── /connect      → Credential upload & account setup    │
│     ├── /creatives    → Creative browser with cards          │
│     ├── /import       → CSV upload (chunked)                 │
│     └── /             → Dashboard home                       │
│                                                              │
│  Dashboard (Next.js:3000)                                    │
│     │                                                        │
│     └── /api/* proxy ──→ Backend API (FastAPI:8000)          │
│                              │                               │
│                              ├── /config/credentials         │
│                              ├── /seats, /seats/{id}/sync    │
│                              ├── /creatives                  │
│                              ├── /thumbnails/{id}.jpg        │
│                              └── /qps/* reports              │
│                                                              │
│  Storage                                                     │
│     ├── ~/.catscan/catscan.db          (SQLite database)     │
│     ├── ~/.catscan/credentials/*.json   (Service accounts)   │
│     ├── ~/.catscan/config.enc          (Encrypted config)    │
│     └── ~/.catscan/thumbnails/         (Generated thumbs)    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Database Tables

| Table | Purpose | Row Count |
|-------|---------|-----------|
| creatives | Synced from Google RTB API | 658 |
| performance_data | Imported CSV rows | 264,085 |
| buyer_seats | Account/seat mapping | 1 |
| fraud_signals | Detected patterns | - |
| import_history | CSV import tracking | - |

### Key Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| /config/credentials | GET | Check credential status |
| /config/credentials | POST | Upload new service account JSON |
| /config/credentials | DELETE | Remove credentials |
| /seats | GET | List all seats with creative counts |
| /seats/{id}/sync | POST | Sync creatives for specific seat |
| /creatives | GET | List creatives with pagination |
| /creatives/{id} | GET | Single creative with video/native details |
| /thumbnails/{id}.jpg | GET | Serve locally-generated video thumbnail |

---

## Onboarding Flow (New)

### User Journey

```
1. User visits http://localhost:3000/connect
   │
   ├─ NOT CONFIGURED:
   │   └─ Shows upload UI + 'How to get a JSON key' help
   │
   └─ CONFIGURED:
       └─ Shows connected status + seat list + sync buttons
```

### Credential Storage

```
Upload JSON → Validate → Save to ~/.catscan/credentials/google-credentials.json
                              └─ Permissions: 0600 (owner read/write only)
```

---

## Creative Card System

### Thumbnail Sources by Format

| Format | Thumbnail Source | Fallback |
|--------|------------------|----------|
| NATIVE | `raw_data.native.logo` or `.image` | Gray placeholder with headline overlay |
| VIDEO | VAST CompanionAds (~9%) or local ffmpeg | Dark gradient + Play icon |
| HTML | Not implemented | Blue gradient + Code icon |

### VAST Thumbnail Extraction

```python
# In api/main.py - _extract_thumbnail_from_vast()
# Extracts from CompanionAds in VAST XML:
# 1. <StaticResource creativeType="image/...">URL</StaticResource>
# 2. Regex patterns for CDATA-wrapped URLs
```

### CLI Thumbnail Generation

```bash
# Generate thumbnails for videos without VAST companions
python cli/qps_analyzer.py generate-thumbnails --limit 100

# Force regenerate all
python cli/qps_analyzer.py generate-thumbnails --limit 500 --force
```

Thumbnails are stored in `~/.catscan/thumbnails/{creative_id}.jpg` and served via `/thumbnails/{id}.jpg`.

---

## What's NOT Done (Backlog)

### High Priority

| Item | Effort | Notes |
|------|--------|-------|
| Batch thumbnail generation | 2-4 hours | Run for all 600+ videos |
| Multi-account support | 4-6 hours | Backend needs multiple credential storage |
| Card/modal field redesign | 2-3 hours | Prioritize: spend, clicks, CPM, geo |

### Medium Priority

| Item | Effort | Notes |
|------|--------|-------|
| HTML preview in cards | 1-2 hours | Scaled iframe with sandbox |
| Test with multi-seat account | 1 hour | Need account with multiple seats |
| Account switcher UI | 2 hours | Dropdown in sidebar for multi-account |

### Low Priority

| Item | Notes |
|------|-------|
| Redirect /collect → /connect | For old bookmarks |
| Dark mode support | CSS variables ready |

---

## Commands Reference

### Daily Operations

```bash
# Start services
sudo systemctl start rtbcat-api
cd dashboard && npm run dev

# Import data
cd creative-intelligence && source venv/bin/activate
python cli/qps_analyzer.py validate /path/to/file.csv
python cli/qps_analyzer.py import /path/to/file.csv

# Generate video thumbnails
python cli/qps_analyzer.py generate-thumbnails --limit 100

# Reports
python cli/qps_analyzer.py summary
python cli/qps_analyzer.py full-report --days 7
```

### Troubleshooting

```bash
# Check services
sudo systemctl status rtbcat-api
journalctl -u rtbcat-api --since '10 minutes ago'

# Database
sqlite3 ~/.catscan/catscan.db 'SELECT COUNT(*) FROM creatives;'
sqlite3 ~/.catscan/catscan.db 'SELECT COUNT(*) FROM performance_data;'

# Check thumbnails
ls -la ~/.catscan/thumbnails/

# Reset credentials (if stuck)
rm ~/.catscan/credentials/google-credentials.json
# Then re-upload via /connect
```

---

## For Next Developer

### Quick Start

1. Read this document
2. Read README.md
3. Check services are running: `curl http://localhost:8000/health`
4. Visit http://localhost:3000/connect to verify credentials
5. Pick a task from the backlog above

### Key Files to Understand

| File | Why |
|------|-----|
| `creative-intelligence/api/main.py` | All API endpoints |
| `dashboard/src/app/connect/page.tsx` | Onboarding flow |
| `dashboard/src/components/creative-card.tsx` | Card rendering logic |
| `dashboard/src/components/sidebar.tsx` | Seat selector logic |
| `creative-intelligence/cli/qps_analyzer.py` | CLI tools including thumbnail generator |
| `creative-intelligence/qps/importer.py` | CSV validation & import |

### Gotchas

1. **Docker vs Local paths** - Config can store Docker paths that don't exist locally. Fix via /connect re-upload.
2. **Dashboard is separate from API** - Restart `npm run dev`, not just the API, for frontend changes.
3. **VAST thumbnails are ~9%** - Most videos need ffmpeg generation for thumbnails.
4. **Browser caching** - Hard refresh (Ctrl+Shift+R) after frontend changes.
5. **API auto-reload** - The systemd service runs with `--reload`, so Python changes take effect automatically.

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 10.3 | Dec 2, 2025 | Onboarding flow, VAST thumbnails, CLI generator, card improvements |
| 10.2 | Dec 1, 2025 | Unified data architecture |
| 10.0 | Nov 2025 | QPS optimization module |

---

**End of Handover Document**
