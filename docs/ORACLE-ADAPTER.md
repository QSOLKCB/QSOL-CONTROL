# QSOL-CONTROL Read-only ORACLE Adapter

## Boundary

CONTROL may read, verify, reference, cache, and display QSOL-ORACLE observations. It may not become an ORACLE writer.

```text
ORACLE provides witnessed evidence.
CONTROL operates the workflow.
CONTROL receipt storage is not ORACLE history.
```

The Phase 2 adapter is implemented in `adapters/oracle.py` and exposed through `tools/oracle_adapter.py`.

Its write capability set toward ORACLE is deliberately empty.

```text
oracle_write_operations = []
```

## Runtime discovery

The adapter reads `manifest.json` from the supplied local QSOL-ORACLE repository and discovers:

- parent protocol;
- semantic schema version;
- ledger model;
- available read capabilities;
- optional timelock/feed capabilities.

`QSOL-ORACLE/1` is the accepted parent major. Backward-compatible 1.x manifest additions are tolerated. An unknown protocol major fails closed.

The adapter requires the parent ledger model to remain `single-writer-append-only`.

## Ledger verification before evidence queries

Before returning an evidence result, CONTROL verifies the ORACLE ledger rather than trusting filenames or hashes supplied out of context.

Checks include:

- canonical sequence order;
- unique event IDs;
- `previous_hash` linkage;
- canonical `event_hash` recomputation;
- `authority: observation-only`;
- supported evidence states and provenance classes;
- earlier-event requirements for `derived_from` references;
- bounded ledger bytes and event count.

This establishes integrity of the observed ORACLE history. It does not establish semantic truth.

## Evidence-only query

The initial adapter deliberately uses exact subject matching. It does not invent a fuzzy semantic query language and pretend ORACLE specified one.

Results use exactly:

```text
known
conflict
unknown
```

For matching canonical events:

- an explicit conflict produces `conflict`;
- an observed state without conflict produces `known`;
- insufficient/unknown evidence produces `unknown`;
- correction/supersession relationships that cannot safely be collapsed by the adapter remain `unknown` rather than being guessed into a new truth state.

Every returned evidence reference preserves ORACLE event ID/hash, observed time, source locator, provenance kind, evidence state, and payload hash.

```text
ORACLE_REFERENCE != CONTROL_AUTHORITY
```

## Suggested searches

For unknown results, callers may attach bounded search suggestions.

They are always emitted with:

```json
"search_suggestions_are_evidence": false
```

CONTROL does not upgrade a research hint into an observation simply because the strings are displayed in the same panel.

## Availability and freshness

The adapter reports availability separately from evidence state.

Freshness is represented as one of:

```text
fresh
stale
undated
future-dated
```

and carries the hard machine boundaries:

```text
FRESH != TRUE
STALE != FALSE
```

A stale observation can still be historically correct. A fresh observation can still be wrong, incomplete, or contradicted.

## Receipt storage

CONTROL can persist exact verified ORACLE payload bytes in its own `ControlStore`.

The stored File record includes:

- the external ORACLE/source reference;
- exact payload SHA-256;
- the ORACLE event/feed/adapter identity where applicable;
- `authority: reference-only`;
- `copied_authority: false`.

The CONTROL storage root is forbidden from overlapping the ORACLE repository tree. This prevents the receipt-cache path from being repurposed as a backdoor ledger writer.

```text
ORACLE_RECEIPT_COPY != ORACLE_LEDGER_APPEND
```

The adapter also understands verified `QSOL-ORACLE-FEED/1` observation receipts when a compatible ORACLE 1.x parent exposes that optional contract. CONTROL does not depend on feed collectors being present.

## QSOL-CONTEXT 2056 timelock view

The adapter can inspect the parent `QSOL-TIMELOCK/1` contract and the ORACLE ledger witness that binds its payload hash.

The UI-facing state is `locked` or `eligible` based on the contract deadline, while always preserving:

```json
"execution_authorized": false
```

```text
ELIGIBLE != EXECUTED
```

Deadline maturity does not bypass publication clearance, privacy review, permanent-deny handling, unclassified-material checks, or current platform authorization.

## CLI

```bash
python3 tools/oracle_adapter.py \
  --oracle-root /path/to/QSOL-ORACLE \
  discover

python3 tools/oracle_adapter.py \
  --oracle-root /path/to/QSOL-ORACLE \
  query "QSOLKCB/QSOL-CONTEXT" \
  --at 2026-08-19T08:45:00+09:30

python3 tools/oracle_adapter.py \
  --oracle-root /path/to/QSOL-ORACLE \
  timelock
```

There is intentionally no `append`, `correct`, `supersede`, `rewrite`, or `relabel` command.
