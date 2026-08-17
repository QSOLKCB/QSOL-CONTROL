# QSOL-CONTROL Architecture

## Purpose

QSOL-CONTROL is the human and machine **operator plane** for the QSOL ecosystem. It connects interfaces to existing authorities without absorbing those authorities.

The architectural verbs are:

```text
SUBSTRATE  — KNOWS
ARK        — SURVIVES
INT        — COMPOSES
ORACLE     — WITNESSES
NEXUS      — REASONS
CONTROL    — OPERATES
LATTICE    — REMEMBERS
```

The first three remain the Three-Pillar foundation. ORACLE and NEXUS provide the evidentiary/reasoning membrane. CONTROL is the operator surface. Lattice memory is a storage protocol within the control architecture, not another pillar.

## Authority matrix

| Concern | Owner | CONTROL role |
|---|---|---|
| Public epistemic state / provenance | QSOL-SUBSTRATE | display/query |
| Recovery / reconstruction | QSOL-ARK | request/display |
| Composition / drift | QSOL-INT | display/query |
| Witness observations / temporal contracts | QSOL-ORACLE | request/display/store refs |
| Council reasoning / vote mechanics / world state | QSOL-NEXUS | invoke/display |
| Human + AI orchestration | QSOL-CONTROL | owner |
| Interaction/model-state persistence | CONTROL lattice storage | owner of storage mechanics only |

Ownership of storage mechanics does not confer authority over the truth of stored content.

## Control surfaces

### Human surface

The WebUI should expose:

```text
Ask
Evidence
Council
Votes
Minority reports
Sources
Timeline
Receipts
Model states
Replay
System health
```

The UI should make uncertainty visible rather than hiding it behind a generic answer card.

### Machine surface

The AI/agent interface should provide structured operations such as:

```text
control.health
control.capabilities
control.ask
control.run.get
control.run.compare
control.evidence.get
control.council.get
control.models.get
control.memory.get
control.memory.trace
control.replay
```

These are target interfaces for future runtime work, not claims that PR #1 implements a network service.

## Query lifecycle

```text
1. caller submits bounded question
2. CONTROL normalizes request and assigns request identity
3. ORACLE evidence path is queried or supplied
4. evidence state and provenance remain explicit
5. if mode=council, CONTROL requests NEXUS Council execution
6. NEXUS owns roster, phases, ballots, consensus mechanics, world/receipt behavior
7. CONTROL receives externally visible outputs and receipts
8. ORACLE may witness the run boundary according to its own contract
9. CONTROL creates an interaction record
10. interaction + model states receive lattice addresses
11. UI/API renders dimensions without authority collapse
```

## Council rendering

CONTROL must preserve at least:

```text
council_roster
phase_outputs where publicly available
sealed_ballots
consensus_threshold
consensus_result
minority_reports
nexus_receipts
```

A Council result is an output of a governed reasoning process, not empirical validation.

```text
COUNCIL_CONSENSUS != EVIDENCE_STATUS
```

## ORACLE boundary

ORACLE is the evidence/witness path around NEXUS. CONTROL may ask ORACLE for current evidence or receipts and may display ORACLE's `known`, `conflict`, or `unknown` state.

CONTROL may not:

- manufacture an ORACLE event;
- rewrite the ORACLE ledger;
- upgrade a NEXUS answer into a primary observation;
- treat a suggested search as evidence;
- interpret hash integrity as semantic truth.

## Lattice memory placement

The logical storage membrane sits between ORACLE/NEXUS outputs and long-horizon recovery:

```text
ORACLE -----------+
                  |
                  v
             LATTICE MEMORY -----> ARK recovery/reconstruction paths
                  ^
                  |
NEXUS -------------+
```

CONTROL owns addressing, interaction packaging, and retrieval semantics. ORACLE remains authoritative only for its own witnessed events; NEXUS remains authoritative only for its own world/governance mechanics.

## 3×3×3 Sierpinski-derived addressing

Top-level coordinate axes:

```text
X information_role
0 question
1 response
2 evidence

Y epistemic_role
0 observed
1 derived
2 unresolved

Z temporal_role
0 current
1 historical
2 recovery
```

Examples:

```text
new human question        -> L[0,1,0]
Council answer            -> L[1,1,0]
ORACLE observation ref    -> L[2,0,0]
unresolved evidence gap   -> L[2,2,0]
archived historical reply -> L[1,1,1]
future recovery package   -> L[2,0,2]
```

The address must never replace the record's content hash, provenance, source identity, or lineage.

Recursive child coordinates may be added only under a versioned storage profile. Recursive geometry must remain deterministic from recorded metadata.

## Interaction record

A conceptual interaction record binds:

```text
run_id
question_id
requester_kind
question_payload/hash
requested_mode
admitted_evidence_refs
oracle_snapshot/receipts
nexus_run/receipts
council_roster
visible outputs
sealed votes
consensus result
minority reports
model_state_refs
lattice_addresses
timestamps
replayability classification
```

## Model-state record

Model-state capture exists for future computational archaeology and comparison. It is a reproducibility envelope, not hidden cognition capture.

The record should separate:

- observed metadata;
- provider-reported metadata;
- locally hashable metadata;
- inferred/unknown metadata.

A future AI should be able to answer:

> What models participated, under what externally recorded conditions, with what evidence and system versions, and what did they visibly return?

It should **not** be told that CONTROL preserved private reasoning that was never exposed.

## Replay classes

```text
R0 exact deterministic replay
R1 deterministic re-execution from preserved inputs
R2 same declared configuration but stochastic/live inference
R3 rerun with changed evidence/model/runtime state
```

The exact labels may evolve before runtime implementation, but the distinction must survive.

## Failure behavior

CONTROL should fail closed for authority-bearing requests and fail visibly for observational/display gaps.

Examples:

- missing ORACLE evidence -> `unknown/unavailable`, not invented evidence;
- NEXUS unavailable -> Council run unavailable, not locally simulated unless explicitly requested and labelled;
- model metadata missing -> `unknown`, not guessed from model name;
- storage failure -> run completion and persistence status separated;
- replay mismatch -> explain changed inputs rather than claiming exact replay.

## Non-goals

QSOL-CONTROL is not:

- another AI Council;
- another ORACLE;
- a replacement for SUBSTRATE;
- a truth-scoring engine;
- a hidden chain-of-thought recorder;
- a blockchain;
- a geometric theory of cognition;
- a reason to duplicate NEXUS in a frontend framework.
