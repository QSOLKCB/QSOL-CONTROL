# QSOL-CONTROL — NEXUS / ORACLE Boundary

## The short version

```text
ORACLE provides evidence.
NEXUS provides governed reasoning.
CONTROL operates the workflow.
```

CONTROL is not allowed to blur those responsibilities merely because it can display them on the same screen.

## Evidence-only path

Phase 2 implements the local read-only ORACLE path:

```text
caller
  -> CONTROL
  -> read-only QSOL-ORACLE adapter
  -> verified ledger + exact subject query
  -> evidence state + provenance refs + gaps + freshness
  -> CONTROL
  -> caller
```

No Council run is required.

The adapter returns only:

```text
known
conflict
unknown
```

Suggested searches are explicitly non-evidence.

## Council path

The NEXUS path remains a later phase:

```text
caller
  -> CONTROL
  -> ORACLE evidence retrieval / admitted refs
  -> CONTROL
  -> NEXUS Council invocation
  -> visible phase outputs / ballots / minority reports / receipts
  -> optional ORACLE witness receipt
  -> CONTROL storage + rendering
  -> caller
```

## NEXUS ownership

CONTROL must treat the following as NEXUS-owned behavior:

- Council roster semantics;
- phase order;
- same-phase blindness/barriers;
- sealed ballot mechanics;
- vote weights;
- consensus threshold;
- minority reports;
- WorldStore identity/lineage;
- NEXUS receipts;
- model adapter/governance behavior.

CONTROL may display or request these. It may not reimplement a contradictory version and call it NEXUS.

## ORACLE ownership

CONTROL must treat the following as ORACLE-owned behavior:

- witnessed observations;
- evidence provenance classification;
- append-only ledger semantics;
- `known`, `conflict`, `unknown` evidence responses;
- temporal-contract state such as the QSOL-CONTEXT 2056 publication directive;
- ORACLE event identities/receipts.

CONTROL storage may cache exact verified ORACLE payload bytes or references, but cached copies do not become new ORACLE authority.

```text
ORACLE_REFERENCE != CONTROL_AUTHORITY
ORACLE_RECEIPT_COPY != ORACLE_LEDGER_APPEND
```

## Implemented read-only adapter security gate

`qsol-control-oracle-adapter/1` discovers `QSOL-ORACLE/1` from the parent manifest at runtime and verifies the parent append-only ledger before returning evidence.

Its ORACLE write capability set is empty:

```text
append     = forbidden
correct    = forbidden
supersede = forbidden
rewrite    = forbidden
relabel    = forbidden
```

The adapter also refuses to use a CONTROL receipt-storage root that overlaps the ORACLE repository tree.

Unknown ORACLE protocol majors fail closed rather than being interpreted by analogy.

## Freshness boundary

CONTROL may display:

```text
fresh
stale
undated
future-dated
```

but must preserve:

```text
FRESH != TRUE
STALE != FALSE
```

Freshness is a temporal property of an observation, not a truth verdict.

## Timelock boundary

The read-only adapter exposes the `QSOL-TIMELOCK/1` QSOL-CONTEXT 2056 contract as `locked` or `eligible` and preserves the ORACLE witness reference when present.

It always reports:

```json
"execution_authorized": false
```

```text
ELIGIBLE != EXECUTED
```

## Stenographer relationship

NEXUS's Courtroom Stenographer is a passive local AI-action study ledger with zero control authority. ORACLE generalizes ecosystem witnessing outside NEXUS.

CONTROL may expose both where useful, but must label provenance clearly so a user can tell whether a record came from:

```text
NEXUS Stenographer
QSOL-ORACLE
CONTROL interaction storage
```

`stored in CONTROL` is not equivalent to `witnessed by ORACLE`.

## Claim boundary

A rendered answer may have several independent dimensions:

```text
ORACLE evidence state: CONFLICT
NEXUS Council result: 5/6 support interpretation A
Consensus threshold: met
Minority report: present
```

CONTROL must preserve the tension. It must **not** rewrite that as:

```text
VERIFIED TRUE: interpretation A
```

## Availability behavior

If ORACLE is unavailable or fails integrity verification:

- mark evidence path unavailable;
- do not manufacture evidence;
- do not silently query an unverified ledger;
- Council invocation should later follow an explicit policy about whether an evidence-unavailable run is permitted and how it is labelled.

If NEXUS is unavailable:

- evidence-only mode may still work;
- Council mode is unavailable;
- CONTROL must not silently substitute its own local vote simulation.

## Version drift

The ORACLE adapter reports parent protocol/schema versions and fails closed on unknown majors. Backward-compatible ORACLE 1.x additions may be discovered without becoming mandatory dependencies.

Later INT integration should test CONTROL↔ORACLE compatibility, stale-parent handling, authority non-escalation, and schema/version drift explicitly.
