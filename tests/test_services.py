"""Service layer tests with lightweight repo stubs."""

import pytest
from fastapi import HTTPException

from services.campaigns_service import CampaignsService
from services.creative_preview_service import CreativePreviewService
from services.creatives_service import CreativesService
from services.traffic_service import TrafficService
from storage.models import Creative


class DummyCampaignRepo:
    def __init__(self) -> None:
        self.calls = []

    async def list_campaigns(self, seat_id=None, status=None, limit=100, offset=0):
        self.calls.append(("list_campaigns", seat_id, status, limit, offset))
        return [
            {
                "id": "camp-1",
                "seat_id": seat_id,
                "name": "Test Campaign",
                "description": None,
                "ai_generated": True,
                "ai_confidence": None,
                "clustering_method": None,
                "status": status or "active",
                "created_at": None,
                "updated_at": None,
                "creative_count": 2,
            }
        ]


@pytest.mark.asyncio
async def test_campaigns_service_list_campaigns_maps_rows():
    repo = DummyCampaignRepo()
    svc = CampaignsService(repo=repo)

    result = await svc.list_campaigns(seat_id=123, status="active", limit=10, offset=5)

    assert len(result) == 1
    campaign = result[0]
    assert campaign.id == "camp-1"
    assert campaign.seat_id == 123
    assert campaign.status == "active"
    assert campaign.creative_count == 2
    assert repo.calls == [("list_campaigns", 123, "active", 10, 5)]


class DummyTrafficRepo:
    def __init__(self) -> None:
        self.rows = []

    async def upsert_traffic_row(self, canonical_size, raw_size, request_count, date, buyer_id):
        self.rows.append((canonical_size, raw_size, request_count, date, buyer_id))


@pytest.mark.asyncio
async def test_traffic_service_insert_rows_inserts_all():
    repo = DummyTrafficRepo()
    svc = TrafficService(repo=repo)

    records = [
        {
            "canonical_size": "300x250 (Medium Rectangle)",
            "raw_size": "300x250",
            "request_count": 100,
            "date": "2026-01-01",
            "buyer_id": "buyer-1",
        },
        {
            "canonical_size": "728x90 (Leaderboard)",
            "raw_size": "728x90",
            "request_count": 200,
            "date": "2026-01-01",
            "buyer_id": "buyer-1",
        },
    ]

    count = await svc.insert_rows(records)

    assert count == 2
    assert len(repo.rows) == 2
    assert repo.rows[0][0] == "300x250 (Medium Rectangle)"


@pytest.mark.asyncio
async def test_traffic_service_insert_rows_empty_rejected():
    svc = TrafficService(repo=DummyTrafficRepo())

    with pytest.raises(HTTPException) as exc:
        await svc.insert_rows([])

    assert exc.value.status_code == 400


class DummyCreativesRepo:
    async def get_newly_uploaded_creatives(self, **_kwargs):
        return [
            {
                "id": "c1",
                "name": "bidders/123/creatives/c1",
                "format": "HTML",
                "approval_status": "APPROVED",
                "width": 300,
                "height": 250,
                "canonical_size": "300x250 (Medium Rectangle)",
                "final_url": "https://example.com",
                "first_seen_at": "2026-01-01T00:00:00Z",
                "first_import_batch_id": "batch-1",
                "total_spend_micros": 2_000_000,
                "total_impressions": 10,
            }
        ]

    async def get_newly_uploaded_creatives_count(self, **_kwargs):
        return 1


@pytest.mark.asyncio
async def test_creatives_service_newly_uploaded_shape():
    svc = CreativesService(creatives_repo=DummyCreativesRepo())

    result = await svc.get_newly_uploaded_creatives(days=7, limit=100)

    assert result.total_count == 1
    assert len(result.creatives) == 1
    creative = result.creatives[0]
    assert creative["id"] == "c1"
    assert creative["total_spend_usd"] == 2.0


def test_creative_preview_video_fallback_uses_thumbnail_when_raw_data_omitted():
    svc = CreativePreviewService()
    creative = Creative(
        id="creative-video-1",
        name="bidders/123/creatives/creative-video-1",
        format="VIDEO",
    )

    preview = svc.build_preview(
        creative,
        slim=True,
        html_thumbnail_url="https://cdn.example.com/thumb.jpg",
    )

    assert preview["video"] is not None
    assert preview["video"]["thumbnail_url"] == "https://cdn.example.com/thumb.jpg"
    assert preview["video"]["video_url"] is None
    assert preview["video"]["vast_xml"] is None


def test_creative_preview_html_fallback_uses_thumbnail_when_raw_data_omitted():
    svc = CreativePreviewService()
    creative = Creative(
        id="creative-html-1",
        name="bidders/123/creatives/creative-html-1",
        format="HTML",
    )

    preview = svc.build_preview(
        creative,
        slim=True,
        html_thumbnail_url="https://cdn.example.com/html-thumb.jpg",
    )

    assert preview["html"] is not None
    assert preview["html"]["thumbnail_url"] == "https://cdn.example.com/html-thumb.jpg"
    assert preview["html"]["snippet"] is None
