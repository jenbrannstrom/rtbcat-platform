"""Read-only, bounded lookups against Google's Authorized Buyers Marketplace API."""

from __future__ import annotations

import json
import re
from typing import Any

import google.auth
from google.auth.transport.requests import AuthorizedSession
from google.oauth2 import service_account

MARKETPLACE_SCOPE = "https://www.googleapis.com/auth/authorized-buyers-marketplace"
MARKETPLACE_BASE = "https://authorizedbuyersmarketplace.googleapis.com/v1"


class PublisherProfilesClient:
    """Use the selected buyer's credentials, never the bidder ID as the buyer ID."""

    def __init__(self, buyer_id: str, credentials_path: str | None = None) -> None:
        if not re.fullmatch(r"[0-9]+", buyer_id):
            raise ValueError("Google buyer_id must be numeric")
        self.buyer_id = buyer_id
        self.credentials_path = credentials_path

    def lookup(
        self,
        *,
        app_id: str | None = None,
        domain: str | None = None,
        publisher_codes: list[str] | None = None,
        publisher_name: str | None = None,
    ) -> dict[str, Any]:
        # Quote values as JSON strings to prevent injected filter operators.
        # Seller-code and name filters were verified live. App/domain filters
        # currently fail upstream, so errors must never become "no match".
        clauses = []
        if app_id:
            clauses.append(f"mobileApps.externalAppId: {json.dumps(app_id)}")
        if domain:
            clauses.append(f"domains: {json.dumps(domain)}")
        query = " OR ".join(clauses)
        match_basis = "app_or_domain_filter"
        if publisher_codes:
            if len(publisher_codes) > 20 or any(
                not re.fullmatch(r"pub-[0-9]+", code) for code in publisher_codes
            ):
                raise ValueError("Provide at most 20 Google publisher codes")
            values = " OR ".join(json.dumps(code) for code in publisher_codes)
            query = f"isParent: true AND publisherCode = ({values})"
            match_basis = "ads_txt_google_direct_account"
        elif publisher_name:
            query = f"displayName: {json.dumps(publisher_name)}"
            match_basis = "publisher_name_search"
        if not query:
            raise ValueError("An app, domain, publisher code or name is required")
        source = f"{MARKETPLACE_BASE}/buyers/{self.buyer_id}/publisherProfiles"
        try:
            if self.credentials_path:
                credentials = service_account.Credentials.from_service_account_file(
                    self.credentials_path, scopes=[MARKETPLACE_SCOPE]
                )
            else:
                credentials, _ = google.auth.default(scopes=[MARKETPLACE_SCOPE])
            profiles = []
            page_token = None
            with AuthorizedSession(credentials) as session:
                for _ in range(3):
                    params = {"pageSize": 100, "filter": query}
                    if page_token:
                        params["pageToken"] = page_token
                    response = session.get(source, params=params, timeout=5)
                    data = response.json()
                    if not response.ok:
                        error = data.get("error", {})
                        reasons = {
                            item.get("reason")
                            for item in error.get("details", [])
                            if isinstance(item, dict)
                        }
                        status = (
                            "api_disabled"
                            if "SERVICE_DISABLED" in reasons
                            else {
                                400: "query_rejected",
                                401: "authentication_failed",
                                403: "permission_denied",
                                429: "rate_limited",
                            }.get(response.status_code, "unavailable")
                        )
                        return {
                            "status": status,
                            "http_status": response.status_code,
                            "source_url": source,
                            "filter": query,
                            "match_basis": match_basis,
                            "profiles": [],
                            "required_scope": MARKETPLACE_SCOPE,
                        }
                    profiles.extend(data.get("publisherProfiles", []))
                    page_token = data.get("nextPageToken")
                    if not page_token:
                        break
            return {
                "status": "ok" if profiles else "no_visible_match",
                "source_url": source,
                "filter": query,
                "match_basis": match_basis,
                "profiles": profiles,
                "truncated": bool(page_token),
                "note": "Publisher-supplied seller profiles; not proof of an exclusive management relationship. Parent profiles may omit app/domain lists.",
            }
        except Exception:
            # Credentials, OAuth responses and request headers must not enter results.
            return {"status": "unavailable", "source_url": source, "profiles": []}
