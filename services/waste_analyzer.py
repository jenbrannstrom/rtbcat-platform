"""Waste Analyzer Service for Phase 11.2.

Generates evidence-based waste signals with full context.
Replaces boolean flags with actionable insights that explain WHY.

Signal Types:
- broken_video: Video creative that can't play (thumbnail failed)
- zero_engagement: High impressions but no clicks over time
- low_ctr: CTR in bottom percentile of account
- high_spend_low_performance: Spending money on underperforming creative
- click_fraud: Suspicious click patterns
- low_vcr: Video completion rate below threshold
- disapproved: Creative is disapproved but still receiving traffic
"""

import json
import sqlite3
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime


@dataclass
class WasteEvidence:
    """Evidence supporting a waste signal."""
    # Raw data points
    impressions: int = 0
    clicks: int = 0
    spend_micros: int = 0
    reached_queries: int = 0

    # Calculated metrics
    ctr: Optional[float] = None
    waste_rate: Optional[float] = None
    vcr: Optional[float] = None

    # Context
    days_observed: int = 0
    percentile: Optional[int] = None
    threshold: Optional[float] = None
    comparison_value: Optional[float] = None

    # Video specific
    thumbnail_status: Optional[str] = None
    error_type: Optional[str] = None
    video_starts: Optional[int] = None
    video_completions: Optional[int] = None

    # Fraud specific
    occurrences: Optional[int] = None
    publishers: Optional[list[str]] = None
    apps: Optional[list[str]] = None

    def to_dict(self) -> dict:
        """Convert to dict, excluding None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class WasteSignal:
    """A single waste signal with evidence and recommendation."""
    creative_id: str
    signal_type: str
    confidence: str  # low, medium, high
    evidence: WasteEvidence
    observation: str  # Human-readable explanation
    recommendation: str  # Suggested action


class WasteAnalyzerService:
    """
    Service for detecting and storing evidence-based waste signals.

    Phase 11.2: Evidence-Based Waste Detection
    """

    # Thresholds for waste detection
    ZERO_ENGAGEMENT_MIN_IMPRESSIONS = 5000
    ZERO_ENGAGEMENT_MIN_DAYS = 5
    LOW_CTR_PERCENTILE = 10  # Bottom 10%
    HIGH_SPEND_MIN_USD = 10
    HIGH_SPEND_MAX_CTR = 0.01  # 0.01%
    LOW_VCR_THRESHOLD = 0.10  # 10%
    FRAUD_CTR_THRESHOLD = 0.50  # 50% CTR is suspicious

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize with database path."""
        self.db_path = db_path or Path.home() / ".catscan" / "catscan.db"

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def analyze_creative(
        self,
        creative_id: str,
        days: int = 7,
    ) -> list[WasteSignal]:
        """
        Analyze a single creative for waste signals.

        Args:
            creative_id: Creative ID to analyze
            days: Timeframe for analysis

        Returns:
            List of WasteSignal objects
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        signals = []

        # Get creative metadata
        cursor.execute("""
            SELECT id, format, approval_status, advertiser_name
            FROM creatives WHERE id = ?
        """, (creative_id,))
        creative = cursor.fetchone()

        if not creative:
            conn.close()
            return []

        # Get performance data
        cursor.execute(f"""
            SELECT
                COALESCE(SUM(impressions), 0) as impressions,
                COALESCE(SUM(clicks), 0) as clicks,
                COALESCE(SUM(spend_micros), 0) as spend,
                COALESCE(SUM(reached_queries), 0) as reached,
                COALESCE(SUM(video_starts), 0) as video_starts,
                COALESCE(SUM(video_completions), 0) as video_completions,
                COUNT(DISTINCT metric_date) as days_observed
            FROM rtb_daily
            WHERE creative_id = ?
              AND metric_date >= date('now', '-{days} days')
        """, (creative_id,))
        perf = cursor.fetchone()

        # Get thumbnail status for video creatives
        thumbnail_status = None
        error_type = None
        if creative["format"] == "VIDEO":
            cursor.execute("""
                SELECT status, error_reason
                FROM thumbnail_status
                WHERE creative_id = ?
            """, (creative_id,))
            thumb = cursor.fetchone()
            if thumb:
                thumbnail_status = thumb["status"]
                error_type = thumb["error_reason"]

        conn.close()

        # Check for broken video
        if creative["format"] == "VIDEO" and thumbnail_status == "failed":
            signals.append(self._create_broken_video_signal(
                creative_id, perf, error_type
            ))

        # Check for zero engagement
        if (perf["impressions"] >= self.ZERO_ENGAGEMENT_MIN_IMPRESSIONS and
            perf["clicks"] == 0 and
            perf["days_observed"] >= self.ZERO_ENGAGEMENT_MIN_DAYS):
            signals.append(self._create_zero_engagement_signal(
                creative_id, perf
            ))

        # Check for high spend low performance
        spend_usd = perf["spend"] / 1_000_000
        if perf["impressions"] > 0:
            ctr = perf["clicks"] / perf["impressions"]
            if spend_usd >= self.HIGH_SPEND_MIN_USD and ctr < self.HIGH_SPEND_MAX_CTR:
                signals.append(self._create_high_spend_low_perf_signal(
                    creative_id, perf, spend_usd, ctr
                ))

        # Check for low video completion rate
        if creative["format"] == "VIDEO" and perf["video_starts"] > 1000:
            vcr = perf["video_completions"] / perf["video_starts"]
            if vcr < self.LOW_VCR_THRESHOLD:
                signals.append(self._create_low_vcr_signal(
                    creative_id, perf, vcr
                ))

        # Check for disapproved with traffic
        if creative["approval_status"] == "DISAPPROVED" and perf["impressions"] > 0:
            signals.append(self._create_disapproved_signal(
                creative_id, perf
            ))

        return signals

    def analyze_all_creatives(
        self,
        days: int = 7,
        save_to_db: bool = True,
    ) -> list[WasteSignal]:
        """
        Analyze all creatives and optionally save signals to database.

        Args:
            days: Timeframe for analysis
            save_to_db: Whether to persist signals to waste_signals table

        Returns:
            List of all detected WasteSignal objects
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Get all creative IDs with activity in timeframe
        cursor.execute(f"""
            SELECT DISTINCT creative_id
            FROM rtb_daily
            WHERE metric_date >= date('now', '-{days} days')
        """)
        creative_ids = [row["creative_id"] for row in cursor.fetchall()]
        conn.close()

        all_signals = []
        for creative_id in creative_ids:
            signals = self.analyze_creative(creative_id, days)
            all_signals.extend(signals)

        if save_to_db and all_signals:
            self._save_signals(all_signals)

        return all_signals

    def get_signals_for_creative(
        self,
        creative_id: str,
        include_resolved: bool = False,
    ) -> list[dict]:
        """
        Get stored waste signals for a creative.

        Args:
            creative_id: Creative ID
            include_resolved: Include resolved signals

        Returns:
            List of signal dicts
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        if include_resolved:
            cursor.execute("""
                SELECT * FROM waste_signals
                WHERE creative_id = ?
                ORDER BY detected_at DESC
            """, (creative_id,))
        else:
            cursor.execute("""
                SELECT * FROM waste_signals
                WHERE creative_id = ? AND resolved_at IS NULL
                ORDER BY detected_at DESC
            """, (creative_id,))

        signals = []
        for row in cursor.fetchall():
            signals.append({
                "id": row["id"],
                "creative_id": row["creative_id"],
                "signal_type": row["signal_type"],
                "confidence": row["confidence"],
                "evidence": json.loads(row["evidence"]) if row["evidence"] else {},
                "observation": row["observation"],
                "recommendation": row["recommendation"],
                "detected_at": row["detected_at"],
                "resolved_at": row["resolved_at"],
            })

        conn.close()
        return signals

    def resolve_signal(
        self,
        signal_id: int,
        resolved_by: str = "user",
        notes: Optional[str] = None,
    ) -> bool:
        """
        Mark a signal as resolved.

        Args:
            signal_id: Signal ID
            resolved_by: Who resolved it
            notes: Resolution notes

        Returns:
            True if resolved
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE waste_signals
            SET resolved_at = CURRENT_TIMESTAMP,
                resolved_by = ?,
                resolution_notes = ?
            WHERE id = ?
        """, (resolved_by, notes, signal_id))
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return affected > 0

    def _save_signals(self, signals: list[WasteSignal]) -> int:
        """Save signals to database, updating existing ones."""
        conn = self._get_connection()
        cursor = conn.cursor()
        saved = 0

        for signal in signals:
            # Check if signal already exists (same creative + type, unresolved)
            cursor.execute("""
                SELECT id FROM waste_signals
                WHERE creative_id = ? AND signal_type = ? AND resolved_at IS NULL
            """, (signal.creative_id, signal.signal_type))
            existing = cursor.fetchone()

            if existing:
                # Update existing signal with new evidence
                cursor.execute("""
                    UPDATE waste_signals
                    SET evidence = ?,
                        observation = ?,
                        recommendation = ?,
                        confidence = ?,
                        detected_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (
                    json.dumps(signal.evidence.to_dict()),
                    signal.observation,
                    signal.recommendation,
                    signal.confidence,
                    existing["id"],
                ))
            else:
                # Insert new signal
                cursor.execute("""
                    INSERT INTO waste_signals
                    (creative_id, signal_type, confidence, evidence, observation, recommendation)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    signal.creative_id,
                    signal.signal_type,
                    signal.confidence,
                    json.dumps(signal.evidence.to_dict()),
                    signal.observation,
                    signal.recommendation,
                ))
            saved += 1

        conn.commit()
        conn.close()
        return saved

    # Signal creation methods

    def _create_broken_video_signal(
        self,
        creative_id: str,
        perf: sqlite3.Row,
        error_type: Optional[str],
    ) -> WasteSignal:
        """Create a broken video signal."""
        evidence = WasteEvidence(
            impressions=perf["impressions"],
            spend_micros=perf["spend"],
            thumbnail_status="failed",
            error_type=error_type,
        )

        spend_usd = perf["spend"] / 1_000_000

        return WasteSignal(
            creative_id=creative_id,
            signal_type="broken_video",
            confidence="high",
            evidence=evidence,
            observation=f"Video thumbnail generation failed ({error_type}). "
                       f"{perf['impressions']:,} impressions served, ${spend_usd:,.2f} spent. "
                       f"Users likely can't play this video.",
            recommendation="Pause creative immediately and contact advertiser to fix video asset.",
        )

    def _create_zero_engagement_signal(
        self,
        creative_id: str,
        perf: sqlite3.Row,
    ) -> WasteSignal:
        """Create a zero engagement signal."""
        evidence = WasteEvidence(
            impressions=perf["impressions"],
            clicks=0,
            spend_micros=perf["spend"],
            days_observed=perf["days_observed"],
            ctr=0.0,
        )

        spend_usd = perf["spend"] / 1_000_000

        return WasteSignal(
            creative_id=creative_id,
            signal_type="zero_engagement",
            confidence="high" if perf["days_observed"] >= 7 else "medium",
            evidence=evidence,
            observation=f"Zero clicks over {perf['days_observed']} days with "
                       f"{perf['impressions']:,} impressions (${spend_usd:,.2f} spent). "
                       f"Creative is not generating any user engagement.",
            recommendation="Review creative quality and relevance. Consider pausing or replacing.",
        )

    def _create_high_spend_low_perf_signal(
        self,
        creative_id: str,
        perf: sqlite3.Row,
        spend_usd: float,
        ctr: float,
    ) -> WasteSignal:
        """Create a high spend low performance signal."""
        evidence = WasteEvidence(
            impressions=perf["impressions"],
            clicks=perf["clicks"],
            spend_micros=perf["spend"],
            ctr=round(ctr * 100, 4),
            threshold=self.HIGH_SPEND_MAX_CTR * 100,
        )

        return WasteSignal(
            creative_id=creative_id,
            signal_type="high_spend_low_performance",
            confidence="medium",
            evidence=evidence,
            observation=f"Spent ${spend_usd:,.2f} but CTR is only {ctr*100:.4f}% "
                       f"(threshold: {self.HIGH_SPEND_MAX_CTR*100}%). "
                       f"Money is being spent on an underperforming creative.",
            recommendation="Analyze targeting. Check if creative matches audience interests.",
        )

    def _create_low_vcr_signal(
        self,
        creative_id: str,
        perf: sqlite3.Row,
        vcr: float,
    ) -> WasteSignal:
        """Create a low video completion rate signal."""
        evidence = WasteEvidence(
            video_starts=perf["video_starts"],
            video_completions=perf["video_completions"],
            vcr=round(vcr * 100, 2),
            threshold=self.LOW_VCR_THRESHOLD * 100,
        )

        return WasteSignal(
            creative_id=creative_id,
            signal_type="low_vcr",
            confidence="medium",
            evidence=evidence,
            observation=f"Video completion rate is {vcr*100:.1f}% "
                       f"({perf['video_completions']:,} completions from {perf['video_starts']:,} starts). "
                       f"Users are abandoning the video.",
            recommendation="Check video length and quality. Consider shorter or more engaging content.",
        )

    def _create_disapproved_signal(
        self,
        creative_id: str,
        perf: sqlite3.Row,
    ) -> WasteSignal:
        """Create a disapproved creative signal."""
        evidence = WasteEvidence(
            impressions=perf["impressions"],
            spend_micros=perf["spend"],
        )

        spend_usd = perf["spend"] / 1_000_000

        return WasteSignal(
            creative_id=creative_id,
            signal_type="disapproved",
            confidence="high",
            evidence=evidence,
            observation=f"Creative is DISAPPROVED but has {perf['impressions']:,} impressions "
                       f"(${spend_usd:,.2f} spent). This should not be possible.",
            recommendation="Remove from bidding immediately. Check bidder configuration.",
        )


# Convenience function
def analyze_waste(days: int = 7, save: bool = True) -> list[WasteSignal]:
    """Quick function to run waste analysis."""
    service = WasteAnalyzerService()
    return service.analyze_all_creatives(days=days, save_to_db=save)
