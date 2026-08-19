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

The first three remain the Three-Pillar foundation. ORACLE and NEXUS provide the evidentiary/reasoning membrane. CONTROL is the operator surface. Lattice memory, persistent Files/Collections, and the model-state registry are storage/reproducibility mechanisms within CONTROL, not additional authority-bearing pillars.

## Authority matrix

| Concern | Owner | CONTROL role |
|---|---|---|
| Public epistemic state / provenance | QSOL-SUBSTRATE | display/query |
| Recovery / reconstruction | QSOL-ARK | request/display/export |
| Composition / drift | QSOL-INT | display/query |
| Witness observations / temporal contracts | QSOL-ORACLE | read/query/store refs only |
| Council reasoning / vote mechanics / WorldStore history | QSOL-NEXUS | discover/invoke/verify/render/store refs only |
| Human + AI orchestration | QSOL-CONTROL | owner |
| Persistent File/Collection mechanics | QSOL-CONTROL | owner of storage mechanics only |
| Interaction/model-state lattice placement | CONTROL lattice layer | owner of storage mechanics only |
| Model-state reproducibility registry | QSOL-CONTROL | metadata storage/comparison only; zero mind/truth authority |
| Minimum CONTROL recovery packaging | QSOL-CONTROL | packaging/verifier only; ARK retains recovery authority |
| Lexical/vector indexes | CONTROL derived storage | zero semantic authority |
| DNA/codon projection | CONTROL recovery projection | zero semantic authority |

Ownership of storage mechanics does not confer authority over the truth of stored content. Invocation authority does not confer authority to rewrite the invoked system's governance. Recording model/runtime metadata does not confer access to hidden cognition.

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

The UI should make uncertainty and provenance visible rather than hiding them behind a generic answer card. The Phase 4 model-state label contract is already fixed even though Phase 5 has not yet implemented the WebUI.

### Machine surface

The planned network AI/agent interface should provide structured operations such as:

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

The implemented local standard-library layer now includes File/Collection storage, interaction persistence, minimum offline ARK recovery packaging, a read-only ORACLE adapter, a governance-preserving NEXUS Council adapter over local JSONL/stdio, and a persistent model-state registry with comparisons/archaeology export. It is still not a network CONTROL service.

## Query lifecycle

Implemented storage/adaptor lifecycle:

```text
1. caller submits bounded question
2. CONTROL normalizes request and assigns request identity
3. optional Files / exact Collection snapshot are selected
4. retrieval proposes candidate context
5. ORACLE evidence path is queried or supplied
6. evidence state and provenance remain explicit
7. if mode=council, CONTROL discovers live NEXUS health/operations
8. CONTROL submits question + admitted evidence refs through council.run
9. NEXUS owns roster, phases, ballots, consensus mechanics, WorldStore and receipts
10. CONTROL resolves committed session/receipt refs and verifies their identities/linkage
11. CONTROL renders canonical roster, phases, sealed ballot, exact threshold and minority reports
12. CONTROL may persist verified external artifacts as reference-only Files/events
13. participating model executions may receive immutable qsol-control-model-state/1 records
14. each model-state field carries explicit provenance and the state binds to its CONTROL run
15. interaction/model-state lineage is preserved without copying ORACLE/NEXUS authority or model cognition
16. UI/API renders dimensions without authority collapse
```

Retrieval occurs before reasoning only as context selection. Retrieval rank is not evidence status. Council consensus is not evidence status. Model identity/configuration is not evidence status.

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

ORACLE is the evidence/witness path around NEXUS. CONTROL implements a **read-only** `qsol-control-oracle-adapter/1` for stable parent protocol `QSOL-ORACLE/1`.

Before evidence queries, CONTROL discovers the parent manifest at runtime and verifies the append-only ledger hash chain. Evidence queries return exact `known`, `conflict`, or `unknown` states while preserving ORACLE event hashes, source references, provenance class, timestamps and payload identities.

The adapter also reports availability/freshness and the QSOL-CONTEXT 2056 timelock view. Search suggestions remain explicitly non-evidence.

CONTROL may store exact verified ORACLE payload bytes in its own store as `reference-only` material, but that storage root must not overlap the ORACLE repository.

CONTROL may not:

- manufacture an ORACLE event;
- append, correct, supersede, rewrite or relabel the ORACLE ledger;
- upgrade a CONTROL receipt copy into ORACLE authority;
- upgrade a NEXUS answer into a primary observation;
- treat a suggested search as evidence;
- interpret freshness or hash integrity as semantic truth;
- treat timelock eligibility as execution authorization.

```text
ORACLE_REFERENCE != CONTROL_AUTHORITY
ORACLE_RECEIPT_COPY != ORACLE_LEDGER_APPEND
FRESH != TRUE
STALE != FALSE
SUGGESTED_SEARCH != EVIDENCE
ELIGIBLE != EXECUTED
```

The adapter exposes no ORACLE write operation. Unknown ORACLE protocol majors fail closed.

## NEXUS governance boundary

CONTROL implements `qsol-control-nexus-adapter/1` against NEXUS's local JSONL/stdio control plane.

The adapter does not hard-code the full parent capability inventory. Every adapter session asks:

```text
system.health
system.operations
```

and requires the live parent to advertise the Council operations CONTROL actually needs. An unknown NEXUS protocol major fails closed.

CONTROL's public NEXUS mutation surface contains exactly:

```text
council.run
```

The adapter does **not** expose generic NEXUS operation passthrough or direct `world.create`. `council.run` may cause NEXUS itself to append its immutable WorldStore objects; that is NEXUS executing its own protocol, not CONTROL rewriting WorldStore history.

After a run, CONTROL resolves `session_ref` and `receipt_ref`, verifies the content-addressed WorldStore objects, calls `receipt.verify`, and checks the committed Council state before rendering it. Verification includes:

- canonical roster ordering and ordinary vote weight `1` / epistemic privilege `none`;
- phase order from the committed session policy;
- same roster join order at every committed phase;
- ballot commitment/reveal integrity;
- tally computed from revealed ballots;
- exact consensus numerator/denominator from the committed policy;
- minority reports preserved against the revealed ballot record;
- exact admitted-evidence snapshot refs/state;
- receipt result/ref/replayability linkage;
- optional Council Chair / Compute Epoch admission evidence when the parent advertises it.

The committed NEXUS policy currently exposes six deliberation phases. CONTROL preserves that exact `phase_order` and renders the subsequent commitment/reveal step separately as `SEALED_BALLOT`.

Requested Council member descriptors are not governance override envelopes. CONTROL rejects fields such as `vote_weight`, `epistemic_privilege`, direct ballot data, consensus-threshold controls, roster authority, or WorldStore state before calling NEXUS.

CONTROL may persist externally visible NEXUS artifacts into its own storage as `reference-only` Files and link them into interaction receipt/response events. Such copies explicitly do not acquire NEXUS governance authority.

The adapter never calls NEXUS Stenographer operations and never requests hidden chain-of-thought. Visible phase submissions and ballot rationales are public/runtime-visible NEXUS outputs. If a parent response exposes fields labelled as hidden/private reasoning, scratchpad, reasoning trace, or chain-of-thought, CONTROL fails closed rather than persisting them.

```text
CONTROL_INVOKES_COUNCIL != CONTROL_OWNS_COUNCIL
NEXUS_SESSION != CONTROL_REINTERPRETATION
CONTROL_RECEIPT_COPY != NEXUS_WORLDSTORE_WRITE
CONTROL_CAN_OVERRIDE_VOTE_WEIGHT = false
CONTROL_CAN_OVERRIDE_BALLOTS = false
CONTROL_CAN_OVERRIDE_CONSENSUS_THRESHOLD = false
NEXUS_OWNS_WORLDSTORE_HISTORY = true
VISIBLE_NEXUS_OUTPUT != HIDDEN_CHAIN_OF_THOUGHT
```

## Model-state reproducibility boundary

Phase 4 implements an immutable `qsol-control-model-state/1` registry for externally inspectable computational circumstances.

A canonical state may record:

```text
model provider/runtime/version/id/revision/quantization
model/weight/tokenizer hashes when locally verifiable
sampling/context/seed/stochastic metadata
Council seat and NEXUS mode
tool/filesystem/network/plugin permission envelope
CONTROL/NEXUS/ORACLE/SUBSTRATE/ARK/INT identities
exact Collection snapshot identity
hardware/runtime metadata
```

Every canonical field has one provenance class:

```text
observed
provider_reported
locally_verified
inferred
unknown
```

Unclassified fields become `unknown`. A provider-reported identifier is not promoted to locally verified merely because CONTROL stored it.

### Artifact identity boundary

Local model, weights, or tokenizer paths may be inspected for hashing. The paths and bytes do not enter canonical records.

```text
regular file     -> sha256(exact file bytes)
sharded directory -> sha256(canonical relative-path/file-hash/size manifest)
```

Directory identity is explicitly a manifest identity, not a fabricated byte-stream hash.

```text
HASH_IDENTITY != ARTIFACT_BYTES
PROVIDER_REPORTED != LOCALLY_VERIFIED
```

### Run linkage

The full Phase 4 registry record is canonical and is bound to `system.control_run_id`.

Phase 1B already has a compact `model_state` event shape. The public Phase 4 runtime therefore appends a backward-compatible event **projection** with `record_refs=[state_id]`; it does not redefine the older event schema in place.

```text
CANONICAL_REGISTRY_RECORD != RUN_EVENT_PROJECTION
COARSE_PROVENANCE != FIELD_LEVEL_PROVENANCE
```

The projection's legacy coarse provenance field is `unknown`, preventing a many-field provenance map from being collapsed into an unjustified stronger label.

### Comparison and archaeology

`qsol-control-model-state-comparison/1` and `qsol-control-model-state-run-comparison/1` compare recorded values and their provenance. They explicitly set model-mind inference to false.

`qsol-control-model-state-archaeology/1` is a deterministic self-describing export. It declares that model artifact bytes and local paths are absent and that hidden chain-of-thought/model-mind capture are false. RESTRICTED exports require explicit acknowledgement.

The future WebUI must use the pinned labels:

```text
Model-state reproducibility metadata
Not model mind
Metadata provenance
Unknown / not established
Provider reported
Locally verified
Inferred — not verified
Observed
```

```text
MODEL_STATE != MODEL_MIND
VISIBLE_OUTPUT != HIDDEN_CHAIN_OF_THOUGHT
RUNTIME_METADATA != CONSCIOUSNESS
MODEL_STATE_COMPARISON != MIND_COMPARISON
```

## Minimum ARK recovery gate

`qsol-control-ark-minimum-bundle/1` closes the Phase 1B offline persistence gate by reusing `QSOL-RESTORE-DAT/1` as the deterministic container for one interaction run and the canonical storage records required to verify it.

The minimum package includes:

```text
CONTROL-RECOVERY.json
lattice/profile.json
run record
complete append-only event chain
referenced File records
referenced raw objects
exact bound Collection descriptor + snapshot lineage to revision 0, when applicable
```

Derived search indexes, optional DNA projections, WebUI state and live service connections are not part of the minimum proof.

Verification reconstructs a fresh local CONTROL store and requires the recovered run fingerprint to match the source run fingerprint. If the source Collection has advanced since the run, the recovery store's local `HEAD` points to the **exact historical snapshot used by the run**, not the source store's newer `HEAD`.

```text
RECOVERY_BUNDLE != SEMANTIC_AUTHORITY
RECOVERY_HEAD != SOURCE_CURRENT_HEAD
HASH_INTEGRITY != EVIDENCE_AUTHORITY
RESTORED_CONTEXT != ORIGINAL_ASSISTANT_INSTANCE
```

CONTROL owns this packaging/verifier mechanism. QSOL-ARK remains the recovery-semantics authority.

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

CONTROL owns addressing and interaction packaging. ORACLE remains authoritative only for its own witnessed events; NEXUS remains authoritative only for its own WorldStore/governance mechanics. Model-state records provide reproducibility metadata and do not become evidence authority merely because they share run lineage.

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

The implemented Phase 1B interaction core binds:

```text
run_id
question payload/hash
requester_kind
requested_mode
file_refs
exact collection_snapshot_ref
oracle/nexus external refs when supplied
visible event payloads
model_state_refs when supplied
lattice_addresses
timestamps
replayability classification
```

Phase 3 supplies verified NEXUS session/receipt references and externally visible Council response artifacts that may be attached to an existing run through receipt and derived response events. Phase 4 supplies canonical model-state records bound by `system.control_run_id` plus compact `model_state` event projections referencing their `state_id`.

The immutable run record remains content-addressed. Its separate event chain is append-only with an atomic `HEAD`, explicit parent lineage, and stable event identities.

## Model-state record

Model-state capture is now implemented as a persistent reproducibility registry. It separates values from how those values were established and refuses hidden-cognition claims.

A future AI should be able to answer:

> What models participated, under what externally recorded conditions, which fields were actually verified, with what evidence/system versions, and what changed between runs?

It should **not** be told that CONTROL preserved private reasoning, consciousness, or an internal mind state that was never exposed.

## Replay classes

```text
R0 exact deterministic replay
R1 deterministic re-execution from preserved inputs
R2 same declared configuration but stochastic/live inference
R3 rerun with changed evidence/model/runtime state
```

Future replay must bind to exact historical Collection snapshots and verified external NEXUS/ORACLE references rather than current live state. Model-state metadata can explain configuration drift but does not upgrade stochastic execution into deterministic replay.

## Failure behavior

CONTROL should fail closed for authority-sensitive or ambiguous state and fail visibly for observational/display gaps.

Examples:

- unavailable/tampered ORACLE parent -> evidence adapter unavailable, not invented evidence;
- unknown ORACLE major -> fail closed, do not guess semantics;
- stale ORACLE evidence -> stale indicator, not automatically false;
- missing ORACLE evidence -> `unknown`, not invented evidence;
- unknown NEXUS major or missing required operation -> Council adapter unavailable;
- NEXUS session/receipt content-address mismatch -> reject the run render;
- NEXUS threshold/tally/ballot-commitment/minority mismatch -> reject rather than normalize;
- hidden-reasoning-labelled field from NEXUS -> reject rather than persist;
- model-state credential/hidden-reasoning-labelled field -> reject before persistence;
- contradictory model-state Collection snapshot -> reject rather than detach state from its run;
- local artifact symlink/unsafe entry -> reject rather than hash ambiguous content;
- ambiguous cross-run model-state alignment key -> reject rather than guess correspondence;
- stale semantic index -> unavailable until rebuilt, not silently searched against wrong membership;
- Collection privacy mismatch -> membership update rejected;
- corrupt raw object -> verification failure;
- incomplete minimum ARK bundle -> offline reconstruction failure even if the outer container hashes correctly;
- malformed DNA projection -> decode failure, not partial reconstruction;
- model metadata missing -> `unknown`, not guessed from model name;
- replay mismatch -> explain changed inputs rather than claiming exact replay.

## Non-goals

QSOL-CONTROL is not:

- another AI Council;
- another ORACLE or an ORACLE ledger writer;
- a replacement for SUBSTRATE;
- a replacement for ARK recovery authority;
- a NEXUS governance fork or WorldStore editor;
- a truth-scoring engine;
- a hidden chain-of-thought recorder;
- a model-mind, consciousness, or sentience detector;
- a model-weight archive merely because it can hash local model artifacts;
- a blockchain;
- a vector database promoted to epistemic authority;
- a biological DNA storage claim;
- a claim that φ is physically optimal for data storage;
- a geometric theory of cognition;
- a reason to duplicate NEXUS in a frontend framework.
