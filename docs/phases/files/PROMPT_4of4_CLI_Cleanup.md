# Claude CLI Prompt 4/4: CLI Updates & Cleanup

## Context

Final prompt: Update CLI tool and clean up old files.

**Project:** `/home/jen/Documents/rtbcat-platform/creative-intelligence/`

---

## Task

### Part 1: Update `cli/qps_analyzer.py`

Add validation step to import command:

```python
def cmd_import(args):
    """Import a CSV file with validation."""
    from qps.importer import validate_csv, import_csv
    
    csv_path = args.file
    
    if not os.path.exists(csv_path):
        print(f"❌ File not found: {csv_path}")
        sys.exit(1)
    
    file_size_mb = os.path.getsize(csv_path) / (1024 * 1024)
    print(f"File: {csv_path} ({file_size_mb:.1f} MB)")
    
    # Validate first
    print("\nValidating...")
    validation = validate_csv(csv_path)
    
    if not validation.is_valid:
        print(f"\n❌ VALIDATION FAILED")
        print(f"\nError: {validation.error_message}")
        print(validation.get_fix_instructions())
        sys.exit(1)
    
    print(f"✓ Validation passed")
    print(f"  Columns found: {len(validation.columns_found)}")
    print(f"  Columns mapped: {len(validation.columns_mapped)}")
    print(f"  Rows (estimated): {validation.row_count_estimate:,}")
    
    if validation.optional_missing:
        print(f"\n  Optional columns not found:")
        for col in validation.optional_missing[:10]:
            print(f"    - {col}")
        if len(validation.optional_missing) > 10:
            print(f"    ... and {len(validation.optional_missing) - 10} more")
    
    # Import
    print(f"\nImporting...")
    result = import_csv(csv_path)
    
    if result.success:
        print(f"\n{'='*60}")
        print("✅ IMPORT COMPLETE")
        print(f"{'='*60}")
        print(f"  Batch ID:         {result.batch_id}")
        print(f"  Rows read:        {result.rows_read:,}")
        print(f"  Rows imported:    {result.rows_imported:,}")
        print(f"  Rows duplicate:   {result.rows_duplicate:,}")
        print(f"  Rows skipped:     {result.rows_skipped:,}")
        print(f"  Date range:       {result.date_range_start} to {result.date_range_end}")
        print(f"  Unique creatives: {result.unique_creatives:,}")
        print(f"  Unique sizes:     {len(result.unique_sizes)}")
        print(f"  Billing IDs:      {', '.join(result.unique_billing_ids[:5])}")
        print(f"  Total reached:    {result.total_reached:,}")
        print(f"  Total impressions:{result.total_impressions:,}")
        print(f"  Total spend:      ${result.total_spend_usd:,.2f}")
        
        if result.errors:
            print(f"\n  Warnings ({len(result.errors)}):")
            for err in result.errors[:5]:
                print(f"    - {err}")
    else:
        print(f"\n❌ IMPORT FAILED: {result.error_message}")
        sys.exit(1)
```

Add validate command:

```python
def cmd_validate(args):
    """Validate a CSV file without importing."""
    from qps.importer import validate_csv
    
    csv_path = args.file
    
    if not os.path.exists(csv_path):
        print(f"❌ File not found: {csv_path}")
        sys.exit(1)
    
    print(f"Validating {csv_path}...")
    validation = validate_csv(csv_path)
    
    print(f"\n{'='*60}")
    if validation.is_valid:
        print("✅ VALID - Ready for import")
    else:
        print("❌ INVALID - Cannot import")
    print(f"{'='*60}")
    
    print(f"\nColumns in file: {len(validation.columns_found)}")
    print(f"Columns mapped:  {len(validation.columns_mapped)}")
    print(f"Rows (est.):     {validation.row_count_estimate:,}")
    
    if validation.columns_mapped:
        print(f"\nMapped columns:")
        for our_name, csv_name in sorted(validation.columns_mapped.items()):
            print(f"  ✓ {our_name} ← '{csv_name}'")
    
    if validation.required_missing:
        print(f"\n❌ MISSING REQUIRED:")
        for col in validation.required_missing:
            print(f"  ✗ {col}")
    
    if validation.optional_missing:
        print(f"\nOptional not found:")
        for col in validation.optional_missing[:10]:
            print(f"  - {col}")
    
    if not validation.is_valid:
        print(validation.get_fix_instructions())
        sys.exit(1)
```

Update argparse to add validate command:

```python
# In main():
validate_parser = subparsers.add_parser("validate", help="Validate CSV without importing")
validate_parser.add_argument("file", help="Path to CSV file")
validate_parser.set_defaults(func=cmd_validate)
```

---

### Part 2: Update Imports at Top of CLI

```python
#!/usr/bin/env python3
"""RTBcat QPS Analyzer CLI - Unified Data Architecture"""

import sys
import os
import argparse
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from qps.importer import validate_csv, import_csv, get_data_summary
from qps.size_analyzer import SizeCoverageAnalyzer
from qps.config_tracker import ConfigPerformanceTracker
from qps.fraud_detector import FraudSignalDetector
from qps.constants import ACCOUNT_NAME, ACCOUNT_ID, PRETARGETING_CONFIGS
```

---

### Part 3: Files to DELETE

```bash
# Old report files (regenerate after new import)
rm -f /home/jen/Documents/rtbcat-platform/creative-intelligence/qps_report.txt
rm -f /home/jen/Documents/rtbcat-platform/creative-intelligence/size_coverage.txt
rm -f /home/jen/Documents/rtbcat-platform/creative-intelligence/config_performance.txt
rm -f /home/jen/Documents/rtbcat-platform/creative-intelligence/fraud_signals.txt

# Old migration (replaced by reset script)
rm -f /home/jen/Documents/rtbcat-platform/creative-intelligence/storage/migrations/002_qps_tables.sql
```

---

### Part 4: Verify Everything Works

```bash
cd /home/jen/Documents/rtbcat-platform/creative-intelligence
source venv/bin/activate

# Test validation
python cli/qps_analyzer.py validate /path/to/your.csv

# Test import
python cli/qps_analyzer.py import /path/to/your.csv

# Test reports
python cli/qps_analyzer.py summary
python cli/qps_analyzer.py coverage --days 7
python cli/qps_analyzer.py configs --days 7
python cli/qps_analyzer.py full-report --days 7
```

---

## Success Criteria

- [ ] CLI import command validates before importing
- [ ] CLI validate command works standalone
- [ ] Clear error messages with fix instructions
- [ ] Old report files deleted
- [ ] All commands work with new schema

---

## After Completing

Tell Jen:

```
Unified Architecture Complete!

Changes made:
1. Database reset with new performance_data table
2. CSV importer with strict validation
3. Analyzers updated to query performance_data
4. CLI with validate command

To use:
  python cli/qps_analyzer.py validate your_file.csv
  python cli/qps_analyzer.py import your_file.csv
  python cli/qps_analyzer.py full-report --days 7

Required CSV columns:
  • Day (date)
  • Creative ID
  • Billing ID
  • Creative size
  • Reached queries
  • Impressions

If any are missing, the importer will show exactly how to fix the export.
```
