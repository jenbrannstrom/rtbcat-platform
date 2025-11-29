# RTBcat Creative Intelligence - Project Handover

**Date:** 2024-11-29  
**Project:** rtbcat-creative-intel  
**Status:** Code refactored, tests need to be generated  
**Location:** `~/Documents/rtbcat-creative-intel`

---

## Project Overview

Building "Creative Intelligence" software for mid-tier DSPs that:
1. Collects creatives from Google Authorized Buyers RTB API
2. Auto-clusters creatives into campaigns using AI (URL patterns, visual similarity)
3. Analyzes waste patterns from RTB logs
4. Recommends pretargeting optimizations to reduce costs

**Target customers:** Mid-tier DSPs who want private, in-house solutions without enterprise complexity.

---

## Current Status

### ✅ Completed

1. **Project scaffolded** with proper structure
2. **Collectors module refactored** from single 700-line file into modular structure:
   - `collectors/base.py` - Base API client (187 lines)
   - `collectors/creatives/client.py` - Creative API calls (157 lines)
   - `collectors/creatives/parsers.py` - Pure parsing functions (283 lines)
   - `collectors/creatives/schemas.py` - TypedDicts (135 lines)
   - `collectors/pretargeting/client.py` - Pretargeting API (108 lines)
   - `collectors/pretargeting/parsers.py` - Pretargeting parsers (211 lines)
   - `collectors/pretargeting/schemas.py` - TypedDicts (140 lines)
3. **README updated** - Removed Kubernetes, added practical deployment options
4. **Virtual environment set up** - `venv/` created and activated

### 🔄 In Progress

**Need to generate comprehensive test suite** for the refactored collectors module.

### ❌ Not Started

1. Dashboard (Next.js frontend)
2. AI clustering engine
3. CSV report ingestion from Gmail
4. Database schema for storage layer
5. Docker deployment testing

---

## Technology Stack

**Backend:**
- Python 3.12
- FastAPI
- Google Authorized Buyers RTB API (realtimebidding v1)
- SQLite (development) / PostgreSQL (production)
- AWS S3 (optional backup)

**Testing:**
- pytest
- pytest-mock
- pytest-asyncio
- pytest-cov

**AI/Clustering:**
- AWS Bedrock (Claude) or customer's own API (Grok/Gemini/self-hosted)

**Deployment:**
- Docker + Docker Compose
- Runs on customer's infrastructure (laptop or cloud server)
- Zero egress costs if using customer's AWS account

---

## Critical API Information

### Correct API: Google Authorized Buyers RTB API

**We use `bidders.creatives` NOT `buyers.creatives`**

- **Service:** `realtimebidding` v1
- **Parent format:** `bidders/{account_id}` (NOT `buyers/`)
- **Auth:** Service account JSON with scope `https://www.googleapis.com/auth/realtime-bidding`
- **Endpoints:**
  - `bidders().creatives().list()` - List all creatives
  - `bidders().creatives().get()` - Get specific creative
  - `bidders().pretargetingConfigs().list()` - List pretargeting configs

**Key API Response Fields:**
```json
{
  "name": "bidders/12345/creatives/cr-abc123",
  "creativeId": "cr-abc123",
  "creativeFormat": "HTML" | "VIDEO" | "NATIVE",
  "declaredClickThroughUrls": ["https://example.com?utm_campaign=spring"],
  "creativeServingDecision": {
    "networkPolicyCompliance": {
      "status": "APPROVED" | "PENDING_REVIEW" | "DISAPPROVED"
    }
  },
  // Union field 'content' - only ONE of these:
  "html": {"snippet": "...", "width": 300, "height": 250},
  "video": {"videoUrl": "...", "videoMetadata": {"duration": "15s"}},
  "native": {
    "headline": "...", 
    "clickLinkUrl": "...",  // ← IMPORTANT: Native uses different URL field
    "image": {"url": "...", "width": 1200, "height": 627}
  }
}
```

**Documentation:**
- Creatives: Already provided in previous messages
- Pretargeting: Already provided in previous messages

---

## Project Structure

```
rtbcat-creative-intel/
├── collectors/
│   ├── __init__.py           (40 lines)   - Public API exports
│   ├── base.py               (187 lines)  - BaseAuthorizedBuyersClient
│   ├── creatives/
│   │   ├── __init__.py       (25 lines)
│   │   ├── schemas.py        (135 lines)  - TypedDicts
│   │   ├── parsers.py        (283 lines)  - Pure parsing functions
│   │   └── client.py         (157 lines)  - CreativesClient
│   ├── pretargeting/
│   │   ├── __init__.py       (25 lines)
│   │   ├── schemas.py        (140 lines)  - TypedDicts
│   │   ├── parsers.py        (211 lines)  - Pure parsing functions
│   │   └── client.py         (108 lines)  - PretargetingClient
│   └── csv_reports.py        (303 lines)  - Gmail CSV fetcher (not yet used)
├── config/
│   ├── config_manager.py     - Encrypted credential storage (Fernet)
│   └── __init__.py
├── storage/
│   ├── sqlite_store.py       - Local SQLite database
│   ├── s3_writer.py          - AWS S3 backup
│   └── __init__.py
├── api/
│   ├── main.py               - FastAPI application
│   └── __init__.py
├── tests/
│   ├── conftest.py           - Pytest fixtures (needs updating)
│   ├── collectors/           - ⚠️ NEEDS TEST FILES GENERATED
│   │   └── __init__.py
│   ├── config/
│   ├── storage/
│   └── api/
├── main.py                   - CLI entry point
├── requirements.txt
├── requirements-dev.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## Usage (Current Working Code)

```python
from collectors import CreativesClient, PretargetingClient

# Initialize
creative_client = CreativesClient(
    credentials_path='~/.rtbcat/service-account.json',
    account_id='12345'
)

# Fetch creatives (async)
creatives = await creative_client.fetch_all_creatives()
# Returns: List[CreativeDict]

# Get specific creative
creative = await creative_client.get_creative_by_id('cr-abc123')

# Pretargeting
pretargeting_client = PretargetingClient(
    credentials_path='~/.rtbcat/service-account.json',
    account_id='12345'
)

configs = await pretargeting_client.fetch_all_pretargeting_configs()
```

---

## Immediate Next Task: Generate Test Suite

### What Needs to Be Created

**Directory structure:**
```
tests/collectors/
├── test_base.py                    # Test BaseAuthorizedBuyersClient
├── creatives/
│   ├── __init__.py
│   ├── test_client.py              # Test CreativesClient (with mocked API)
│   ├── test_parsers.py             # Test parsing functions (pure, no mocks)
│   └── fixtures/
│       ├── __init__.py
│       ├── html_creative.json      # Sample HTML creative API response
│       ├── video_creative.json     # Sample video creative API response
│       └── native_creative.json    # Sample native creative API response
└── pretargeting/
    ├── __init__.py
    ├── test_client.py              # Test PretargetingClient
    ├── test_parsers.py             # Test parsing functions
    └── fixtures/
        ├── __init__.py
        └── pretargeting_config.json
```

### Sample Fixture Files

**tests/collectors/creatives/fixtures/html_creative.json:**
```json
{
  "name": "bidders/12345/creatives/cr-html-001",
  "accountId": "12345",
  "creativeId": "cr-html-001",
  "creativeFormat": "HTML",
  "declaredClickThroughUrls": [
    "https://example.com/lp?utm_campaign=spring2024&utm_source=google&utm_medium=display"
  ],
  "advertiserName": "Example Corp",
  "apiUpdateTime": "2024-11-29T10:00:00Z",
  "html": {
    "snippet": "<div style='width:300px;height:250px;background:#ff5733'><h1>50% OFF</h1></div>",
    "width": 300,
    "height": 250
  },
  "creativeServingDecision": {
    "networkPolicyCompliance": {
      "status": "APPROVED"
    }
  }
}
```

**tests/collectors/creatives/fixtures/video_creative.json:**
```json
{
  "name": "bidders/12345/creatives/cr-video-001",
  "accountId": "12345",
  "creativeId": "cr-video-001",
  "creativeFormat": "VIDEO",
  "declaredClickThroughUrls": ["https://example.com/video?utm_campaign=summer"],
  "advertiserName": "Video Corp",
  "apiUpdateTime": "2024-11-28T15:00:00Z",
  "video": {
    "videoUrl": "https://storage.googleapis.com/creatives/video.mp4",
    "videoMetadata": {
      "duration": "15s",
      "isValidVast": true,
      "isVpaid": false
    }
  },
  "creativeServingDecision": {
    "networkPolicyCompliance": {
      "status": "APPROVED"
    }
  }
}
```

**tests/collectors/creatives/fixtures/native_creative.json:**
```json
{
  "name": "bidders/12345/creatives/cr-native-001",
  "accountId": "12345",
  "creativeId": "cr-native-001",
  "creativeFormat": "NATIVE",
  "advertiserName": "Native Ads Inc",
  "apiUpdateTime": "2024-11-27T12:00:00Z",
  "native": {
    "headline": "Amazing Product - Limited Time Offer",
    "body": "Get 50% off when you buy now. Free shipping!",
    "callToAction": "Shop Now",
    "clickLinkUrl": "https://example.com/native?utm_campaign=fall2024",
    "image": {
      "url": "https://storage.googleapis.com/images/product.jpg",
      "width": 1200,
      "height": 627
    },
    "logo": {
      "url": "https://storage.googleapis.com/images/logo.png",
      "width": 128,
      "height": 128
    }
  },
  "creativeServingDecision": {
    "networkPolicyCompliance": {
      "status": "PENDING_REVIEW"
    }
  }
}
```

**tests/collectors/pretargeting/fixtures/pretargeting_config.json:**
```json
{
  "name": "bidders/12345/pretargetingConfigs/config-001",
  "displayName": "US Desktop - Standard Sizes",
  "state": "ACTIVE",
  "billingId": "123",
  "includedFormats": ["HTML"],
  "includedCreativeDimensions": [
    {"width": "300", "height": "250"},
    {"width": "728", "height": "90"}
  ],
  "geoTargeting": {
    "includedIds": ["2840"],
    "excludedIds": []
  },
  "includedEnvironments": ["WEB"],
  "includedPlatforms": ["PERSONAL_COMPUTER"],
  "minimumViewabilityDecile": 5,
  "maximumQps": "10000"
}
```

### Test Requirements

- **Use pytest** for test framework
- **Use pytest-mock** for mocking Google API calls
- **Pure functions** (parsers) tested WITHOUT mocks
- **API clients** tested WITH mocked `googleapiclient.discovery.build()`
- **Use `@pytest.mark.parametrize`** for edge cases (e.g., testing `parse_utm_params` with various URL formats)
- **Each test file < 300 lines**
- **Update `tests/conftest.py`** with fixtures:
  - `mock_service_account` - Returns mock credentials
  - `mock_google_api_service` - Mocked API service
  - `sample_html_creative_response` - Loads fixture JSON
  - `sample_video_creative_response`
  - `sample_native_creative_response`

### Key Testing Patterns

**Pure functions (no mocking):**
```python
def test_parse_utm_params():
    url = "https://example.com?utm_campaign=test&utm_source=google"
    result = parse_utm_params(url)
    assert result == {"utm_campaign": "test", "utm_source": "google"}
```

**API clients (with mocking):**
```python
def test_fetch_all_creatives(mocker):
    mock_service = mocker.MagicMock()
    mock_service.bidders().creatives().list().execute.return_value = {
        "creatives": [sample_html_creative_response],
        "nextPageToken": None
    }
    
    client = CreativesClient(credentials_path="fake.json", account_id="123")
    client.service = mock_service
    
    creatives = await client.fetch_all_creatives()
    assert len(creatives) == 1
```

**Parametrized edge case tests:**
```python
@pytest.mark.parametrize("url,expected", [
    ("https://example.com?utm_campaign=test", {"utm_campaign": "test"}),
    ("https://example.com", {}),
    ("", {}),
    (None, {})
])
def test_parse_utm_params_edge_cases(url, expected):
    result = parse_utm_params(url)
    assert result == expected
```

---

## Environment Setup

**Virtual environment is already created and activated:**
```bash
cd ~/Documents/rtbcat-creative-intel
source venv/bin/activate  # Shows (venv) in prompt
```

**Installed packages:**
- Core dependencies from `requirements.txt`
- Need to install test dependencies: `pip install pytest pytest-mock pytest-asyncio pytest-cov`

---

## Known Issues / Gotchas

1. **Native creatives use different URL field:** `native.clickLinkUrl` instead of `declaredClickThroughUrls`
2. **Approval status path:** `creativeServingDecision.networkPolicyCompliance.status` (not `dealsPolicyCompliance`)
3. **Union field:** Only ONE of `html`, `video`, or `native` exists per creative
4. **Rate limiting:** API returns 429 errors, handled with exponential backoff in `base.py`
5. **Field names are plural:** `declaredClickThroughUrls` (array), not `declaredClickThroughUrl`

---

## Command Reference

```bash
# Activate venv (ALWAYS do this first)
cd ~/Documents/rtbcat-creative-intel
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install pytest pytest-mock pytest-asyncio pytest-cov

# Create test structure manually
mkdir -p tests/collectors/creatives/fixtures
mkdir -p tests/collectors/pretargeting/fixtures
touch tests/collectors/creatives/__init__.py
touch tests/collectors/pretargeting/__init__.py
touch tests/collectors/creatives/fixtures/__init__.py
touch tests/collectors/pretargeting/fixtures/__init__.py

# Run tests
pytest tests/collectors/ -v

# Run with coverage
pytest tests/collectors/ --cov=collectors --cov-report=term-missing

# View project tree
tree -L 4 --dirsfirst -I '__pycache__|*.pyc|venv|.git|*.egg-info|node_modules' --charset ascii

# Interactive Claude CLI
claude
# Then at '>' prompt, paste instructions
```

---

## Customer Context

**Jen's setup:**
- OS: Zorin OS (Ubuntu-based)
- IDE: VSCode with Claude extension
- Also has Claude CLI available via `claude` command (not `claude-code`)
- Working directory: `~/Documents/rtbcat-creative-intel`

**Customer needs:**
- Private, in-house solution (no data sharing)
- Cost-transparent (show real $ amounts, not "scalable")
- Simple installation (docker-compose up -d)
- Works for mid-tier DSPs (not enterprise complexity)

---

## Next Session Action Plan

1. **Generate test files** using VSCode Claude Extension or manually
2. **Create fixture JSON files** (samples provided above)
3. **Update `tests/conftest.py`** with fixtures
4. **Run tests** and fix any failures
5. **Achieve >80% code coverage** on parsers (pure functions)
6. **Then move to:** Dashboard development (Next.js)

---

## Important Links

- **API Docs:** Provided in previous conversation (search for "REST Resource: bidders.creatives")
- **GitHub:** Will be set up at https://github.com/rtbcat/creative-intel
- **README:** Already updated and committed

---

## Files That Need Attention

⚠️ **Priority 1:** Generate test suite
⚠️ **Priority 2:** Test API connection with real Google service account
⚠️ **Priority 3:** Build CSV report ingestion from Gmail
⚠️ **Priority 4:** Create dashboard mockups

---

## Code Modules to Understand

### collectors/creatives/parsers.py

**Key functions to test:**
- `parse_creative_response(raw: dict) -> CreativeDict` - Main parser
- `_extract_html_data(raw: dict) -> dict` - Parse HTML creative
- `_extract_video_data(raw: dict) -> dict` - Parse video creative
- `_extract_native_data(raw: dict) -> dict` - Parse native creative
- `_parse_utm_params(url: str) -> dict` - Extract UTM parameters
- `_get_approval_status(raw: dict) -> str` - Get approval status
- `_get_dest_url(raw: dict, creative_format: str) -> str` - Get destination URL

**All functions are PURE** - no side effects, no API calls, just data transformation.

### collectors/creatives/client.py

**Key methods to test:**
- `fetch_all_creatives(filter_str: str = None) -> List[CreativeDict]` - Fetch with pagination
- `get_creative_by_id(creative_id: str) -> CreativeDict` - Fetch single creative

**Both are async and make API calls** - need mocking.

### collectors/base.py

**Key methods to test:**
- `_execute_with_retry(request)` - Exponential backoff for rate limits
- Constructor validation

---

## Deployment Options (From README)

| Deployment | Monthly Cost | Creative Capacity | Best For |
|------------|--------------|-------------------|----------|
| Laptop | $0 | 10K creatives | POC, testing, demos |
| Cloud Server | $35-50 | 100K creatives | Production, teams |
| Customer AWS | $35* | 500K creatives | Privacy-focused, existing AWS users |
| RTB Fabric | Variable** | Unlimited | High-scale DSPs (200K+ QPS) |

*Uses customer's existing AWS account (no markup)
**Scales with QPS: $0.015/million requests + Lambda compute

---

## Quick Start for Next Claude Session

```bash
# 1. Navigate and activate venv
cd ~/Documents/rtbcat-creative-intel
source venv/bin/activate

# 2. Check current structure
tree tests/collectors/ -L 3

# 3. Start generating tests
# Option A: Use VSCode Claude Extension
# Option B: Create files manually following the structure above
```

**First task:** Create test files for `collectors/creatives/parsers.py` - these are pure functions and easiest to test.

---

## Test Generation Prompt for Next Session

If using Claude CLI or VSCode Extension, use this prompt:

```
Generate comprehensive test suite for rtbcat-creative-intel collectors module.

Create these test files:

1. tests/collectors/test_base.py
   - Test BaseAuthorizedBuyersClient initialization
   - Test _execute_with_retry with mocked rate limits
   - Test account_id validation

2. tests/collectors/creatives/test_parsers.py
   - Test parse_creative_response for HTML, video, native formats
   - Test _extract_html_data, _extract_video_data, _extract_native_data
   - Test _parse_utm_params with @pytest.mark.parametrize for edge cases:
     * Complete URL with all UTM params
     * URL with no UTM params
     * Malformed URL
     * None/empty string
   - Test _get_approval_status for APPROVED, PENDING_REVIEW, DISAPPROVED
   - Test _get_dest_url for HTML vs native creatives
   
3. tests/collectors/creatives/test_client.py
   - Test fetch_all_creatives with single page response
   - Test fetch_all_creatives with pagination (nextPageToken)
   - Test fetch_all_creatives with API error
   - Test get_creative_by_id success and not found cases
   - Use pytest-mock to mock googleapiclient

4. tests/collectors/creatives/fixtures/
   Create JSON files with realistic Google API responses (see samples in handover doc)

5. tests/collectors/pretargeting/test_parsers.py
   - Test parse_pretargeting_config
   - Test extraction of geo targeting, dimensions, formats

6. tests/collectors/pretargeting/test_client.py
   - Test fetch_all_pretargeting_configs
   - Test get_pretargeting_config_by_id

7. Update tests/conftest.py with fixtures:
   - mock_google_api_service
   - sample_html_creative_response (load from JSON)
   - sample_video_creative_response
   - sample_native_creative_response

Use pytest, pytest-mock. Pure functions tested without mocks. API clients tested with mocked googleapiclient.discovery.build(). Each test file < 300 lines. Complete implementations, not stubs.
```

---

**END OF HANDOVER**

Last updated: 2024-11-29  
Next session: Focus on test suite generation
