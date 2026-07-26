# CatScan paired read-only API soak

`scripts/catscan_api_read_only_soak.py` repeatedly sends the same 15
rehearsed `GET` contracts to GCP and the loopback-only Hetzner shadow. It
records request failures, HTTP status, latency, response size, exact result
hashes, value-free schema hashes and changed JSON paths.

It never sends a state-changing HTTP method. Every successful target response
must also contain `X-CatScan-Shadow: read-only`. Reports omit response bodies,
credentials and buyer IDs. The health contract retains only its non-sensitive
release/version identifiers so differences between application builds cannot
be mistaken for provider or database effects.

Exact result mismatches and request/schema failures are separate. The rehearsal
database is an older snapshot while GCP remains writable, so value drift is
expected on current-window endpoints. A changed schema, non-200 response,
timeout or missing target shadow header is a different and more serious signal.

## One-cycle baseline

Create an SSH tunnel to the target's loopback API, put the existing CatScan API
key in a mode-0600 temporary file, then run:

```bash
venv/bin/python scripts/catscan_api_read_only_soak.py \
  --source-base-url https://scan.rtb.cat/api \
  --target-base-url http://127.0.0.1:18000 \
  --source-label gcp-production \
  --target-label hetzner-rehearsal-shadow \
  --token-file /secure/path/one-use-token \
  --delete-token-file \
  --iterations 1 \
  --strict \
  --report-dir docs/internal/rtbcat-migration/api-soak/baseline
```

The token file is deleted immediately after it is read. If
`CATSCAN_SOAK_BUYER_ID` is unset, the runner selects the first seat returned by
both deployments and does not record its ID.

## Six-hour soak

Use `--duration-seconds 21600 --interval-seconds 900`. Alternating runs query
GCP first and Hetzner first to reduce fixed request-order bias. The runner
writes `run-NNNN.json` after every cycle and atomically refreshes
`summary.json`, so partial evidence survives a process or workstation failure.

Keep the SSH tunnel supervised with server-alive checks. The target API must
remain loopback-only and read-only, and all target schedulers must remain
disabled throughout the run.

Source and target use different network paths. Treat latency as directional
soak evidence rather than a controlled same-network benchmark. If their health
revision identifiers differ, the run compares real deployed behavior but is
also not a controlled same-code comparison.
