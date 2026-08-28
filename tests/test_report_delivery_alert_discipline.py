"""Human-alert policy for the Authorized Buyers delivery watchdog."""

from datetime import date

from scripts.check_report_delivery import CANONICAL_KIND, render_alert_body


METRIC_DATE = date(2026, 8, 26)
DELIVERY_DATE = date(2026, 8, 27)


def test_daily_restatements_are_silent() -> None:
    body = render_alert_body(
        METRIC_DATE,
        DELIVERY_DATE,
        [],
        [],
        {"6574658621": ["2026-08-21", "2026-08-22"]},
    )

    assert body is None


def test_non_actionable_missing_reports_are_silent() -> None:
    body = render_alert_body(
        METRIC_DATE,
        DELIVERY_DATE,
        [
            ("6574658621", CANONICAL_KIND, True),
            ("6574658621", "catscan-secondary", False),
        ],
        [],
        {"6574658621": ["2026-08-21"]},
    )

    assert body is None


def test_missing_money_email_and_rows_remains_actionable() -> None:
    body = render_alert_body(
        METRIC_DATE,
        DELIVERY_DATE,
        [("6574658621", CANONICAL_KIND, False)],
        ["6574658621"],
        {"6574658621": ["2026-08-21"]},
    )

    assert body is not None
    assert "MONEY report email did not arrive" in body
    assert "re-run the saved report" in body
    assert "re-sent money reports for earlier days" not in body


def test_arrived_email_without_money_rows_remains_actionable() -> None:
    body = render_alert_body(
        METRIC_DATE,
        DELIVERY_DATE,
        [],
        ["6574658621"],
        {},
    )

    assert body is not None
    assert "email arrived but no spend numbers" in body
    assert "import may have failed" in body
