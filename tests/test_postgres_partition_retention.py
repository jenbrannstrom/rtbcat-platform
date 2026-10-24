import datetime as dt
import importlib.util
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("retention", Path(__file__).parents[1] / "scripts/hetzner/retain_postgres_partitions.py")
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def part(month, start, end):
    return {"name": "rtb_daily_" + month, "bounds": f"FOR VALUES FROM ('{start}') TO ('{end}')", "oid": 123, "bytes": 1}


class RetentionSafety(unittest.TestCase):
    def test_only_complete_expired_months(self):
        cutoff = dt.date(2026, 10, 24) - dt.timedelta(days=180)
        self.assertEqual(cutoff, dt.date(2026, 4, 27))
        self.assertTrue(module.expired(part("202603", "2026-03-01", "2026-04-01"), cutoff))
        self.assertFalse(module.expired(part("202604", "2026-04-01", "2026-05-01"), cutoff))

    def test_future_month_not_removed(self):
        self.assertFalse(module.expired(part("202612", "2026-12-01", "2027-01-01"), dt.date(2026, 4, 27)))

    def test_real_bounds_override_misleading_name(self):
        with self.assertRaises(ValueError):
            module.expired(part("202601", "2026-10-01", "2026-11-01"), dt.date(2026, 4, 27))

    def test_default_or_unexpected_partition_refused(self):
        with self.assertRaises(ValueError):
            module.expired({"name": "rtb_daily_default", "bounds": "DEFAULT"}, dt.date(2026, 4, 27))

    def test_boundary_and_year_rollover(self):
        self.assertTrue(module.expired(part("202512", "2025-12-01", "2026-01-01"), dt.date(2026, 1, 1)))

    def test_missing_or_disagreeing_policy_refused(self):
        for config in [[], [{"raw_retention_days": 30}], [{"raw_retention_days": 180}, {"raw_retention_days": 90}]]:
            with self.assertRaises(ValueError):
                module.retention_days(config, 180)

    def test_identical_existing_global_rows_supported(self):
        self.assertEqual(module.retention_days([{"raw_retention_days": 180}] * 3, 180), 180)

    def test_in_window_removal_never_issues_sql(self):
        with patch.object(module, "sql") as sql:
            with self.assertRaises(ValueError):
                module.remove_partition(part("202604", "2026-04-01", "2026-05-01"), dt.date(2026, 4, 27), 180)
            sql.assert_not_called()

    def test_archive_failure_prevents_removal(self):
        candidate = part("202603", "2026-03-01", "2026-04-01")
        with patch.object(module, "archive_partition", side_effect=RuntimeError("decode failed")):
            with patch.object(module, "remove_partition") as remove:
                with self.assertRaises(RuntimeError):
                    module.process_candidates([candidate], Path("/unused"), dt.date(2026, 4, 27), 180)
                remove.assert_not_called()

    def test_successful_archive_precedes_removal(self):
        candidate = part("202603", "2026-03-01", "2026-04-01")
        calls = []
        with patch.object(module, "archive_partition", side_effect=lambda *a: calls.append("archive")):
            with patch.object(module, "remove_partition", side_effect=lambda *a: calls.append("remove")):
                module.process_candidates([candidate], Path("/unused"), dt.date(2026, 4, 27), 180)
        self.assertEqual(calls, ["archive", "remove"])

    def test_dry_run_never_starts_backup_or_mutation(self):
        args = SimpleNamespace(apply=False, minimum_days=180, archive_volume=Path("/unused"))
        with patch.object(module.argparse.ArgumentParser, "parse_args", return_value=args):
            with patch.object(module, "inventory", return_value=(dt.date(2026, 10, 24), 180, dt.date(2026, 4, 27), [])):
                with patch.object(module, "process_candidates") as process, patch.object(module, "verify_backup") as backup, patch.object(module, "ensure_ahead") as ahead:
                    module.main()
                    process.assert_not_called()
                    backup.assert_not_called()
                    ahead.assert_not_called()


if __name__ == "__main__":
    unittest.main()
