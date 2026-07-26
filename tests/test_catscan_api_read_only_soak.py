from __future__ import annotations

from scripts.catscan_api_read_only_soak import (
    CONTRACTS,
    Observation,
    build_auth_headers,
    changed_json_paths,
    runtime_identity,
    schema_sha256,
    summarize,
)


def _observation(
    *,
    duration_ms: float,
    body_hash: str = "same",
    schema_hash: str = "schema",
    shadow_header: str | None = None,
) -> dict:
    return vars(
        Observation(
            status=200,
            duration_ms=duration_ms,
            response_bytes=10,
            body_sha256=body_hash,
            schema_sha256=schema_hash,
            json_valid=True,
            shadow_header=shadow_header,
            error_type=None,
        )
    )


def test_contract_catalog_is_get_only_and_matches_rehearsed_read_set() -> None:
    assert len(CONTRACTS) == 15
    assert {contract.name for contract in CONTRACTS} == {
        "health",
        "stats",
        "sizes",
        "seats",
        "spend_90d",
        "rtb_funnel_90d",
        "publishers_90d_limit_100",
        "geos_90d_limit_100",
        "configs_30d",
        "home_funnel_90d_limit_200",
        "home_configs_30d",
        "endpoint_efficiency_90d",
        "data_health_90d_limit_1000",
        "qps_summary_90d",
        "creatives_v2_limit_200",
    }
    assert all(contract.path.startswith("/") for contract in CONTRACTS)


def test_schema_hash_ignores_values_order_and_list_length() -> None:
    first = {"rows": [{"buyer": "one", "spend": 1}, {"buyer": "two", "spend": 2}]}
    second = {"rows": [{"spend": 999, "buyer": "different"}]}

    assert schema_sha256(first) == schema_sha256(second)


def test_changed_paths_do_not_include_values() -> None:
    source = {"rows": [{"buyer_id": "secret-buyer", "spend": 100}]}
    target = {"rows": [{"buyer_id": "other-secret", "spend": 99}]}

    paths = changed_json_paths(source, target)

    assert paths == ["$.rows[0].buyer_id", "$.rows[0].spend"]
    serialized = str(paths)
    assert "secret-buyer" not in serialized
    assert "100" not in serialized


def test_auth_header_auto_selects_email_or_bearer() -> None:
    assert build_auth_headers("person@example.com", "auto") == {
        "X-Email": "person@example.com"
    }
    assert build_auth_headers("opaque-token", "auto") == {
        "Authorization": "Bearer opaque-token"
    }


def test_runtime_identity_keeps_only_safe_health_revision_fields() -> None:
    assert runtime_identity(
        {
            "release_version": "0.9.5",
            "version": "sha-example",
            "git_sha": "example",
            "has_credentials": True,
            "secret": "must-not-appear",
        }
    ) == {
        "release_version": "0.9.5",
        "version": "sha-example",
        "git_sha": "example",
    }


def test_summary_separates_failures_result_drift_and_latency() -> None:
    run = {
        "contracts": [
            {
                "name": "stats",
                "source": _observation(duration_ms=20),
                "target": _observation(
                    duration_ms=10,
                    body_hash="different",
                    shadow_header="read-only",
                ),
                "result_match": False,
                "schema_match": True,
            }
        ]
    }

    summary = summarize([run], started_at="2026-07-25T00:00:00Z")

    assert summary["source_request_failures"] == 0
    assert summary["target_request_failures"] == 0
    assert summary["target_shadow_header_failures"] == 0
    assert summary["exact_result_mismatches"] == 1
    assert summary["schema_mismatches"] == 0
    assert summary["contracts"]["stats"]["source_latency_ms"]["p95"] == 20
    assert summary["contracts"]["stats"]["target_latency_ms"]["p95"] == 10
