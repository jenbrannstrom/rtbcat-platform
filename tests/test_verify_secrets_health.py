"""Tests for scripts/verify_secrets_health.sh exit-code semantics.

These tests mock docker commands to verify the verifier script produces
the correct exit codes without requiring a running container.
"""

from __future__ import annotations

import json
import os
import subprocess
import stat
import textwrap

import pytest

SCRIPT_PATH = os.path.join(
    os.path.dirname(__file__), os.pardir, "scripts", "verify_secrets_health.sh"
)

# Sample payloads matching get_secrets_health() output
HEALTHY_PAYLOAD = {
    "checked_at": "2026-03-05T00:00:00+00:00",
    "strict_mode": False,
    "healthy": True,
    "backend": "env",
    "prefer_env": True,
    "name_prefix": "",
    "summary": {
        "enabled_features": 3,
        "required_keys": 5,
        "configured_keys": 5,
        "missing_keys": 0,
    },
    "missing_required_keys": [],
    "features": [],
}

UNHEALTHY_PAYLOAD = {
    "checked_at": "2026-03-05T00:00:00+00:00",
    "strict_mode": True,
    "healthy": False,
    "backend": "env",
    "prefer_env": True,
    "name_prefix": "",
    "summary": {
        "enabled_features": 3,
        "required_keys": 5,
        "configured_keys": 3,
        "missing_keys": 2,
    },
    "missing_required_keys": ["GMAIL_IMPORT_SECRET", "CREATIVE_CACHE_REFRESH_SECRET"],
    "features": [],
}


@pytest.fixture()
def mock_env(tmp_path):
    """Create a mock environment where 'docker' is a stub script.

    Yields a helper to configure the stub behavior.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()

    class MockDocker:
        def __init__(self):
            self._inspect_exit = 0
            self._inspect_status = "running"
            self._exec_exit = 0
            self._exec_output = json.dumps(HEALTHY_PAYLOAD)

        def set_container_missing(self):
            self._inspect_exit = 1

        def set_container_stopped(self):
            self._inspect_status = "exited"

        def set_exec_output(self, payload: dict):
            self._exec_output = json.dumps(payload)

        def set_exec_fail(self):
            self._exec_exit = 1
            self._exec_output = "ImportError: No module named 'services'"

        def write_stub(self):
            stub = bin_dir / "docker"
            # The stub handles: docker inspect, docker inspect -f, docker exec
            stub.write_text(textwrap.dedent(f"""\
                #!/bin/bash
                if [[ "$1" == "inspect" && "$2" == "-f" ]]; then
                    if [ {self._inspect_exit} -ne 0 ]; then exit 1; fi
                    echo "{self._inspect_status}"
                    exit 0
                fi
                if [[ "$1" == "inspect" ]]; then
                    if [ {self._inspect_exit} -ne 0 ]; then
                        echo "Error: No such container" >&2
                        exit 1
                    fi
                    exit 0
                fi
                if [[ "$1" == "exec" ]]; then
                    if [ {self._exec_exit} -ne 0 ]; then
                        echo '{self._exec_output}' >&2
                        exit 1
                    fi
                    echo '{self._exec_output}'
                    exit 0
                fi
                echo "mock docker: unknown command $*" >&2
                exit 1
            """))
            stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
            return stub

    mock = MockDocker()
    return mock, bin_dir, tmp_path


def _run_verifier(bin_dir, tmp_path, extra_args=None):
    """Run the verifier script with the mock docker on PATH."""
    env = os.environ.copy()
    env["PATH"] = str(bin_dir) + ":" + env.get("PATH", "")
    cmd = ["bash", SCRIPT_PATH, "--container", "test-container"]
    if extra_args:
        cmd.extend(extra_args)
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(tmp_path),
        timeout=10,
    )
    return result


class TestVerifierExitCodes:
    """Verify exit code semantics: 0=healthy, 2=unavailable, 3=unhealthy."""

    def test_healthy_exits_0(self, mock_env):
        mock, bin_dir, tmp_path = mock_env
        mock.set_exec_output(HEALTHY_PAYLOAD)
        mock.write_stub()
        result = _run_verifier(bin_dir, tmp_path)
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
        assert "HEALTHY" in result.stdout

    def test_unhealthy_exits_3(self, mock_env):
        mock, bin_dir, tmp_path = mock_env
        mock.set_exec_output(UNHEALTHY_PAYLOAD)
        mock.write_stub()
        result = _run_verifier(bin_dir, tmp_path)
        assert result.returncode == 3, f"stdout: {result.stdout}\nstderr: {result.stderr}"
        assert "UNHEALTHY" in result.stdout
        assert "GMAIL_IMPORT_SECRET" in result.stdout

    def test_container_missing_exits_2(self, mock_env):
        mock, bin_dir, tmp_path = mock_env
        mock.set_container_missing()
        mock.write_stub()
        result = _run_verifier(bin_dir, tmp_path)
        assert result.returncode == 2, f"stdout: {result.stdout}\nstderr: {result.stderr}"
        assert "PROBE_UNAVAILABLE" in result.stdout

    def test_container_stopped_exits_2(self, mock_env):
        mock, bin_dir, tmp_path = mock_env
        mock.set_container_stopped()
        mock.write_stub()
        result = _run_verifier(bin_dir, tmp_path)
        assert result.returncode == 2, f"stdout: {result.stdout}\nstderr: {result.stderr}"
        assert "PROBE_UNAVAILABLE" in result.stdout

    def test_exec_failure_exits_2(self, mock_env):
        mock, bin_dir, tmp_path = mock_env
        mock.set_exec_fail()
        mock.write_stub()
        result = _run_verifier(bin_dir, tmp_path)
        assert result.returncode == 2, f"stdout: {result.stdout}\nstderr: {result.stderr}"
        assert "PROBE_UNAVAILABLE" in result.stdout


class TestVerifierJsonOutput:
    """Verify --json-out writes the probe payload."""

    def test_json_out_written_on_healthy(self, mock_env):
        mock, bin_dir, tmp_path = mock_env
        mock.set_exec_output(HEALTHY_PAYLOAD)
        mock.write_stub()
        json_path = tmp_path / "secrets_health.json"
        result = _run_verifier(bin_dir, tmp_path, ["--json-out", str(json_path)])
        assert result.returncode == 0
        assert json_path.exists()
        data = json.loads(json_path.read_text())
        assert data["healthy"] is True

    def test_json_out_written_on_unhealthy(self, mock_env):
        mock, bin_dir, tmp_path = mock_env
        mock.set_exec_output(UNHEALTHY_PAYLOAD)
        mock.write_stub()
        json_path = tmp_path / "secrets_health.json"
        result = _run_verifier(bin_dir, tmp_path, ["--json-out", str(json_path)])
        assert result.returncode == 3
        assert json_path.exists()
        data = json.loads(json_path.read_text())
        assert data["healthy"] is False


class TestVerifierSecurityGuardrails:
    """Verify no secret values leak in output."""

    def test_no_secret_values_in_stdout(self, mock_env):
        mock, bin_dir, tmp_path = mock_env
        mock.set_exec_output(UNHEALTHY_PAYLOAD)
        mock.write_stub()
        result = _run_verifier(bin_dir, tmp_path)
        # The output should mention key NAMES but never contain actual secret values.
        # Since our mock doesn't include values, check that the output only contains
        # expected key-name references and status fields.
        assert "GMAIL_IMPORT_SECRET" in result.stdout  # key name is OK
        assert "CREATIVE_CACHE_REFRESH_SECRET" in result.stdout  # key name is OK
        # Should not contain raw JSON dump of features array
        assert '"configured": true' not in result.stdout

    def test_strict_flag_informational(self, mock_env):
        mock, bin_dir, tmp_path = mock_env
        mock.set_exec_output(HEALTHY_PAYLOAD)
        mock.write_stub()
        result = _run_verifier(bin_dir, tmp_path, ["--strict"])
        assert result.returncode == 0
        assert "verify_strict_flag=true" in result.stdout
