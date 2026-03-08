import json
from pathlib import Path

from scripts.render_v1_closeout_summary import build_summary_markdown, main


def test_build_summary_markdown_with_payload():
    payload = {
        "branch": "main",
        "commit": "abc1234",
        "profile": "quick",
        "timestamp_utc": "2026-03-01 00:00:00 UTC",
        "steps": [
            {"step": "Phase 0 regression", "status": "PASS", "notes": "command succeeded"},
            {"step": "Deployed canary", "status": "BLOCKED", "notes": "network | policy"},
        ],
    }
    markdown = build_summary_markdown("V1 Closeout Quick Report", payload, Path("/tmp/unused.json"))

    assert "## V1 Closeout Quick Report" in markdown
    assert "- branch: `main`" in markdown
    assert "| Phase 0 regression | PASS | command succeeded |" in markdown
    assert "| Deployed canary | BLOCKED | network \\| policy |" in markdown


def test_build_summary_markdown_with_missing_payload():
    markdown = build_summary_markdown("Missing Report", None, Path("/tmp/missing.json"))
    assert "## Missing Report" in markdown
    assert "- report missing: `/tmp/missing.json`" in markdown


def test_main_writes_summary_from_report_json(monkeypatch, tmp_path: Path):
    report_path = tmp_path / "closeout.json"
    summary_path = tmp_path / "summary.md"
    report_path.write_text(
        json.dumps(
            {
                "branch": "main",
                "commit": "def5678",
                "profile": "deployed_only",
                "timestamp_utc": "2026-03-01 00:00:00 UTC",
                "steps": [{"step": "Deployed canary go/no-go", "status": "PASS", "notes": "ok"}],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_path))
    monkeypatch.setattr(
        "sys.argv",
        [
            "render_v1_closeout_summary.py",
            "--report-json",
            str(report_path),
            "--title",
            "V1 Closeout Deployed Report",
        ],
    )

    assert main() == 0

    output = summary_path.read_text(encoding="utf-8")
    assert "## V1 Closeout Deployed Report" in output
    assert "- profile: `deployed_only`" in output
    assert "| Deployed canary go/no-go | PASS | ok |" in output
