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

No Council run is required. The adapter returns only `known`, `conflict`, or `unknown`; suggested searches are explicitly non-evidence.

## Council path

Phase 3 implements the local NEXUS Council path:

```text
caller
  -> CONTROL
  -> admitted evidence references / explicit evidence state
  -> discover NEXUS system.health + system.operations
  -> NEXUS council.run over local JSONL/stdio
  -> NEXUS commits WorldStore session + receipts
  -> CONTROL world.inspect + receipt.verify
  -> verify roster / phases / ballots / threshold / minority reports
  -> CONTROL reference-only storage + rendering
  -> caller
```

CONTROL does not call NEXUS by copying Council mechanics locally. It invokes the parent runtime and then verifies the committed parent artifacts.

## NEXUS ownership

CONTROL treats the following as NEXUS-owned behavior:

- Council roster semantics and canonical join order;
- phase order and same-phase blindness/barriers;
- sealed ballot mechanics and ballot contents;
- vote weights and epistemic privilege;
- consensus numerator/denominator;
- minority reports;
- WorldStore identity/lineage;
- NEXUS receipts and replayability claims;
- Council Chair / Compute Epoch admission policy where present;
- model adapter/governance behavior.

CONTROL may request execution, inspect committed state, verify linkage, render it, and store reference-only copies. It may not reimplement a contradictory version and call it NEXUS.

## Implemented NEXUS governance gate

`qsol-control-nexus-adapter/1` discovers NEXUS capabilities through:

```text
system.health
system.operations
```

and requires the live parent to advertise the operations needed by the adapter. It does not hard-code the full operation catalog.

CONTROL's exposed NEXUS mutation surface contains exactly:

```text
council.run
```

It does not expose generic operation passthrough or direct `world.create`.

Requested member/configuration objects are rejected before submission if they contain CONTROL-side attempts to set:

```text
vote_weight
epistemic_privilege
ballot / ballots
ballot commitments
consensus threshold numerator/denominator
roster authority
WorldStore state
```

After execution, CONTROL resolves and content-address verifies the committed Council session and receipt before rendering. It verifies ballot commitments, recomputes the tally, requires the exact committed threshold, and preserves minority reports.

```text
CONTROL_INVOKES_COUNCIL != CONTROL_OWNS_COUNCIL
CONTROL_RECEIPT_COPY != NEXUS_WORLDSTORE_WRITE
CONTROL_CAN_OVERRIDE_VOTE_WEIGHT = false
CONTROL_CAN_OVERRIDE_BALLOTS = false
CONTROL_CAN_OVERRIDE_CONSENSUS_THRESHOLD = false
NEXUS_OWNS_WORLDSTORE_HISTORY = true
```

`council.run` may cause NEXUS itself to append immutable WorldStore objects. That is parent-owned protocol execution, not direct CONTROL WorldStore mutation.

## Phase order and sealed ballot

The committed NEXUS session policy is the source of canonical `phase_order`. CONTROL preserves it exactly.

In the current reference runtime the policy contains six deliberation phases:

```text
WHITE
RED
BLACK
YELLOW
GREEN
BLUE
```

The commitment/reveal stage is rendered separately as `SEALED_BALLOT`. CONTROL does not alter the parent policy array merely to flatten the lifecycle into one list.

## ORACLE ownership

CONTROL treats the following as ORACLE-owned behavior:

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

## Implemented ORACLE read-only security gate

`qsol-control-oracle-adapter/1` discovers `QSOL-ORACLE/1` from the parent manifest at runtime and verifies the parent append-only ledger before returning evidence.

Its ORACLE write capability set is empty:

```text
append     = forbidden
correct    = forbidden
supersede = forbidden
rewrite    = forbidden
relabel    = forbidden
```

The adapter refuses a CONTROL receipt-storage root that overlaps the ORACLE repository tree. Unknown ORACLE protocol majors fail closed rather than being interpreted by analogy.

## Freshness boundary

CONTROL may display `fresh`, `stale`, `undated`, or `future-dated`, but preserves:

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

## Hidden chain-of-thought boundary

NEXUS's Courtroom Stenographer is a passive local AI-action study ledger with zero CONTROL authority. The Phase 3 adapter does **not** call Stenographer operations and does not request hidden chain-of-thought.

Visible Council phase submissions and visible ballot rationales are externally visible NEXUS outputs and may be preserved. Fields explicitly labelled as hidden/private reasoning, chain-of-thought, scratchpad, or reasoning trace fail closed rather than being copied into CONTROL.

```text
VISIBLE_NEXUS_OUTPUT != HIDDEN_CHAIN_OF_THOUGHT
HIDDEN_CHAIN_OF_THOUGHT_CAPTURED = false
```

## Claim boundary

A rendered answer may have several independent dimensions:

```text
ORACLE evidence state: CONFLICT
NEXUS Council result: 5/6 support interpretation A
Consensus threshold: met
Minority report: present
```

CONTROL preserves the tension. It must **not** rewrite that as:

```text
VERIFIED TRUE: interpretation A
```

## Availability behavior

If ORACLE is unavailable or fails integrity verification:

- mark evidence path unavailable;
- do not manufacture evidence;
- do not silently query an unverified ledger.

If NEXUS is unavailable, advertises an unsupported protocol major, omits required operations, or returns invalid committed artifacts:

- evidence-only mode may still work;
- Council mode is unavailable/fails closed;
- CONTROL must not silently substitute its own vote simulation;
- CONTROL must not normalize a tampered roster, ballot, threshold, or receipt into a plausible-looking answer.

## Version drift

The ORACLE adapter reports parent protocol/schema versions and fails closed on unknown majors. The NEXUS adapter discovers parent protocol/runtime version and operation inventory on each Council session and fails closed on unknown protocol majors or missing required operations.

Later INT integration should test CONTROL↔ORACLE and CONTROL↔NEXUS compatibility, stale-parent handling, authority non-escalation, and schema/version drift explicitly.
