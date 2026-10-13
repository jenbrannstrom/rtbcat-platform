"""build_config_row maps a Google pretargeting payload to a DB row."""

from __future__ import annotations

import json

from services.pretargeting_service import build_config_row


def test_build_config_row_maps_google_payload():
    row = build_config_row(1487810529, {
        "configId": "cfg-1",
        "billingId": " 198363911721 ",
        "displayName": "US+CAN_CTV",
        "state": "ACTIVE",
        "maximumQps": "15000",
        "includedFormats": ["VIDEO"],
        "includedPlatforms": ["CONNECTED_TV"],
        "includedCreativeDimensions": [{"width": 1920, "height": 1080}, {"width": 0, "height": 5}],
        "geoTargeting": {"includedIds": ["2840"], "excludedIds": ["2124"]},
        "includedMobileOperatingSystemIds": ["30001"],
    })

    assert row["bidder_id"] == "1487810529"
    assert row["config_id"] == "cfg-1"
    assert row["billing_id"] == "198363911721"
    assert row["display_name"] == "US+CAN_CTV"
    assert row["state"] == "ACTIVE"
    assert json.loads(row["included_formats"]) == ["VIDEO"]
    assert json.loads(row["included_platforms"]) == ["CONNECTED_TV"]
    assert json.loads(row["included_sizes"]) == ["1920x1080"]
    assert json.loads(row["included_geos"]) == ["2840"]
    assert json.loads(row["excluded_geos"]) == ["2124"]
    assert json.loads(row["included_operating_systems"]) == ["30001"]
    assert json.loads(row["raw_config"])["maximumQps"] == "15000"


def test_build_config_row_handles_sparse_payload():
    row = build_config_row("b", {"configId": "cfg-2"})

    assert row["billing_id"] is None
    assert row["state"] == "ACTIVE"
    assert row["included_operating_systems"] is None
    assert json.loads(row["included_sizes"]) == []
    assert json.loads(row["included_geos"]) == []
