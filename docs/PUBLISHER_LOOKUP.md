# Publisher identity lookup

Collect live evidence about who owns, manages or sells an app/site. This feature
does not score opportunities, query spend, contact companies, create deals, or
change bidding. Results carry retrieval times and source URLs. No database
migration is required; callers can save the JSON/CSV output.

## Interfaces

- App session: `POST /publisher-lookup` (`/api/publisher-lookup` through the edge).
- Agent token: `POST /agent/v1/publisher-lookup`, requiring
  `agent:publishers:read` and access to the requested buyer.
- MCP: `rtbcat_lookup_publisher`, forwarding to that Agent API route.

Example body (use a real buyer ID accessible to the caller):

```json
{
  "buyer_id": "12345678",
  "app_id": "com.example.app",
  "include_google": true
}
```

An Android package or numeric Apple app ID can be supplied as `app_id`.
A `domain` can be supplied instead for website `ads.txt`, or alongside an app
ID as an explicit developer-domain override for `app-ads.txt`. An override is
labelled `provided_domain`; it is not presented as an app-store-verified link.
Supply `publisher_name` (for example, `AnyMind`) to search Google's profiles
by company name. Name matches are candidates, not verified app associations;
an explicit name search takes precedence over automatic Google account matching.

## Sources and interpretation

1. Google Play or Apple's lookup API supplies the developer website and name.
   Store support addresses remain labelled as support, not advertising sales.
2. The developer site's `app-ads.txt` (or website `ads.txt`) supplies
   `OWNERDOMAIN`, `MANAGERDOMAIN` and authorized seller-account declarations.
   Manager declarations can be country-specific; the country is preserved.
3. For up to three declared managers, `sellers.json` is fetched and joined by
   the manager's advertising-system domain and exact seller ID. Its business
   contact and matching seller records are returned as corroborating evidence.
4. Google's Marketplace `buyers.publisherProfiles.list` supplies visible seller
   profiles and publisher-entered `directDealsContact` and
   `programmaticDealsContact` fields. Up to 20 Google `DIRECT` account IDs from
   the ads file are matched to parent seller profiles using `publisherCode`.
   Results include the queried IDs, ads-file evidence URL and match basis.
   This identifies authorized sellers, not an agency's management mandate.
   An explicit company-name search uses `displayName` instead.

`DIRECT` is an account relationship, not proof of publisher management. A Google
parent profile groups a seller's inventory; it does not establish an MCM parent
relationship. A missing manager or Google match means unknown. Profiles and
declarations are self-reported, can be incomplete or stale, and do not prove
exclusive rights or availability through a non-Google buying path.

Google parent profiles may omit app/domain lists, and not every publisher shares
a full profile. This is therefore not a complete discovery mirror of every
inventory association in the Authorized Buyers UI.

## Google setup

The service account selected for the buyer needs Marketplace access. The
`authorizedbuyersmarketplace.googleapis.com` service must be enabled in that
credential's project, and tokens use the
`https://www.googleapis.com/auth/authorized-buyers-marketplace` scope.
Enabling the API alone does not grant access to a buyer account.

The app uses the seat's linked active service account. A missing or inactive
linked account fails closed instead of selecting another customer's credential.
Legacy configured credentials/ADC are considered only for seats without a link.
The lookup does not relink accounts or update their metadata.

`api_disabled`, `permission_denied`, `authentication_failed`, `query_rejected`,
`rate_limited`, `credentials_missing`, `timeout` and `no_visible_match` are
distinct outcomes. Public evidence remains available when Google cannot be
queried. A rejected filter is not an empty result.

Live verification on 2026-10-14: the Marketplace API was enabled in
`catscan-prod-202601`. The app's service account can read profiles for buyers
`6574658621` and `6634662463`. Seller-code and company-name filters work.
Google currently rejects the documented nested app-field path and returns HTTP
500 for domain filters. When no usable Google DIRECT account is available,
the app/domain query still reports its explicit upstream failure. It never
turns that failure into a claim that no publisher exists.

## CSV and single-identity collection

Run from the repository with the existing Python environment:

```bash
venv/bin/python scripts/publisher_lookup.py \
  --input-csv /path/publishers.csv \
  --app-id-column 'Mobile app ID' \
  --output-json /path/publisher-evidence.json \
  --output-csv /path/publishers-enriched.csv
```

Add `--buyer-id BUYER_ID --credentials /secure/service-account.json` for Google.
Omit `--credentials` to use ADC with a buyer ID. Credentials never enter outputs.
Use `--domain-column COLUMN` for a website/domain input column. For one identity,
replace `--input-csv` with `--app-id com.example.app` or `--domain example.com`.
Use `--publisher-name AnyMind --buyer-id BUYER_ID` for a company-name search.

The CSV preserves input columns and row order, and adds evidence columns. Rows
without an app ID/domain are retained with `identity_required`; names alone are
not guessed. The JSON keeps the complete bounded lookup response for each row.

## Bounds and release checks

The API allows twelve seconds for evidence collection and returns completed
sections if another source times out. Each public fetch has DNS-pinned public
addresses, validated redirects, two redirects maximum, and response-size limits
(2 MiB for store/ads text, 8 MiB for manager seller files). Up to 500 seller lines
are returned, prioritizing declared-manager and Google accounts, with the total
count and explicit truncation flag. Google reads at most three 100-profile pages
and reports truncation. The CLI processes input rows sequentially.

No public Google seller-file crawl is performed on each query: that file can be
very large. Non-manager seller identities remain account IDs unless Google
Marketplace exposes the matching profile. App-store layout changes may require
updating extraction; a missing developer website is explicit, never fabricated.

Run `venv/bin/python -m pytest tests/test_publisher_lookup.py
tests/test_mcp_server_tools.py tests/test_mcp_server_auth_and_limits.py
tests/test_agent_scope_and_seat_enforcement.py tests/test_url_safety.py -q`.
Deploy API and MCP images from the same normal release. Existing live endpoints
do not acquire the new routes/tool until that release is deployed.

## Primary references

- [Google publisher profile fields](https://developers.google.com/authorized-buyers/apis/marketplace/reference/rest/v1/buyers.publisherProfiles)
- [Google profile listing and scope](https://developers.google.com/authorized-buyers/apis/marketplace/reference/rest/v1/buyers.publisherProfiles/list)
- [Google repeated-field filter syntax](https://developers.google.com/authorized-buyers/apis/guides/get-started/list-filters)
- [Google visibility limitations](https://developers.google.com/authorized-buyers/apis/guides/marketplace/publisher-profiles)
- [IAB ads.txt/app-ads.txt specifications](https://iabtechlab.com/ads-txt/)
