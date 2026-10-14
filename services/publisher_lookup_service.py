"""Collect publisher identity evidence without conflating sellers and managers."""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Callable
from urllib.parse import urlencode, urlparse

from collectors.publisher_profiles import PublisherProfilesClient
from services.url_safety import PublicHTTPResponse, request_public_http_url


def normalize_domain(value: str) -> str:
    """Accept a domain or HTTP website; reject credentials, ports and IP literals."""
    parsed = urlparse(value if "://" in value else "https://" + value)
    if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password:
        raise ValueError("Use a public HTTP(S) website or domain")
    if parsed.port or not parsed.hostname:
        raise ValueError("Use a domain without a port")
    domain = parsed.hostname.lower().encode("idna").decode("ascii")
    if not re.fullmatch(
        r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]*",
        domain,
    ):
        raise ValueError("Use a public domain name")
    return domain.removeprefix("www.")


class _StoreHTML(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self.current: tuple[str, list[str]] | None = None
        self.title: list[str] = []
        self.in_title = False
        self.json_ld: list[str] = []
        self.in_json_ld = False

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag == "title":
            self.in_title = True
        if tag == "a":
            self.current = (dict(attrs).get("href", ""), [])
        if tag == "script" and dict(attrs).get("type") == "application/ld+json":
            self.in_json_ld = True

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title.append(data)
        if self.current:
            self.current[1].append(data)
        if self.in_json_ld:
            self.json_ld.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False
        if tag == "script":
            self.in_json_ld = False
        if tag == "a" and self.current:
            self.links.append((self.current[0], "".join(self.current[1])))
            self.current = None


def parse_ads_txt(text: str) -> dict[str, Any]:
    """A DIRECT seller account is deliberately not promoted to a manager."""
    owners: list[str] = []
    managers: list[dict] = []
    contacts: list[str] = []
    sellers: list[dict] = []
    invalid = 0
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if "=" in line:
            key, value = (part.strip() for part in line.split("=", 1))
            parts = [part.strip() for part in value.split(",")]
            try:
                if key.upper() == "OWNERDOMAIN":
                    domain = normalize_domain(parts[0])
                    if domain not in owners:
                        owners.append(domain)
                elif key.upper() == "MANAGERDOMAIN":
                    manager = {
                        "domain": normalize_domain(parts[0]),
                        "country": parts[1].upper() if len(parts) > 1 else None,
                    }
                    if manager not in managers:
                        managers.append(manager)
                elif key.upper() == "CONTACT":
                    contacts.append(value)
            except ValueError:
                invalid += 1
            continue
        parts = [part.strip() for part in line.split(",")]
        if (
            len(parts) not in (3, 4)
            or parts[2].upper() not in {"DIRECT", "RESELLER"}
            or not parts[1]
        ):
            invalid += 1
            continue
        try:
            domain = normalize_domain(parts[0])
        except ValueError:
            invalid += 1
            continue
        sellers.append(
            {
                "advertising_system": domain,
                "seller_id": parts[1],
                "relationship": parts[2].upper(),
                "line": number,
                "certification_id": parts[3] if len(parts) == 4 else None,
            }
        )
    return {
        "owner_domains": owners,
        "manager_domains": managers,
        "contacts": contacts,
        "sellers": sellers,
        "invalid_line_count": invalid,
    }


class PublisherLookupService:
    """On-demand evidence collection with bounded network reads and partial results."""

    def __init__(
        self, fetch: Callable[..., PublicHTTPResponse] = request_public_http_url
    ) -> None:
        self.fetch = fetch

    async def _read(
        self, url: str, max_bytes: int = 2 * 1024 * 1024
    ) -> PublicHTTPResponse:
        # DNS-pinned fetch validates every redirect and blocks private destinations.
        return await asyncio.wait_for(
            asyncio.to_thread(
                self.fetch,
                url,
                timeout=3,
                max_redirects=2,
                max_response_bytes=max_bytes,
                headers={
                    "User-Agent": "RTBcat-Publisher-Lookup/1.0",
                    "Accept-Encoding": "identity",
                },
            ),
            timeout=4,
        )

    async def _app(self, app_id: str) -> dict:
        if app_id.isdigit():
            url = "https://itunes.apple.com/lookup?" + urlencode({"id": app_id})
            response = await self._read(url)
            if response.status != 200:
                return {
                    "status": "unavailable",
                    "source_url": url,
                    "http_status": response.status,
                }
            results = json.loads(response.body).get("results", [])
            item = next((r for r in results if str(r.get("trackId")) == app_id), None)
            if not item:
                return {"status": "not_found", "source_url": url}
            return {
                "status": "ok",
                "source_url": url,
                "name": item.get("trackName"),
                "developer_name": item.get("sellerName"),
                "developer_website": item.get("sellerUrl"),
                "support_contacts": [],
            }
        url = "https://play.google.com/store/apps/details?" + urlencode(
            {"id": app_id, "hl": "en"}
        )
        response = await self._read(url)
        if response.status != 200:
            return {
                "status": "not_found" if response.status == 404 else "unavailable",
                "source_url": url,
                "http_status": response.status,
            }
        page = _StoreHTML()
        page.feed(response.body.decode("utf-8", errors="replace"))
        website = next(
            (
                href
                for href, label in page.links
                if "website" in label.lower()
                and href.startswith(("http://", "https://"))
            ),
            None,
        )
        title = "".join(page.title).removesuffix(" - Apps on Google Play")
        developer_name = None
        for raw in page.json_ld:
            try:
                structured = json.loads(raw)
                author = structured.get("author", {})
                if isinstance(author, dict) and isinstance(author.get("name"), str):
                    developer_name = author["name"]
            except (ValueError, AttributeError):
                continue
        return {
            "status": "ok" if website else "developer_website_missing",
            "source_url": url,
            "name": title,
            "developer_name": developer_name,
            "developer_website": website,
            "support_contacts": sorted(
                {
                    href[7:].split("?", 1)[0]
                    for href, _ in page.links
                    if href.startswith("mailto:")
                }
            ),
        }

    async def _manager(
        self, manager: dict, sellers: list[dict], owners: list[str]
    ) -> dict:
        domain = manager["domain"]
        url = f"https://{domain}/sellers.json"
        result = {
            **manager,
            "source_url": url,
            "status": "unavailable",
            "seller_matches": [],
        }
        ids = {s["seller_id"] for s in sellers if s["advertising_system"] == domain}
        if not ids:
            return {**result, "status": "no_account_to_match"}
        try:
            response = await self._read(url, max_bytes=8 * 1024 * 1024)
            if response.status != 200:
                return {**result, "http_status": response.status}
            data = json.loads(response.body)
            matches = [s for s in data.get("sellers", []) if s.get("seller_id") in ids]
            return {
                **result,
                "status": "ok" if matches else "account_not_found",
                "source_url": response.url,
                "contact_email": data.get("contact_email"),
                "seller_matches": matches,
                "declared_owner_domains": owners,
            }
        except Exception:
            return result

    async def _public(
        self,
        app_id: str | None,
        domain: str | None,
        result: dict,
        ads_ready: asyncio.Event,
    ) -> None:
        app = None
        if app_id:
            try:
                app = await self._app(app_id)
                result["app_store"] = app
            except Exception:
                result["app_store"] = {"status": "unavailable"}
        website = app.get("developer_website") if app else None
        # An explicit domain is website evidence. Never claim it was verified by a store.
        if domain:
            source_kind = "provided_domain"
        elif website:
            try:
                domain = normalize_domain(website)
            except ValueError:
                result["ads_txt"] = {"status": "invalid_developer_website"}
                return
            source_kind = "app_store_developer_website"
        else:
            result["ads_txt"] = {"status": "developer_website_missing"}
            return
        path = "app-ads.txt" if app_id else "ads.txt"
        url = f"https://{domain}/{path}"
        result["ads_txt"] = {
            "status": "unavailable",
            "source_url": url,
            "domain_source": source_kind,
        }
        try:
            response = await self._read(url)
            if response.status != 200:
                result["ads_txt"].update(
                    status="not_found" if response.status == 404 else "unavailable",
                    http_status=response.status,
                )
                return
            body = response.body.decode("utf-8-sig", errors="replace")
            if "<html" in body[:1024].lower() or "<!doctype" in body[:1024].lower():
                result["ads_txt"]["status"] = "invalid_content"
                return
            parsed = parse_ads_txt(body)
            all_sellers = parsed.pop("sellers")
            managers = parsed["manager_domains"]
            manager_domains = {m["domain"] for m in managers}
            prioritized = sorted(
                all_sellers,
                key=lambda s: (
                    s["advertising_system"] not in manager_domains,
                    s["advertising_system"] != "google.com",
                    s["relationship"] != "DIRECT",
                    s["line"],
                ),
            )
            result["ads_txt"].update(
                **parsed,
                status="ok",
                source_url=response.url,
                authorized_sellers=prioritized[:500],
                authorized_seller_count=len(all_sellers),
                sellers_truncated=len(all_sellers) > 500,
            )
            result["managers"] = [{**m, "status": "not_checked"} for m in managers]
            ads_ready.set()
            # Keep explicit declarations even when their corroborating fetch fails.
            checked = await asyncio.gather(
                *(
                    self._manager(m, all_sellers, parsed["owner_domains"])
                    for m in managers[:3]
                )
            )
            result["managers"] = checked + result["managers"][3:]
        except Exception:
            return

    async def lookup(
        self,
        *,
        app_id: str | None = None,
        domain: str | None = None,
        publisher_name: str | None = None,
        google_client: PublisherProfilesClient | None = None,
        google_status: str = "not_configured",
    ) -> dict[str, Any]:
        if app_id and not re.fullmatch(
            r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+|[0-9]+", app_id
        ):
            raise ValueError(
                "app_id must be an Android package or numeric Apple app ID"
            )
        domain = normalize_domain(domain) if domain else None
        publisher_name = publisher_name.strip() if publisher_name else None
        if not app_id and not domain and not publisher_name:
            raise ValueError("app_id, domain or publisher_name is required")
        result: dict[str, Any] = {
            "query": {
                "app_id": app_id,
                "domain": domain,
                "publisher_name": publisher_name,
            },
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "app_store": {"status": "not_requested"},
            "ads_txt": {"status": "pending" if app_id or domain else "not_requested"},
            "managers": [],
            "google_marketplace": {"status": google_status, "profiles": []},
            "notes": [
                "Manager declarations are publisher assertions, not independently verified contracts.",
                "DIRECT/RESELLER identifies a seller-account relationship, not a management mandate.",
                "Missing declarations or profiles mean unknown, not self-managed.",
                "App-store support contacts are not verified advertising sales contacts.",
                "Google profiles matched by DIRECT account identify authorized sellers, not necessarily managers.",
                "Company-name matches are search candidates, not verified app associations.",
            ],
        }

        ads_ready = asyncio.Event()

        async def public() -> None:
            try:
                if app_id or domain:
                    await self._public(app_id, domain, result, ads_ready)
            finally:
                ads_ready.set()

        public_task = asyncio.create_task(public())

        async def google() -> None:
            if google_client:
                result["google_marketplace"] = {"status": "pending", "profiles": []}
                codes = []
                if not publisher_name:
                    await ads_ready.wait()
                    codes = sorted(
                        {
                            seller["seller_id"]
                            for seller in result["ads_txt"].get(
                                "authorized_sellers", []
                            )
                            if seller["advertising_system"] == "google.com"
                            and seller["relationship"] == "DIRECT"
                            and re.fullmatch(r"pub-[0-9]+", seller["seller_id"])
                        }
                    )
                result["google_marketplace"] = await asyncio.to_thread(
                    google_client.lookup,
                    app_id=app_id,
                    domain=domain,
                    publisher_codes=codes[:20],
                    publisher_name=publisher_name,
                )
                if codes:
                    result["google_marketplace"].update(
                        queried_publisher_codes=codes[:20],
                        publisher_codes_truncated=len(codes) > 20,
                        account_evidence_url=result["ads_txt"].get("source_url"),
                    )

        tasks = [
            public_task,
            asyncio.create_task(google()),
        ]
        _, pending = await asyncio.wait(tasks, timeout=12)
        for task in pending:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        for key in ("ads_txt", "google_marketplace"):
            if result[key]["status"] == "pending":
                result[key]["status"] = "timeout"
        result["partial"] = (
            bool(pending)
            or any(
                result[k]["status"] not in {"ok", "not_requested", "no_visible_match"}
                for k in ("app_store", "ads_txt", "google_marketplace")
            )
            or any(manager["status"] != "ok" for manager in result["managers"])
            or bool(result["google_marketplace"].get("truncated"))
            or bool(result["google_marketplace"].get("publisher_codes_truncated"))
        )
        return result
