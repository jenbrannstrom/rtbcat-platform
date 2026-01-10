# Cat-Scan Roadmap

**Last Updated:** January 2026

---

## Known Bugs

- [ ] **Campaigns tab filtering** - Creative ID type mismatch causing empty campaigns view
- [ ] **Thumbnail placeholders** - Some creatives show placeholder instead of generated thumbnail (ffmpeg)
- [ ] **CSV import account mismatch** - Imports not linking to correct accounts

---

## Features - Free Tier

### Core Improvements
- [ ] **MCP Integration** - Connect AI tools via Model Context Protocol
- [ ] **Navigation restructure** - Cleaner sidebar organization with unified Settings
- [ ] **Creative geo display** - Language detection and geo-mismatch alerts

  **Requirements:**
  - Gemini API detects language on first creative sync (one-time analysis)
  - "Rescan, incorrect" button for manual re-analysis
  - Language field is human-editable
  - Mismatch alert when language doesn't match serving countries
  - API key via `GEMINI_API_KEY` environment variable

  **Implementation:**

  1. **Database Schema** (`migrations/015_language_detection.sql`)
     - `detected_language` (TEXT) - "German", "English", etc.
     - `detected_language_code` (TEXT) - ISO 639-1: "de", "en"
     - `language_confidence` (REAL) - 0.0 to 1.0
     - `language_source` (TEXT) - "gemini" or "manual"
     - `language_analyzed_at` (TIMESTAMP)
     - `language_analysis_error` (TEXT)

  2. **Creative Model** (`storage/models.py`)
     - Add new fields to `Creative` dataclass matching the migration

  3. **Language Analyzer** (`api/analysis/language_analyzer.py` - new)
     - `GeminiLanguageAnalyzer` class following `ai_clusterer.py` pattern
     - Lazy-loaded Gemini client with `GEMINI_API_KEY` env var
     - `extract_text_from_creative()` - gets text from HTML/VAST/native
     - `detect_language()` - calls Gemini, returns structured result
     - Graceful fallback when API not configured

  4. **Language-Country Mapping** (`utils/language_country_map.py` - new)
     - Map ISO 639-1 language codes to country codes where language is official
     - `check_language_country_match()` function for mismatch detection
     - Example: "de" (German) -> ["DE", "AT", "CH"]

  5. **Repository Updates** (`storage/repositories/creative_repository.py`)
     - `update_language_detection()` - save detection results
     - `get_creatives_needing_language_analysis()` - find unanalyzed creatives

  6. **API Endpoints** (`api/routers/creatives.py`)
     - `POST /creatives/{id}/analyze-language?force=false` - trigger analysis
     - `PUT /creatives/{id}/language` - manual update
     - `GET /creatives/{id}/geo-mismatch` - check mismatch status
     - New models: `LanguageDetectionResponse`, `GeoMismatchAlert`
     - Update `CreativeResponse` to include language fields

  7. **Sync Integration** (`api/routers/seats.py`)
     - Call language analysis for new creatives after sync
     - Only analyze creatives that haven't been analyzed yet
     - Non-blocking (async background processing)

  8. **Frontend Changes**
     - Types (`dashboard/src/types/api.ts`): Add `LanguageDetectionResponse`, `GeoMismatchAlert`
     - API Client (`dashboard/src/lib/api.ts`): `analyzeCreativeLanguage()`, `updateCreativeLanguage()`, `getCreativeGeoMismatch()`
     - Preview Modal (`dashboard/src/components/preview-modal.tsx`): Add `LanguageSection` component
       - Detected language with confidence
       - Mismatch alert (amber warning) if language doesn't match serving countries
       - "Rescan, incorrect" button
       - Inline edit form for manual correction

  9. **Dependencies** (`requirements.txt`)
     - Add: `google-generativeai>=0.3.0`

  **Critical Files:**
  | File | Change |
  |------|--------|
  | `migrations/015_language_detection.sql` | New migration |
  | `storage/models.py` | Add 6 new fields to Creative |
  | `api/analysis/language_analyzer.py` | New Gemini analyzer module |
  | `utils/language_country_map.py` | New language-country mapping |
  | `storage/repositories/creative_repository.py` | Add update methods |
  | `api/routers/creatives.py` | 3 new endpoints, update response |
  | `api/routers/seats.py` | Add language analysis to sync |
  | `dashboard/src/types/api.ts` | Add new interfaces |
  | `dashboard/src/lib/api.ts` | Add 3 API functions |
  | `dashboard/src/components/preview-modal.tsx` | Add LanguageSection |
  | `requirements.txt` | Add google-generativeai |

  **Verification:**
  1. Set `GEMINI_API_KEY` env var, run migration, test endpoint
  2. Open creative modal, verify language section and mismatch alerts
  3. Sync creatives, verify auto-analysis populates `language_analyzed_at`

### Pretargeting Management
- [ ] **Pretargeting Write API** - Push config changes to Google (patch, activate, suspend)
- [ ] **Rollback functionality** - Undo changes and restore previous snapshots
- [ ] **Change history tracking** - Full audit trail of all pretargeting modifications

---

## Features - Optimization Engine

- [ ] **QPS Adjudication Engine** - Auto-calculate optimal pretargeting based on performance data:

  the most crucial part of the app: QPS optimisation. So far we just built the framework.

  QPS optim is two parts:
  1. having the right data to hand to evaluate what is needed (we are 60% there with the current UI, there are some very confusing elements in the ui and missing data)
  2. the logic to figure out the best pretargeting config to apply. 

  Operationally we also need to WRITE the findings to the AB seat. AND crucially record those changes so we can roll them back in case it goes wrong.

  

  How do we use game theory to determine the best optimisation to the QPS problem?
  The factors are:
  1. the settings inside a pretargeting setting
  2. there are 10 pretargeting settings available
  3. the creatives uploaded to the AB seat contain targeting or the CSV's show what the bidder and media buyer is trying to do. A creative will always have at least one country targeting. 


  /home/jen/Documents/rtbcat-platform/DATA_SCIENCE_EVALUATION.md was an attempt at compiling what we have available. 

  We need to consult /home/jen/Documents/rtbcat-platform/DATA_SCIENCE_EVALUATION.md to see if we are actually using all data available to use to make those decisions. 
- [ ] **Creative change monitoring** - Detect new creatives and trigger optimization workflows
- [ ] **AI/MCP optimization** - Let AI agents analyze and optimize via MCP tools
- [ ] **Learning from outcomes** - Track before/after results to improve recommendation confidence

---

## Features - Paid Tier

- [ ] **Billing/subscription system** - Stripe integration for paid features
- [ ] **Auto-optimization** - Hands-free pretargeting adjustments based on new creatives

---

## Integrations

- [ ] **Robyn MMM integration** - Marketing mix modeling data export and visualization
- [ ] **Clerk auth for Terraform** - Secure credential handling during deployment

---

## Completed

- [x] Multi-bidder account support with account switching
- [x] Creative sync from Google Authorized Buyers API
- [x] CSV import (CLI and UI)
- [x] Gmail auto-import
- [x] RTB funnel visualization
- [x] Efficiency analysis with recommendations
- [x] Campaign clustering
- [x] Video thumbnail generation
- [x] GCP deployment with OAuth2 authentication
