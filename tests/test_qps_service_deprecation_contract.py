from __future__ import annotations

from services.qps_service import QpsService


def test_qps_summary_deprecation_contract_is_schema_compatible() -> None:
    payload = QpsService().get_summary()

    assert payload["total_rows"] == 0
    assert payload["unique_dates"] == 0
    assert payload["unique_billing_ids"] == 0
    assert payload["unique_sizes"] == 0
    assert payload["date_range"] == {"start": None, "end": None}
    assert payload["total_reached_queries"] == 0
    assert payload["total_impressions"] == 0
    assert payload["total_spend_usd"] == 0.0
    assert "rebuilt" in payload["message"].lower()


def test_qps_report_deprecation_payload_has_expected_fields() -> None:
    payload = QpsService().size_coverage_report(days=7)

    assert payload["analysis_days"] == 7
    assert "report" in payload
    assert "generated_at" in payload
