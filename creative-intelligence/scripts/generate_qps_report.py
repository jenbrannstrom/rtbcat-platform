#!/usr/bin/env python3
"""
Generate QPS Optimization Report.

This script generates a comprehensive QPS optimization report as described in
RTBcat_QPS_Optimization_Strategy_v2.md.

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

import asyncio
import os
import sys
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analytics.qps_optimizer import QPSOptimizer
from storage import SQLiteStore


async def main():
    """Generate all QPS optimization reports."""

    print("=" * 60)
    print("RTBcat QPS Optimization Report Generator")
    print("=" * 60)
    print()

    # Initialize storage
    store = SQLiteStore()
    await store.initialize()

    # Initialize optimizer
    optimizer = QPSOptimizer(store)

    # Output directory
    output_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Generate full report
    print("Generating full QPS report...")
    full_report = await optimizer.generate_full_report()

    # Print to console
    print()
    print(full_report)
    print()

    # Save to file
    report_path = os.path.join(output_dir, "qps_report.txt")
    with open(report_path, "w") as f:
        f.write(full_report)
    print(f"Full report saved to: {report_path}")

    # Generate individual reports
    print()
    print("Generating individual module reports...")

    # Module 1: Size Coverage
    try:
        size_report = await optimizer.generate_size_coverage_report()
        size_path = os.path.join(output_dir, "size_coverage.txt")
        with open(size_path, "w") as f:
            f.write(size_report.to_printout())
        print(f"  Size Coverage saved to: {size_path}")
    except Exception as e:
        print(f"  Size Coverage: Error - {e}")

    # Module 2: Config Performance
    try:
        config_report = await optimizer.generate_config_performance_report()
        config_path = os.path.join(output_dir, "config_performance.txt")
        with open(config_path, "w") as f:
            f.write(config_report.to_printout())
        print(f"  Config Performance saved to: {config_path}")
    except Exception as e:
        print(f"  Config Performance: Error - {e}")

    # Module 3: Fraud Signals
    try:
        fraud_report = await optimizer.generate_fraud_signal_report()
        fraud_path = os.path.join(output_dir, "fraud_signals.txt")
        with open(fraud_path, "w") as f:
            f.write(fraud_report.to_printout())
        print(f"  Fraud Signals saved to: {fraud_path}")
    except Exception as e:
        print(f"  Fraud Signals: Error - {e}")

    print()
    print("=" * 60)
    print("Report generation complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
