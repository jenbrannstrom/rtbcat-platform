"""Fraud Signal Detector for QPS Optimization.

Flags suspicious patterns for HUMAN REVIEW. Does NOT definitively identify fraud.

Important limitations:
- VPNs make geographic analysis unreliable
- Smart fraudsters mix 70-80% real traffic with 20-30% fake
- Pure fraud gets caught by Google's systems
- We can only detect patterns over time

Example:
    >>> from qps.fraud_detector import FraudSignalDetector
    >>> detector = FraudSignalDetector()
    >>> report = detector.generate_report(days=14)
    >>> print(report)
"""

import sqlite3
import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass

from qps.models import FraudSignal

logger = logging.getLogger(__name__)

DB_PATH = os.path.expanduser("~/.catscan/catscan.db")


@dataclass
class FraudReport:
    """Complete fraud signal detection report."""

    signals: List[FraudSignal]
    high_ctr_signals: int
    clicks_exceed_signals: int
    total_suspicious_apps: int
    analysis_days: int
    generated_at: str


class FraudSignalDetector:
    """Detects suspicious patterns in traffic data for human review."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    def detect_high_ctr(self, days: int = 14, ctr_threshold: float = 3.0) -> List[FraudSignal]:
        """
        Detect apps with abnormally high CTR.

        Note: High CTR alone is not proof of fraud. Could be:
        - Very engaging content
        - Well-targeted audience
        - Or yes, click fraud

        Flags for human review, not automatic blocking.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        signals: List[FraudSignal] = []

        try:
            cursor.execute("""
                SELECT
                    app_id,
                    app_name,
                    SUM(COALESCE(impressions, 0)) as total_impressions,
                    SUM(COALESCE(clicks, 0)) as total_clicks,
                    COUNT(DISTINCT metric_date) as days_active
                FROM rtb_daily
                WHERE metric_date >= ?
                  AND app_id IS NOT NULL
                  AND app_id != ''
                GROUP BY app_id, app_name
                HAVING SUM(COALESCE(impressions, 0)) > 100 AND SUM(COALESCE(clicks, 0)) > 0
            """, (cutoff_date,))

            for row in cursor.fetchall():
                app_id = row[0] or "unknown"
                app_name = row[1] or app_id
                impressions = row[2] or 0
                clicks = row[3] or 0
                days_active = row[4] or 0

                if impressions <= 0:
                    continue

                ctr = (clicks / impressions) * 100

                if ctr > ctr_threshold:
                    strength = "HIGH" if ctr > 5.0 else "MEDIUM"
                    signals.append(FraudSignal(
                        entity_type="app",
                        entity_id=app_id,
                        entity_name=app_name,
                        signal_type="high_ctr",
                        signal_strength=strength,
                        evidence={
                            "ctr_pct": round(ctr, 2),
                            "impressions": impressions,
                            "clicks": clicks,
                            "expected_ctr_pct": 0.5,
                        },
                        days_observed=days_active,
                        recommendation=f"Review - CTR {ctr:.1f}% is {ctr/0.5:.0f}x average",
                    ))

        finally:
            conn.close()

        return signals

    def detect_clicks_exceed_impressions(self, days: int = 14) -> List[FraudSignal]:
        """
        Detect cases where clicks > impressions.

        Note: This can be legitimate (timing across midnight) or fraud.
        Single occurrences are usually timing. Repeated patterns are suspicious.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        signals: List[FraudSignal] = []

        try:
            # Find apps/sizes where clicks > impressions on multiple days
            cursor.execute("""
                SELECT
                    app_id,
                    app_name,
                    COUNT(*) as total_days,
                    SUM(CASE WHEN COALESCE(clicks, 0) > COALESCE(impressions, 0) THEN 1 ELSE 0 END) as violation_days,
                    SUM(COALESCE(clicks, 0)) as total_clicks,
                    SUM(COALESCE(impressions, 0)) as total_impressions
                FROM rtb_daily
                WHERE metric_date >= ?
                  AND COALESCE(impressions, 0) > 0
                GROUP BY app_id, app_name
                HAVING SUM(CASE WHEN COALESCE(clicks, 0) > COALESCE(impressions, 0) THEN 1 ELSE 0 END) >= 2
            """, (cutoff_date,))

            for row in cursor.fetchall():
                app_id = row[0] or "unknown"
                app_name = row[1] or app_id
                total_days = row[2] or 0
                violation_days = row[3] or 0
                total_clicks = row[4] or 0
                total_impressions = row[5] or 0

                if violation_days >= 2:
                    strength = "HIGH" if violation_days >= 5 else ("MEDIUM" if violation_days >= 3 else "LOW")

                    signals.append(FraudSignal(
                        entity_type="app",
                        entity_id=app_id,
                        entity_name=app_name,
                        signal_type="clicks_exceed_impressions",
                        signal_strength=strength,
                        evidence={
                            "violation_days": violation_days,
                            "total_days": total_days,
                            "total_clicks": total_clicks,
                            "total_impressions": total_impressions,
                        },
                        days_observed=total_days,
                        recommendation=f"Investigate - clicks > impressions on {violation_days} of {total_days} days",
                    ))

        finally:
            conn.close()

        return signals

    def store_signals(self, signals: List[FraudSignal]) -> int:
        """
        Store fraud signals in the database for tracking.

        Returns number of new signals stored.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Ensure table exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fraud_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                entity_name TEXT,
                signal_type TEXT NOT NULL,
                signal_strength TEXT NOT NULL,
                evidence TEXT,
                days_observed INTEGER DEFAULT 1,
                status TEXT DEFAULT 'pending',
                reviewed_by TEXT,
                reviewed_at TIMESTAMP,
                notes TEXT
            )
        """)

        stored = 0
        for signal in signals:
            try:
                cursor.execute("""
                    INSERT INTO fraud_signals
                    (entity_type, entity_id, entity_name, signal_type, signal_strength, evidence, days_observed)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    signal.entity_type,
                    signal.entity_id,
                    signal.entity_name,
                    signal.signal_type,
                    signal.signal_strength,
                    json.dumps(signal.evidence),
                    signal.days_observed,
                ))
                stored += 1
            except Exception as e:
                logger.warning(f"Failed to store signal: {e}")

        conn.commit()
        conn.close()

        return stored

    def analyze(self, days: int = 14) -> FraudReport:
        """
        Run all fraud detection checks.

        Args:
            days: Number of days of data to analyze

        Returns:
            FraudReport with all detected signals
        """
        high_ctr = self.detect_high_ctr(days)
        clicks_exceed = self.detect_clicks_exceed_impressions(days)

        all_signals = high_ctr + clicks_exceed

        # Count unique suspicious apps
        suspicious_apps = set()
        for s in all_signals:
            if s.entity_type == "app":
                suspicious_apps.add(s.entity_id)

        return FraudReport(
            signals=all_signals,
            high_ctr_signals=len(high_ctr),
            clicks_exceed_signals=len(clicks_exceed),
            total_suspicious_apps=len(suspicious_apps),
            analysis_days=days,
            generated_at=datetime.now().isoformat(),
        )

    def generate_report(self, days: int = 14) -> str:
        """Generate human-readable fraud signals report (printout)."""
        report = self.analyze(days)

        lines = []
        lines.append("=" * 80)
        lines.append(f"FRAUD SIGNALS REPORT (last {report.analysis_days} days)")
        lines.append("=" * 80)
        lines.append(f"Generated: {report.generated_at}")
        lines.append("")

        # Important disclaimer
        lines.append("IMPORTANT DISCLAIMER:")
        lines.append("These are PATTERNS that may indicate fraud, not proof of fraud.")
        lines.append("Smart fraudsters mix 70-80% real traffic with 20-30% fake.")
        lines.append("VPNs make geographic analysis unreliable.")
        lines.append("All signals require HUMAN REVIEW before action.")
        lines.append("")

        # Summary
        lines.append("SUMMARY")
        lines.append("-" * 40)
        lines.append(f"High CTR signals:           {report.high_ctr_signals}")
        lines.append(f"Clicks > Impressions:       {report.clicks_exceed_signals}")
        lines.append(f"Total suspicious apps:      {report.total_suspicious_apps}")
        lines.append("")

        if not report.signals:
            lines.append("No suspicious patterns detected in this period.")
            lines.append("")
        else:
            # Group by signal type
            high_ctr_signals = [s for s in report.signals if s.signal_type == "high_ctr"]
            clicks_signals = [s for s in report.signals if s.signal_type == "clicks_exceed_impressions"]

            if high_ctr_signals:
                lines.append("=" * 80)
                lines.append("HIGH CTR SIGNALS (may indicate click fraud)")
                lines.append("=" * 80)
                lines.append("")

                for signal in sorted(high_ctr_signals, key=lambda x: x.evidence.get("ctr_pct", 0), reverse=True)[:10]:
                    lines.append(f"APP: {signal.entity_name}")
                    lines.append(f"  ID: {signal.entity_id}")
                    lines.append(f"  CTR: {signal.evidence.get('ctr_pct', 0):.1f}% (expected: ~0.5%)")
                    lines.append(f"  Impressions: {signal.evidence.get('impressions', 0):,}")
                    lines.append(f"  Clicks: {signal.evidence.get('clicks', 0):,}")
                    lines.append(f"  Days observed: {signal.days_observed}")
                    lines.append(f"  Signal strength: {signal.signal_strength}")
                    lines.append(f"  Recommendation: {signal.recommendation}")
                    lines.append("")

            if clicks_signals:
                lines.append("=" * 80)
                lines.append("CLICKS > IMPRESSIONS (may indicate click injection)")
                lines.append("=" * 80)
                lines.append("")

                for signal in sorted(clicks_signals, key=lambda x: x.evidence.get("violation_days", 0), reverse=True)[:10]:
                    lines.append(f"APP: {signal.entity_name}")
                    lines.append(f"  ID: {signal.entity_id}")
                    lines.append(f"  Violations: {signal.evidence.get('violation_days', 0)} of {signal.evidence.get('total_days', 0)} days")
                    lines.append(f"  Signal strength: {signal.signal_strength}")
                    lines.append(f"  Recommendation: {signal.recommendation}")
                    lines.append("")

        lines.append("=" * 80)
        lines.append("WHAT TO DO WITH THESE SIGNALS")
        lines.append("=" * 80)
        lines.append("")
        lines.append("1. Review each flagged app in Google Authorized Buyers")
        lines.append("2. Check if the app is on any known blacklists")
        lines.append("3. Compare with industry benchmarks for that app category")
        lines.append("4. If suspicious, add to your pretargeting blocklist")
        lines.append("5. Monitor for 7+ days before making permanent decisions")
        lines.append("")
        lines.append("DO NOT automatically block based on these signals alone!")
        lines.append("")
        lines.append("=" * 80)
        lines.append("END OF FRAUD SIGNALS REPORT")
        lines.append("=" * 80)

        return "\n".join(lines)


if __name__ == "__main__":
    import sys

    days = 14
    if "--days" in sys.argv:
        idx = sys.argv.index("--days")
        if idx + 1 < len(sys.argv):
            days = int(sys.argv[idx + 1])

    detector = FraudSignalDetector()
    print(detector.generate_report(days))
