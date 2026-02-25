# Codex Plan: TUKY Import Pipeline Audit (Local Code + Correctness Path)

## Objective

Audit the local code paths for the TUKY import pipeline issue and identify where data can be:

- misclassified in import tracking (UI shows fewer CSV types than actually imported),
- silently dropped from end-to-end processing (Gmail -> import -> pipeline -> precompute),
- or misinterpreted in the UI due to unit mismatch (daily counts vs QPS).

This audit runs in parallel with Claude's production evidence collection.

## Scope (Codex side)

### In scope

1. Gmail import code correctness (`scripts/gmail_import.py`, `scripts/gmail_import_batch.py`)
2. Import tracking/report-type classification fidelity (`ingestion_runs`/`import_history` recording path)
3. Pipeline trigger semantics after Gmail import (`run_pipeline_for_file`)
4. Home endpoint observed-QPS derivation path (`rtb_endpoints_current` refresh formula)
5. Local code-level RCA notes and prioritized fix list

### Out of scope (Claude handling)

1. Production TUKY seat data reconciliation (Postgres/BQ outputs)
2. `ingestion_runs` / `import_history` prod evidence for TUKY
3. Gmail unread straggler classification (Feb 11–14)
4. Prod import matrix behavior verification

## Working Hypotheses (to verify/falsify)

1. **Import tracking underreports CSV types** because GCS-downloaded files are renamed to generic filenames (e.g. `catscan-report-<seat>-<timestamp>.csv`), and report kind is inferred from local filename instead of original report name / parsed report type.
2. **Message-level checkpoint/read semantics can hide partial failures** (message marked processed/read even if one file import or downstream pipeline step failed).
3. **Known `CatscanImportResult` mismatch in batch importer** causes imports to land while tracking/counters/pipeline execution break, producing confusing UI state and unread/email checkpoint drift.
4. **Home observed endpoint values are likely not corrupted raw metrics**, but derived average QPS values (`reached_queries/day/86400`) distributed by endpoint allocated QPS.
5. There may still be **pipeline success not enforced** (raw import succeeds, pipeline/precompute fails, email still marked processed).

## Audit Steps (Codex)

1. Capture exact code-path line references for:
   - file renaming in GCS download
   - report kind detection
   - import run recording
   - batch importer import result handling
   - mark-as-read / checkpoint logic
   - pipeline invocation and error handling
   - endpoint observed QPS formula
2. Confirm data/unit semantics for Home observed QPS path from code.
3. Identify all places where failures are logged but not propagated (silent correctness risk).
4. Produce a local code-audit findings summary with severity and likely impact.
5. Draft a ranked fix plan for after Claude’s prod evidence confirms/denies the hypotheses.

## Deliverables (Codex)

1. This plan doc (current file)
2. Local code audit findings summary (chat + optional follow-up doc)
3. Ranked patch plan (no code changes yet unless explicitly requested)

## Change Policy

- This pass is **read-only code audit** (no functional changes yet).
- No production mutations from this side during the audit.
- Code fixes will be proposed after we align with Claude’s prod evidence.

## Initial Indicators Already Seen

- `home_seat_daily` values for TUKY (prod spot-check) align with the attached CSV scale, which weakens the “numeric corruption” hypothesis.
- `rtb_endpoints_current` observed QPS path uses `reached_queries / days / 86400` (QPS), which strongly suggests a unit mismatch in interpretation.
- Gmail batch importer currently appears to treat checkpointed messages as “already processed” regardless of Gmail unread status.

