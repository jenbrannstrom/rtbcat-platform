from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts" / "hetzner"
TERRAFORM_DIR = ROOT / "terraform" / "hetzner"

SCRIPTS = (
    SCRIPT_DIR / "configure_pgbackrest_s3.sh",
    SCRIPT_DIR / "verify_pgbackrest_backup.sh",
    SCRIPT_DIR / "create_pgbackrest_pitr_probe.sh",
    SCRIPT_DIR / "bootstrap_pgbackrest_restore_host.sh",
    SCRIPT_DIR / "restore_pgbackrest_pitr_drill.sh",
)


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda path: path.name)
def test_pgbackrest_scripts_parse_and_expose_help(script: Path) -> None:
    subprocess.run(["bash", "-n", str(script)], check=True)
    result = subprocess.run(
        ["bash", str(script), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Usage:" in result.stdout


def test_initial_backup_and_recurring_schedule_are_separate_gates() -> None:
    script = (SCRIPT_DIR / "configure_pgbackrest_s3.sh").read_text()

    assert "--start-full-backup" in script
    assert "--enable-backup-timers" in script
    assert 'systemctl start --no-block rtbcat-pgbackrest-full.service' in script
    assert "No successful full backup exists" in script
    assert "repo1-cipher-type=aes-256-cbc" in script
    assert "repo1-bundle=y" in script
    assert "repo1-block=y" in script
    assert "repo1-type=gcs" in script
    assert "repo1-gcs-key-type=service" in script
    assert "The GCS service key must be postgres-owned mode 0600" in script
    assert "active|activating|reloading|deactivating" in script
    assert "unit_is_running rtbcat-pgbackrest-full.service" in script


def test_restore_script_refuses_production_and_nonempty_clusters() -> None:
    script = (SCRIPT_DIR / "restore_pgbackrest_pitr_drill.sh").read_text()

    assert 'PRODUCTION_MARKER="/etc/rtbcat/database-host.env"' in script
    assert 'CONFIRM" != "DESTROY_EMPTY_RESTORE_DRILL_CLUSTER' in script
    assert "RTBCAT_RESTORE_DRILL_BOOTSTRAPPED=true" in script
    assert "pgdata_bytes > 1073741824" in script
    assert "--archive-mode=off" in script
    assert ".server.listen_addresses == \"127.0.0.1\"" in script
    assert 'POSTGRES_UNIT="postgresql@15-main.service"' in script
    assert 'systemctl start "$POSTGRES_UNIT"' in script
    assert "TARGET_TIME_POSTGRES" in script
    assert "--target=\"$TARGET_TIME_POSTGRES\"" in script
    assert "'+%Y-%m-%d %H:%M:%S.%6N+00'" in script


def test_restore_bootstrap_resume_is_bounded_to_a_small_fresh_cluster() -> None:
    script = (SCRIPT_DIR / "bootstrap_pgbackrest_restore_host.sh").read_text()

    assert 'PG_CONTROLDATA="/usr/lib/postgresql/15/bin/pg_controldata"' in script
    assert "pgdata_bytes <= 1073741824" in script
    assert 'grep -qx \'15\' "$PGDATA/PG_VERSION"' in script
    assert '[[ ! -e "$PGDATA/postmaster.pid" ]]' in script
    assert 'resume_fresh_cluster="true"' in script
    assert "max_connections = 100" in script


def test_restore_host_is_opt_in_and_uses_no_volume() -> None:
    variables = (TERRAFORM_DIR / "variables.tf").read_text()
    main = (TERRAFORM_DIR / "main.tf").read_text()
    cloud_init = (
        TERRAFORM_DIR / "cloud-init" / "pgbackrest-restore-drill.yaml.tftpl"
    ).read_text()

    variable_block = variables.split(
        'variable "enable_pgbackrest_restore_drill_host" {', maxsplit=1
    )[1].split("}", maxsplit=1)[0]
    assert "default     = false" in variable_block
    assert 'server_type = var.pgbackrest_restore_drill_server_type' in main
    assert 'resource "hcloud_volume" "pgbackrest_restore_drill"' not in main
    assert "RTBCAT_RESTORE_DRILL=true" in cloud_init
