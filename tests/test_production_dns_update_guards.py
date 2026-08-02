"""Guards for the exact-record Cloudflare DNS update path."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "hetzner" / "update_production_dns.sh"


def script_text() -> str:
    return SCRIPT.read_text()


def test_dns_script_parses_and_exposes_check_only_usage() -> None:
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True)
    result = subprocess.run(
        ["bash", str(SCRIPT), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Read-only record preflight" in result.stdout
    assert "UPDATE_SCAN_RTB_CAT_A_RECORD" in result.stdout


def test_dns_script_is_restricted_and_exact_match_guarded() -> None:
    text = script_text()
    for required in (
        'if [[ "$HOSTNAME" != "scan.rtb.cat" ]]',
        "(.result | length) == 1",
        '.content == $current',
        '.proxied == false',
        '"$CONFIRM" != "UPDATE_SCAN_RTB_CAT_A_RECORD"',
        "--request PATCH",
        "write_receipt prepared false null",
        "read-after-write verification failed",
    ):
        assert required in text

    assert "--request POST" not in text
    assert "--request DELETE" not in text


def test_dns_receipt_contains_rollback_and_is_private() -> None:
    text = script_text()
    assert "rollback:" in text
    assert 'expected_current_ip: $new_ip' in text
    assert 'new_ip: $expected_current_ip' in text
    assert 'install -m 0600 "$receipt_tmp" "$JSON_OUT"' in text
    assert 'if [[ -L "$JSON_OUT" ]]' in text


def test_dns_token_is_never_written_to_receipt() -> None:
    text = script_text()
    receipt = text[
        text.index("write_receipt()") : text.index('if [[ "$APPLY" != "true" ]]')
    ]
    assert "auth_header" not in receipt
    assert "token:" not in receipt


def test_dns_check_only_writes_private_recovery_receipt(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_curl = fake_bin / "curl"
    fake_curl.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' '{\"success\":true,\"errors\":[],\"result\":["
        "{\"id\":\"record-id\",\"type\":\"A\","
        "\"name\":\"scan.rtb.cat\",\"content\":\"192.0.2.10\","
        "\"ttl\":300,\"proxied\":false}]}'\n"
    )
    fake_curl.chmod(0o755)
    receipt = tmp_path / "dns-preflight.json"
    env = os.environ | {
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "CLOUDFLARE_API_TOKEN": "test-token-not-for-output",
        "CLOUDFLARE_ZONE_ID": "a" * 32,
    }

    result = subprocess.run(
        [
            "bash",
            str(SCRIPT),
            "--hostname",
            "scan.rtb.cat",
            "--expected-current-ip",
            "192.0.2.10",
            "--new-ip",
            "192.0.2.20",
            "--json-out",
            str(receipt),
        ],
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert receipt.stat().st_mode & 0o777 == 0o600
    report = json.loads(receipt.read_text())
    assert report["status"] == "accepted"
    assert report["applied"] is False
    assert report["before"]["content"] == "192.0.2.10"
    assert report["rollback"] == {
        "expected_current_ip": "192.0.2.20",
        "new_ip": "192.0.2.10",
    }
    assert "test-token-not-for-output" not in receipt.read_text()
