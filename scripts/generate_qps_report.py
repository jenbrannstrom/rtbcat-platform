#!/usr/bin/env python3
"""
Generate QPS Optimization Report.

This script generates a comprehensive QPS optimization report as described in
RTBcat_QPS_Optimization_Strategy_v2.md.

Note: For more options, use the CLI tool instead:
    python cli/qps_analyzer.py full-report --days 7

Usage:
    cd /home/jen/Documents/rtbcat-platform/creative-intelligence
    source venv/bin/activate
    python scripts/generate_qps_report.py

Output files:
    - qps_report.txt (full report)
    - size_coverage.txt (Module 1)
    - config_performance.txt (Module 2)
    - fraud_signals.txt (Module 3)
"""

import os
import sys
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qps import (
    SizeCoverageAnalyzer,
    ConfigPerformanceTracker,
    FraudSignalDetector,
    ACCOUNT_NAME,
    ACCOUNT_ID,
)


def main():
    """Generate all QPS optimization reports."""

    print("=" * 60)
    print("RTBcat QPS Optimization Report Generator")
    print("=" * 60)
    print()

    # Output directory
    output_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    days = 7

    # Generate full report
    print("Generating full QPS report...")

    lines = []
    lines.append("")
    lines.append("=" * 80)
    lines.append("RTBcat QPS OPTIMIZATION FULL REPORT")
    lines.append("=" * 80)
    lines.append("")
    lines.append(f"Account: {ACCOUNT_NAME} (ID: {ACCOUNT_ID})")
    lines.append(f"Generated: {datetime.now().isoformat()}")
    lines.append(f"Analysis Period: {days} days")
    lines.append("")

    # Module 1: Size Coverage
    print("  Generating Size Coverage report...")
    try:
        analyzer = SizeCoverageAnalyzer()
        size_report = analyzer.generate_report(days)
        lines.append(size_report)
        lines.append("")

        # Save individual report
        size_path = os.path.join(output_dir, "size_coverage.txt")
        with open(size_path, "w") as f:
            f.write(size_report)
        print(f"    Saved to: {size_path}")
    except Exception as e:
        lines.append(f"Size Coverage: Error - {e}")
        lines.append("")
        print(f"    Error: {e}")

    # Module 2: Config Performance
    print("  Generating Config Performance report...")
    try:
        tracker = ConfigPerformanceTracker()
        config_report = tracker.generate_report(days)
        lines.append(config_report)
        lines.append("")

        # Save individual report
        config_path = os.path.join(output_dir, "config_performance.txt")
        with open(config_path, "w") as f:
            f.write(config_report)
        print(f"    Saved to: {config_path}")
    except Exception as e:
        lines.append(f"Config Performance: Error - {e}")
        lines.append("")
        print(f"    Error: {e}")

    # Module 3: Fraud Signals
    print("  Generating Fraud Signals report...")
    try:
        detector = FraudSignalDetector()
        fraud_report = detector.generate_report(days * 2)  # 14 days for fraud
        lines.append(fraud_report)
        lines.append("")

        # Save individual report
        fraud_path = os.path.join(output_dir, "fraud_signals.txt")
        with open(fraud_path, "w") as f:
            f.write(fraud_report)
        print(f"    Saved to: {fraud_path}")
    except Exception as e:
        lines.append(f"Fraud Signals: Error - {e}")
        lines.append("")
        print(f"    Error: {e}")

    lines.append("=" * 80)
    lines.append("END OF FULL REPORT")
    lines.append("=" * 80)

    full_report = "\n".join(lines)

    # Print to console
    print()
    print(full_report)
    print()

    # Save full report
    report_path = os.path.join(output_dir, "qps_report.txt")
    with open(report_path, "w") as f:
        f.write(full_report)
    print(f"Full report saved to: {report_path}")

    print()
    print("=" * 60)
    print("Report generation complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
