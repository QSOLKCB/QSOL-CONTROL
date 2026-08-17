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

The first three remain the Three-Pillar foundation. ORACLE and NEXUS provide the evidentiary/reasoning membrane. CONTROL is the operator surface. Lattice memory and persistent Files/Collections are storage mechanisms within CONTROL, not additional authority-bearing pillars.

## Authority matrix

| Concern | Owner | CONTROL role |
|---|---|---|
| Public epistemic state / provenance | QSOL-SUBSTRATE | display/query |
| Recovery / reconstruction | QSOL-ARK | request/display/export |
| Composition / drift | QSOL-INT | display/query |
| Witness observations / temporal contracts | QSOL-ORACLE | request/display/store refs |
| Council reasoning / vote mechanics / world state | QSOL-NEXUS | invoke/display |
| Human + AI orchestration | QSOL-CONTROL | owner |
| Persistent File/Collection mechanics | QSOL-CONTROL | owner of storage mechanics only |
| Interaction/model-state lattice placement | CONTROL lattice layer | owner of storage mechanics only |
| Lexical/vector indexes | CONTROL derived storage | zero semantic authority |
| DNA/codon projection | CONTROL recovery projection | zero semantic authority |

Ownership of storage mechanics does not confer authority over the truth of stored content.

## Control surfaces

### Human surface

The planned WebUI should expose:

```text
Ask
Evidence
Council
Votes
Minority reports
Sources
Files
Collections
Search
Timeline
Receipts
Model states
Lattice memory
Replay
System health
```

The UI should make uncertainty and provenance visible rather than hiding them behind a generic answer card.

### Machine surface

The planned AI/agent interface should provide structured operations such as:

```text
control.health
control.capabilities
control.ask
control.file.put
control.file.get
control.collection.create
control.collection.snapshot
control.collection.search
control.run.get
control.run.compare
control.evidence.get
control.council.get
control.models.get
control.memory.get
control.memory.trace
control.replay
```

Phase 1 currently provides a local standard-library storage runtime and CLI, not a network service.

## Query lifecycle

Target end-to-end lifecycle:

```text
1. caller submits bounded question
2. CONTROL normalizes request and assigns request identity
3. optional Files / exact Collection snapshot are selected
4. retrieval proposes candidate context
5. ORACLE evidence path is queried or supplied
6. evidence state and provenance remain explicit
7. if mode=council, CONTROL requests NEXUS Council execution
8. NEXUS owns roster, phases, ballots, consensus mechanics, world/receipt behavior
9. CONTROL receives externally visible outputs and receipts
10. ORACLE may witness the run boundary according to its own contract
11. CONTROL creates an interaction record
12. interaction + model states receive lattice addresses
13. run references exact File IDs / Collection snapshot IDs
14. UI/API renders dimensions without authority collapse
```

Retrieval occurs before reasoning only as context selection. Retrieval rank is not evidence status.

## Persistent Files and Collections

Phase 1 introduces two durable objects.

```text
FILE
  raw bytes -> sha256 object identity
  immutable metadata -> file_id

COLLECTION
  named persistent corpus
  immutable membership snapshots
  atomic HEAD pointer
```

The same raw bytes may legitimately have multiple File records when provenance/metadata differ. The same File may belong to multiple Collections without duplication of raw content.

Collection member lists are lexicographically ordered by `file_id`.

### Privacy monotonicity

```text
PUBLIC < INTERNAL < RESTRICTED
```

A Collection may be more restrictive than its Files, never less restrictive.

This prevents Collection membership from silently declassifying a File.

## Search architecture

Search indexes are projections over one exact Collection snapshot.

```text
Collection snapshot
      |
      +--> deterministic lexical index
      |
      +--> semantic vector index
```

Implemented search modes:

```text
qsol.term-frequency-cosine/1
qsol.cosine-vector-search/1
```

Semantic embedding generation is deliberately external to the canonical storage core. The index must identify provider/model/revision/dimensions.

When Collection membership changes:

- the old snapshot remains immutable;
- old indexes remain historical projections;
- semantic search against the new `HEAD` fails closed until a matching index exists;
- the deterministic lexical baseline may be rebuilt from canonical bytes.

```text
SEARCH_SCORE != TRUTH
SEMANTIC_SIMILARITY != EVIDENCE_STRENGTH
INDEX != CANONICAL_MEMORY
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

The logical interaction-memory membrane sits between ORACLE/NEXUS outputs and long-horizon recovery:

```text
ORACLE -----------+
                  |
                  v
             LATTICE MEMORY -----> persistent refs -----> ARK recovery
                  ^
                  |
NEXUS -------------+
```

CONTROL owns addressing and interaction packaging. ORACLE remains authoritative only for its own witnessed events; NEXUS remains authoritative only for its own world/governance mechanics.

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

The address must never replace content hash, provenance, source identity or lineage.

```text
LATTICE_ADDRESS != COLLECTION_MEMBERSHIP
GEOMETRY != TRUTH
```

Recursive child coordinates may be added only under a versioned storage profile.

## DNA/codon recovery projection

Phase 1 also defines a reversible projection of File bytes through the 27-cell lattice.

### Payload radix

```text
A=00 C=01 G=10 T=11
4 bases = 1 byte
3 bases = 6 bits = 64 codon slots
```

### Outer radix

```text
3 axes x 3 values x 3 values = 27 lattice cells
```

### Traversals

```text
qsol.lexicographic-27/1
qsol.phi-stride-27/1
```

The φ-gated profile uses fixed modular stride 17:

```text
index(n) = (17 * n) mod 27
```

Since `gcd(17,27)=1`, it forms a single complete path over all 27 cells before repeating.

The traversal is versioned addressing only. It does not claim physical optimality, cognitive geometry or biological meaning.

The projection is accepted only after byte-exact reconstruction and SHA-256 verification.

```text
RAW_BYTES = CANONICAL
DNA_PROJECTION = DERIVED
DNA_ENCODING != BIOLOGICAL_CLAIM
PHI_TRAVERSAL != PHYSICAL_TRUTH
```

## Interaction record

A future persistent interaction record binds:

```text
run_id
question_id
requester_kind
question_payload/hash
requested_mode
file_refs
collection_snapshot_refs
search_index_refs
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

This is Phase 1B work; Phase 1A implements the File/Collection substrate it will reference.

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

Future replay must bind to exact historical Collection snapshots rather than current `HEAD` state.

## Failure behavior

CONTROL should fail closed for authority-sensitive or ambiguous state and fail visibly for observational/display gaps.

Examples:

- missing ORACLE evidence -> `unknown/unavailable`, not invented evidence;
- stale semantic index -> unavailable until rebuilt, not silently searched against wrong membership;
- Collection privacy mismatch -> membership update rejected;
- corrupt raw object -> verification failure;
- malformed DNA projection -> decode failure, not partial reconstruction;
- NEXUS unavailable -> Council run unavailable unless explicitly simulated/labelled;
- model metadata missing -> `unknown`, not guessed from model name;
- replay mismatch -> explain changed inputs rather than claiming exact replay.

## Non-goals

QSOL-CONTROL is not:

- another AI Council;
- another ORACLE;
- a replacement for SUBSTRATE;
- a truth-scoring engine;
- a hidden chain-of-thought recorder;
- a blockchain;
- a vector database promoted to epistemic authority;
- a biological DNA storage claim;
- a claim that φ is physically optimal for data storage;
- a geometric theory of cognition;
- a reason to duplicate NEXUS in a frontend framework.
