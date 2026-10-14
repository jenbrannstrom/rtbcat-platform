"""Evidence interpretation, source failures, buyer authorization and live transport."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI, HTTPException

from api.dependencies import get_config, get_current_user, get_store
from api.routers import publisher_lookup as routes
from api.schemas.publisher_lookup import PublisherLookupRequest
from collectors import publisher_profiles as google
from services.agent_token_service import AGENT_PUBLISHERS_READ_SCOPE
from services.auth_service import User
from services.publisher_lookup_service import (
    PublisherLookupService,
    normalize_domain,
    parse_ads_txt,
)
from services.url_safety import PublicHTTPResponse, UnsafePublicURL
from tests.support.asgi_client import SyncASGIClient


def response(url, body, status=200):
    return PublicHTTPResponse(status=status, body=body.encode(), headers={}, url=url)


def test_ads_txt_distinguishes_manager_from_direct_account():
    parsed = parse_ads_txt(
        """
OWNERDOMAIN=publisher.example
MANAGERDOMAIN=manager.example, PK # territory-specific declaration
manager.example, seller-42, DIRECT
google.com, pub-999, RESELLER, cert
unrelated.example, direct-1, DIRECT
bad.example, x, OWNER
"""
    )
    assert parsed["manager_domains"] == [{"domain": "manager.example", "country": "PK"}]
    assert parsed["owner_domains"] == ["publisher.example"]
    assert len(parsed["sellers"]) == 3
    assert parsed["invalid_line_count"] == 1


@pytest.mark.parametrize(
    "value",
    [
        "http://user:password@site.example",
        "127.0.0.1",
        "https://site.example:8000",
        "file:///etc/passwd",
    ],
)
def test_invalid_domain_inputs_are_rejected(value):
    with pytest.raises(ValueError):
        normalize_domain(value)


@pytest.mark.asyncio
async def test_store_to_manager_account_evidence_and_google_failure():
    calls = []

    def fetch(url, **kwargs):
        calls.append(url)
        assert kwargs["max_response_bytes"] <= 8 * 1024 * 1024
        if "play.google.com" in url:
            return response(
                url,
                '<title>Example App - Apps on Google Play</title><a href="https://publisher.example/about">Website</a><a href="mailto:support@publisher.example">Support email</a>',
            )
        if url.endswith("app-ads.txt"):
            return response(
                url,
                "OWNERDOMAIN=publisher.example\nMANAGERDOMAIN=manager.example\nmanager.example, s42, DIRECT\n",
            )
        return response(
            url,
            json.dumps(
                {
                    "contact_email": "partners@manager.example",
                    "sellers": [
                        {
                            "seller_id": "s42",
                            "name": "Example Publisher",
                            "domain": "publisher.example",
                            "seller_type": "PUBLISHER",
                        },
                        {"seller_id": "other", "name": "Different Publisher"},
                    ],
                }
            ),
        )

    client = SimpleNamespace(
        lookup=lambda **kw: {"status": "api_disabled", "profiles": []}
    )
    result = await PublisherLookupService(fetch).lookup(
        app_id="com.example.app", google_client=client
    )
    assert result["ads_txt"]["domain_source"] == "app_store_developer_website"
    assert result["app_store"]["support_contacts"] == ["support@publisher.example"]
    assert result["google_marketplace"]["status"] == "api_disabled"
    assert result["partial"] is True
    assert result["managers"][0]["seller_matches"][0]["name"] == "Example Publisher"
    assert len(result["managers"][0]["seller_matches"]) == 1
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_missing_manager_is_unknown_and_sellers_are_not_promoted():
    result = await PublisherLookupService(
        lambda url, **kw: response(url, "google.com,pub-999,DIRECT\n")
    ).lookup(domain="publisher.example")
    assert result["managers"] == []
    assert result["ads_txt"]["status"] == "ok"
    assert result["ads_txt"]["domain_source"] == "provided_domain"


@pytest.mark.asyncio
async def test_html_error_page_is_not_accepted_as_ads_txt():
    result = await PublisherLookupService(
        lambda url, **kw: response(url, "<!doctype html><html>Not found</html>")
    ).lookup(domain="publisher.example")
    assert result["ads_txt"]["status"] == "invalid_content"
    assert not result["managers"]


@pytest.mark.asyncio
async def test_unsafe_destination_is_reported_without_following_it():
    def blocked(url, **kwargs):
        raise UnsafePublicURL("URL hostname resolves to a non-public address")

    result = await PublisherLookupService(blocked).lookup(domain="internal.example")
    assert result["ads_txt"]["status"] == "unavailable"


@pytest.mark.asyncio
async def test_large_seller_list_is_explicitly_truncated_without_losing_manager():
    text = "\n".join(f"other.example, {i}, RESELLER" for i in range(700))
    text += "\nMANAGERDOMAIN=manager.example\nmanager.example, key, DIRECT\n"

    def fetch(url, **kw):
        return response(url, text if url.endswith("ads.txt") else '{"sellers": []}')

    result = await PublisherLookupService(fetch).lookup(domain="publisher.example")
    assert result["ads_txt"]["authorized_seller_count"] == 701
    assert result["ads_txt"]["sellers_truncated"]
    assert (
        result["ads_txt"]["authorized_sellers"][0]["advertising_system"]
        == "manager.example"
    )


@pytest.mark.asyncio
async def test_numeric_apple_id_uses_store_verified_developer_website():
    def fetch(url, **kw):
        if "itunes.apple.com" in url:
            return response(
                url,
                '{"results":[{"trackId":123,"trackName":"App","sellerName":"Owner","sellerUrl":"https://publisher.example"}]}',
            )
        return response(url, "google.com, pub-1, DIRECT")

    result = await PublisherLookupService(fetch).lookup(app_id="123")
    assert result["app_store"]["developer_name"] == "Owner"
    assert result["ads_txt"]["source_url"] == "https://publisher.example/app-ads.txt"


def test_google_pagination_and_disabled_api(monkeypatch):
    calls = []
    responses = [
        {"publisherProfiles": [{"displayName": "First"}], "nextPageToken": "next"},
        {"publisherProfiles": [{"displayName": "Second"}]},
    ]

    class Session:
        def __init__(self, credentials):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, url, **kwargs):
            calls.append((url, kwargs))
            return SimpleNamespace(ok=True, json=lambda: responses.pop(0))

    monkeypatch.setattr(
        google.google.auth, "default", lambda **kw: (object(), "project")
    )
    monkeypatch.setattr(google, "AuthorizedSession", Session)
    client = google.PublisherProfilesClient("123")
    result = client.lookup(app_id="com.example.app", domain=None)
    assert len(result["profiles"]) == 2
    assert calls[0][0].endswith("buyers/123/publisherProfiles")
    assert calls[1][1]["params"]["pageToken"] == "next"
    assert (
        calls[0][1]["params"]["filter"] == 'mobileApps.externalAppId: "com.example.app"'
    )
    monkeypatch.setattr(
        Session,
        "get",
        lambda *a, **kw: SimpleNamespace(
            ok=False,
            status_code=403,
            json=lambda: {
                "error": {
                    "message": "sensitive upstream text",
                    "details": [{"reason": "SERVICE_DISABLED"}],
                }
            },
        ),
    )
    result = client.lookup(app_id="com.example.app", domain=None)
    assert result["status"] == "api_disabled"
    assert "sensitive" not in json.dumps(result)


@pytest.mark.asyncio
async def test_google_joins_only_direct_google_accounts_and_preserves_basis():
    calls = []

    def lookup(**kwargs):
        calls.append(kwargs)
        return {
            "status": "ok",
            "profiles": [],
            "match_basis": "ads_txt_google_direct_account",
        }

    result = await PublisherLookupService(
        lambda url, **kw: response(
            url,
            "google.com,pub-123,DIRECT\ngoogle.com,pub-456,RESELLER\nother.example,pub-789,DIRECT",
        )
    ).lookup(domain="publisher.example", google_client=SimpleNamespace(lookup=lookup))
    assert calls[0]["publisher_codes"] == ["pub-123"]
    assert (
        result["google_marketplace"]["account_evidence_url"]
        == "https://publisher.example/ads.txt"
    )
    assert result["managers"] == []


@pytest.mark.asyncio
async def test_name_search_does_not_invent_an_app_association():
    calls = []

    def lookup(**kwargs):
        calls.append(kwargs)
        return {
            "status": "ok",
            "profiles": [{"displayName": "Agency"}],
            "match_basis": "publisher_name_search",
        }

    result = await PublisherLookupService(
        lambda *a, **kw: pytest.fail("name search must not fetch an inferred website")
    ).lookup(publisher_name="Agency", google_client=SimpleNamespace(lookup=lookup))
    assert calls[0]["publisher_name"] == "Agency"
    assert result["ads_txt"]["status"] == "not_requested"
    assert result["managers"] == []
    assert result["partial"] is False


@pytest.mark.asyncio
async def test_invalid_store_website_is_explicit():
    result = await PublisherLookupService(
        lambda url, **kw: response(url, '<a href="http://127.0.0.1">Website</a>')
    ).lookup(app_id="com.example.app")
    assert result["ads_txt"]["status"] == "invalid_developer_website"


def app_client(monkeypatch, *, allowed=True):
    app = FastAPI()
    app.include_router(routes.router)
    service = SimpleNamespace(lookup=AsyncMock(return_value={"managers": []}))
    app.dependency_overrides[get_current_user] = lambda: User(
        id="u", email="user@example.com", role="read"
    )
    app.dependency_overrides[get_store] = lambda: object()
    app.dependency_overrides[get_config] = lambda: SimpleNamespace(
        is_configured=lambda: False
    )
    app.dependency_overrides[routes.get_lookup_service] = lambda: service
    app.dependency_overrides[routes.get_lookup_seats_service] = lambda: object()

    async def access(*args, **kwargs):
        if not allowed:
            raise HTTPException(403, "Buyer access denied")

    monkeypatch.setattr(routes, "require_buyer_access", access)
    return app, service


def test_buyer_denial_happens_before_network_requests(monkeypatch):
    app, service = app_client(monkeypatch, allowed=False)
    client = SyncASGIClient(app)
    result = client.post(
        "/publisher-lookup",
        json={"buyer_id": "123", "app_id": "com.example.app", "include_google": False},
    )
    assert result.status_code == 403
    service.lookup.assert_not_awaited()


def test_app_input_validation_and_public_only_route(monkeypatch):
    app, service = app_client(monkeypatch)
    client = SyncASGIClient(app)
    assert client.post("/publisher-lookup", json={"buyer_id": "123"}).status_code == 422
    result = client.post(
        "/publisher-lookup",
        json={"buyer_id": "123", "app_id": "com.example.app", "include_google": False},
    )
    assert result.status_code == 200
    service.lookup.assert_awaited_once()


@pytest.mark.asyncio
async def test_linked_credentials_do_not_fall_back_or_mutate_seat():
    service = SimpleNamespace(lookup=AsyncMock(return_value={}))
    seats = SimpleNamespace(
        get_buyer_seat=AsyncMock(
            return_value=SimpleNamespace(active=True, service_account_id="linked")
        ),
        get_service_account=AsyncMock(return_value=None),
    )
    config = SimpleNamespace(
        is_configured=lambda: True,
        get_service_account_path=lambda: pytest.fail("wrong account fallback"),
    )
    await routes._lookup(
        PublisherLookupRequest(buyer_id="123", app_id="com.example.app"),
        service,
        seats,
        config,
    )
    assert service.lookup.await_args.kwargs["google_client"] is None
    assert service.lookup.await_args.kwargs["google_status"] == "credentials_missing"


@pytest.mark.parametrize(
    ("buyer_id", "buyer_ids"), [("123", None), (None, ["123", "456"])]
)
def test_agent_token_scope_and_buyer_enforced_before_fetch(
    monkeypatch, buyer_id, buyer_ids
):
    app, service = app_client(monkeypatch)
    context = SimpleNamespace(
        user=User(id="u", email="u@example.com", role="read"),
        token=SimpleNamespace(
            id="token", buyer_id=buyer_id, buyer_ids=buyer_ids, scopes=[]
        ),
    )

    @app.middleware("http")
    async def context_middleware(request, call_next):
        request.state.agent_auth_context = context
        return await call_next(request)

    app.dependency_overrides[routes.get_auth_service] = lambda: SimpleNamespace(
        log_audit=AsyncMock()
    )
    client = SyncASGIClient(app)
    body = {"buyer_id": "123", "app_id": "com.example.app", "include_google": False}
    assert client.post("/agent/v1/publisher-lookup", json=body).status_code == 403
    context.token.scopes = [AGENT_PUBLISHERS_READ_SCOPE]
    assert (
        client.post(
            "/agent/v1/publisher-lookup", json={**body, "buyer_id": "999"}
        ).status_code
        == 403
    )
    service.lookup.assert_not_awaited()
    assert client.post("/agent/v1/publisher-lookup", json=body).status_code == 200
    context.token.buyer_id = None
    context.token.buyer_ids = []
    service.lookup.reset_mock()
    assert client.post("/agent/v1/publisher-lookup", json=body).status_code == 403
    service.lookup.assert_not_awaited()


@pytest.mark.asyncio
async def test_mcp_forwards_publisher_lookup_and_bearer():
    from tests.mcp_server_test_support import MCPHarness, TOKEN_A

    observed = []

    async def upstream(request):
        observed.append(request)
        return httpx.Response(200, json={"managers": [], "checked_at": "now"})

    async with MCPHarness(upstream_transport=httpx.MockTransport(upstream)) as harness:
        message = await harness.call_tool(
            "rtbcat_lookup_publisher", {"buyer_id": "123", "app_id": "com.example.app"}
        )
        assert harness.tool_payload(message)["checked_at"] == "now"
    assert observed[0].url.path == "/agent/v1/publisher-lookup"
    assert observed[0].headers["authorization"] == f"Bearer {TOKEN_A}"
    assert json.loads(observed[0].content)["app_id"] == "com.example.app"
