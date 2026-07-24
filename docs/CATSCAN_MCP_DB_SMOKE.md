# CatScan MCP database smoke contracts

`scripts/catscan_mcp_db_smoke.py` compares the read answers produced by two
PostgreSQL databases. It is intended for migration rehearsals now and as the
database contract beneath a future buyer-facing CatScan MCP server.

The smoke runner does not compare only table counts. It asks deterministic
media-buyer questions:

| Future MCP tool | Question answered |
|---|---|
| `catscan.list_buyers` | Which buyer seats and reporting currencies can I query? |
| `catscan.get_data_freshness` | How far does each compiled dataset extend? |
| `catscan.get_daily_spend` | What was canonical daily spend, and which days are missing? |
| `catscan.get_monthly_spend` | What are the calendar-month canonical totals through a cutoff? |
| `catscan.get_all_time_spend` | What is each buyer's complete canonical history through a cutoff? |
| `catscan.get_performance_summary` | What happened through the bid and spend funnel? |
| `catscan.get_report_completeness` | Is there enough compiled data to issue a report? |
| `catscan.get_top_geos` | Which countries led performance? |
| `catscan.get_top_publishers` | Which publishers led performance? |
| `catscan.get_top_configs` | Which pretargeting configurations led performance? |

Every query has an explicit buyer set, an explicit closed date window where
applicable, deterministic ordering, and a hard statement timeout. Spend comes
from `rtb_buyer_spend_daily`. The suite does not query raw `rtb_daily`, and
each connection sets `default_transaction_read_only=on` before executing a
contract.

## Run it

Use the project virtual environment. Put database URLs in environment
variables; do not pass credentials on the command line:

```bash
export CATSCAN_SMOKE_SOURCE_DSN='postgresql://...'
export CATSCAN_SMOKE_TARGET_DSN='postgresql://...'

venv/bin/python scripts/catscan_mcp_db_smoke.py \
  --source-label cloud-sql \
  --target-label hetzner-rehearsal \
  --days 30 \
  --stable-lag-days 1 \
  --report-json /tmp/catscan-mcp-db-smoke.json
```

For an SSH tunnel or local proxy, preserve the credentials and override only
the network/database coordinates:

```bash
venv/bin/python scripts/catscan_mcp_db_smoke.py \
  --source-host 127.0.0.1 \
  --source-port 55432 \
  --target-host 127.0.0.1 \
  --target-port 55433 \
  --target-dbname rtbcat_serving_rehearsal
```

By default the runner selects buyers present in both databases. It ends the
comparison one day before the older database's latest canonical spend date,
which avoids comparing new source writes with an older online snapshot. Use
repeatable `--buyer-id` options or `--end-date YYYY-MM-DD` when a specific
reconciliation case is required.

The console and JSON evidence contain row counts, timings, hashes, and the
names of changed columns. Difference samples hash their row keys and omit
metric values. A zero exit code means every normalized result matched exactly;
one means at least one contract differed; two means the run was blocked.

## MCP boundary

The SQL catalog is a data contract, not an authorization boundary. A future
MCP server should expose these names as typed read tools while reusing the
existing CatScan controls:

- authenticate an agent identity;
- resolve its buyer grants;
- pass only those buyer IDs to a contract;
- validate date ranges and limits;
- audit every request;
- keep mutations behind separate authenticated action APIs.

Direct database access should continue to use `agent_read` roles and grants.
Outside media-buyer clients should normally call a versioned HTTP/MCP service,
not receive raw PostgreSQL credentials.

## Private finance companion

`scripts/catscan_finance_db_reconcile.py` separately verifies the
`financial_viability` schema, exact table cardinalities, monthly canonical/raw
spend, customer balances, Mercury transactions and invoice obligations. These
are migration contracts only. They must not be added to the media-buyer MCP
tool catalog.
