"""Unit tests for deterministic creative language and market flags."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from services.creative_countries_service import CreativeCountriesService
from services.creative_language_flag_service import build_creative_language_flag_row


def test_build_creative_language_flag_row_flags_english_aed_in_ph() -> None:
    creative = SimpleNamespace(
        id="1987702299778854923",
        name="AED free shipping creative",
        buyer_id="1487810529",
        format="HTML",
        approval_status="APPROVED",
        advertiser_name=None,
        detected_language=None,
        detected_language_code=None,
        raw_data={
          "html": {
            "snippet": """
              <div>
                Only for new app users with qualifying orders
                AED 0
                FREE SHIPPING
              </div>
            """
          }
        },
    )

    row = build_creative_language_flag_row(
        creative=creative,
        serving_countries=["PH"],
        latest_geo_run=None,
    )

    assert row["heuristic_language_code"] == "en"
    assert row["language_flag_status"] == "orange"
    assert "English creative serving in PHL" == row["language_flag_reason"]
    assert row["currency_flag_status"] == "red"
    assert "AED" in row["detected_currencies"]
    assert row["currency_flag_reason"] == "Currency AED conflicts with PHL"
    assert row["geo_linguistic_status"] == "red"
    assert row["geo_linguistic_decision"] == "heuristic_currency_mismatch"


def test_currency_mismatch_overrides_ai_match() -> None:
    creative = SimpleNamespace(
        id="creative-2",
        name="currency conflict",
        buyer_id="1487810529",
        format="HTML",
        approval_status="APPROVED",
        advertiser_name=None,
        detected_language="English",
        detected_language_code="en",
        raw_data={"html": {"snippet": "AED 99 free shipping"}},
    )

    row = build_creative_language_flag_row(
        creative=creative,
        serving_countries=["PH"],
        latest_geo_run={
            "status": "completed",
            "result": {"decision": "match"},
        },
    )

    assert row["geo_linguistic_status"] == "red"
    assert row["geo_linguistic_reason"] == "Currency AED conflicts with PHL (overrides AI match)"


def test_build_creative_language_flag_row_normalizes_country_names() -> None:
    creative = SimpleNamespace(
        id="2014265280192819202",
        name="Hindi India creative",
        buyer_id="1487810529",
        format="HTML",
        approval_status="APPROVED",
        advertiser_name=None,
        detected_language="Hindi",
        detected_language_code="hi",
        raw_data={"html": {"snippet": "<div>हिंदी ऑफर</div>"}},
    )

    row = build_creative_language_flag_row(
        creative=creative,
        serving_countries=["INDIA"],
        latest_geo_run=None,
    )

    assert row["serving_countries"] == ["IN"]
    assert row["language_flag_status"] == "green"
    assert row["language_flag_reason"] == "HI matches IND"
    assert row["currency_flag_status"] == "orange"
    assert row["currency_flag_reason"] == "No obvious market currency detected"


def test_build_creative_language_flag_row_surfaces_geo_secondary_language_finding() -> None:
    creative = SimpleNamespace(
        id="2028723258945941508",
        name="Mixed CTA creative",
        buyer_id="1487810529",
        format="NATIVE",
        approval_status="APPROVED",
        advertiser_name=None,
        detected_language="English",
        detected_language_code="en",
        raw_data={
            "native": {
                "headline": "Earn rewards",
                "body": "Best rewards app",
                "callToAction": "instalar",
            }
        },
    )

    row = build_creative_language_flag_row(
        creative=creative,
        serving_countries=["PH"],
        latest_geo_run={
            "status": "completed",
            "result": {
                "decision": "needs_review",
                "primary_languages": ["English"],
                "secondary_languages": ["Spanish"],
                "findings": [
                    {
                        "category": "language_mismatch",
                        "description": "Spanish word 'instalar' (install) mixed into English-dominant creative served to Philippines",
                    }
                ],
            },
        },
    )

    assert row["geo_linguistic_status"] == "orange"
    assert row["geo_linguistic_reason"] == (
        "Spanish word 'instalar' (install) mixed into English-dominant creative served to Philippines"
    )


def test_build_creative_language_flag_row_flags_spanish_cta_in_english_native_copy() -> None:
    creative = SimpleNamespace(
        id="2013919535262576642",
        name="English body Spanish CTA",
        buyer_id="1487810529",
        format="NATIVE",
        approval_status="APPROVED",
        advertiser_name=None,
        detected_language="English",
        detected_language_code="en",
        raw_data={
            "native": {
                "headline": "Benjamin - Earn Cash Rewards",
                "body": "Benjamin: The Best Money Stacking App!",
                "callToAction": "instalar",
            }
        },
    )

    row = build_creative_language_flag_row(
        creative=creative,
        serving_countries=["INDIA"],
        latest_geo_run=None,
    )

    assert row["serving_countries"] == ["IN"]
    assert row["language_flag_status"] == "red"
    assert row["language_flag_source"] == "plaintext_fields"
    assert row["language_flag_reason"] == (
        "Spanish CTA 'instalar' mixed into English creative serving in IND"
    )
    assert row["plaintext_language_summary"] == (
        "Primary plaintext: English · CTA: Spanish ('instalar')"
    )
    assert row["primary_text_language_code"] == "en"
    assert row["secondary_text_language_code"] == "es"
    assert row["secondary_text_sample"] == "instalar"


class _PerfService:
    async def get_country_breakdown(self, creative_id: str, days: int):
        del creative_id, days
        return [
            {"country_code": "INDIA", "spend_micros": 5_000_000, "impressions": 1000, "clicks": 20},
            {"country_code": "IN", "spend_micros": 3_000_000, "impressions": 500, "clicks": 10},
        ]


@pytest.mark.asyncio
async def test_build_country_metrics_normalizes_and_aggregates_country_names() -> None:
    service = CreativeCountriesService(perf_service=_PerfService())

    payload = await service.build_country_metrics("2014265280192819202", 7)

    assert payload["total_countries"] == 1
    assert payload["countries"] == [
        {
            "country_code": "IN",
            "country_name": "India",
            "country_iso3": "IND",
            "spend_micros": 8_000_000,
            "impressions": 1500,
            "clicks": 30,
            "spend_percent": 100.0,
        }
    ]
