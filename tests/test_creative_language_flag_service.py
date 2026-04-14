"""Unit tests for deterministic creative language and market flags."""

from __future__ import annotations

from types import SimpleNamespace

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
