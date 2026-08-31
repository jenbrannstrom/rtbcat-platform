"""A 0-QPS RTB endpoint must display as 0, never "Unlimited".

Google's ``Endpoint.maximumQps`` is a proto3 int64 scalar, so a 0 cap is
*omitted* from the JSON response rather than sent as "0". The collector used
to map that absence to None, the DB stored NULL, and the dashboard rendered
null as "Unlimited" -- but RTB endpoints have no unlimited mode. These tests
lock in: absent -> 0 at parse time, and NULL -> 0 when serving rows synced
before that fix.
"""

from __future__ import annotations

import pytest

from api.routers.settings import endpoints as endpoints_router
from collectors.endpoints.client import parse_endpoint_response


def _raw(**overrides):
    base = {
        "name": "bidders/123/endpoints/456",
        "url": "https://dsp-test.example.com/google/bid",
        "tradingLocation": "US_EAST",
        "bidProtocol": "OPENRTB_2_5",
    }
    base.update(overrides)
    return base


class TestParseEndpointResponse:
    def test_absent_maximum_qps_is_zero_not_none(self):
        parsed = parse_endpoint_response(_raw())
        assert parsed["maximumQps"] == 0
        assert parsed["maximumQps"] is not None

    def test_string_zero_is_zero(self):
        assert parse_endpoint_response(_raw(maximumQps="0"))["maximumQps"] == 0

    def test_int64_string_is_parsed(self):
        assert parse_endpoint_response(_raw(maximumQps="500"))["maximumQps"] == 500

    def test_malformed_value_is_none(self):
        assert parse_endpoint_response(_raw(maximumQps="lots"))["maximumQps"] is None


class TestBuildEndpointItems:
    def test_legacy_null_row_serves_as_zero(self):
        rows = [
            {
                "endpoint_id": "ep-0",
                "url": "https://dsp-test.example.com/google/bid",
                "maximum_qps": None,  # synced before absent->0 normalisation
                "trading_location": "US_EAST",
                "bid_protocol": "OPENRTB_2_5",
                "synced_at": "2026-08-30T00:00:00+00:00",
            },
            {
                "endpoint_id": "ep-1",
                "url": "https://dsp.example.com/google/bid",
                "maximum_qps": 250,
                "trading_location": "US_WEST",
                "bid_protocol": "OPENRTB_2_5",
                "synced_at": "2026-08-31T00:00:00+00:00",
            },
        ]
        items, total, synced_at = endpoints_router._build_endpoint_items(rows)
        by_id = {item.endpoint_id: item for item in items}
        assert by_id["ep-0"].maximum_qps == 0
        assert by_id["ep-1"].maximum_qps == 250
        assert total == 250
        assert synced_at == "2026-08-31T00:00:00+00:00"

    def test_live_api_dict_without_maximum_qps_serves_as_zero(self):
        items, total, _ = endpoints_router._build_endpoint_items(
            [{"endpointId": "ep-0", "url": "https://x", "tradingLocation": "ASIA"}]
        )
        assert items[0].maximum_qps == 0
        assert total == 0

    def test_response_never_serialises_null_qps(self):
        items, _, _ = endpoints_router._build_endpoint_items(
            [{"endpoint_id": "ep-0", "url": "https://x", "maximum_qps": None}]
        )
        assert items[0].model_dump()["maximum_qps"] == 0


@pytest.mark.parametrize("value,expected", [(None, 0), ("0", 0), (0, 0), ("125", 125), (7, 7), ("bad", 0)])
def test_qps_or_zero(value, expected):
    assert endpoints_router._qps_or_zero(value) == expected
