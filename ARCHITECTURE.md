# QSOL-CONTROL Architecture

## Purpose

QSOL-CONTROL is the human and machine **operator plane** for the QSOL ecosystem. It connects operator interfaces to existing authorities without absorbing those authorities.

```text
SUBSTRATE  - KNOWS
ARK        - SURVIVES
INT        - COMPOSES
ORACLE     - WITNESSES
NEXUS      - REASONS
CONTROL    - OPERATES
LATTICE    - REMEMBERS
```

The first three remain the Three-Pillar foundation. ORACLE and NEXUS provide the witness/reasoning membrane. CONTROL is the operator surface. Lattice memory, persistent Files/Collections, search indexes, the model-state registry, and DNA projections are storage or reproducibility mechanisms inside CONTROL, not authority-bearing pillars.

## Authority matrix

| Concern | Owner | CONTROL role |
|---|---|---|
| Public epistemic state / provenance | QSOL-SUBSTRATE | display/query |
| Recovery / reconstruction | QSOL-ARK | request/display/export |
| Composition / drift | QSOL-INT | display/query |
| Witness observations / temporal contracts | QSOL-ORACLE | read/query/store refs only |
| Council reasoning / vote mechanics / WorldStore history | QSOL-NEXUS | discover/invoke/verify/render/store refs only |
| Human + AI orchestration | QSOL-CONTROL | owner |
| Persistent File/Collection mechanics | QSOL-CONTROL | storage mechanics only |
| Human WebUI | QSOL-CONTROL | local operator interface only |
| AI / agent API | QSOL-CONTROL | structured local orchestration interface only |
| Interaction/lattice placement | CONTROL lattice layer | storage/addressing only |
| Model-state reproducibility registry | QSOL-CONTROL | metadata storage/comparison only |
| Minimum CONTROL recovery packaging | QSOL-CONTROL | packaging/verifier only; ARK retains recovery authority |
| Lexical/vector indexes | CONTROL derived storage | zero semantic authority |
| DNA/codon projection | CONTROL recovery projection | zero semantic authority |

Ownership of storage mechanics does not confer truth authority. Invocation authority does not confer authority to rewrite the invoked system. Recording model/runtime metadata does not confer access to hidden cognition.

## Control surfaces

### Human surface: implemented Phase 5

The Human WebUI is implemented as `qsol-control-webui/1`:

```text
webui/server.py
tools/webui.py
webui/static/
ai/webui-contract.json
```

The server is local and loopback-only. It reuses the existing CONTROL storage, ORACLE, NEXUS, model-state, lattice, and DNA runtimes instead of creating a parallel application authority layer.

Implemented views:

```text
ASK
EVIDENCE
COUNCIL
MINORITY
SOURCES
TIMELINE
RECEIPTS
MODELS
MEMORY
DNA
REPLAY / COMPARE
COLLECTIONS
HEALTH
```

The composer exposes exactly:

```text
Evidence only
Ask Council
```

The UI shows provenance and uncertainty explicitly and never derives a synthetic truth percentage from votes, confidence, model count, consensus, search similarity, codon frequency, or lattice position.

### Machine surface: implemented Phase 6

The machine interface is implemented as `qsol-control-agent-api/1` with a transport-neutral dispatcher and dependency-free JSONL/stdio transport:

```text
api/common.py
api/runtime.py
api/dispatcher.py
api/stdio.py
tools/agent_api.py
ai/agent-api-contract.json
schema/agent-api-request.schema.json
schema/agent-api-response.schema.json
```

Implemented operations:

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
```

`control.replay` is intentionally absent. Actual replay execution remains Phase 7.

The machine API does not reuse the browser HTTP routes as its public contract. Both surfaces instead converge on the same CONTROL runtime/storage primitives and the same ORACLE/NEXUS/model-state/lattice implementations.

```text
HUMAN_CALLER_AUTHORITY == AI_CALLER_AUTHORITY
API_ACCESS != EPISTEMIC_PRIVILEGE
```

AI-originated runs preserve `requester_kind: ai`; human-originated API runs preserve `requester_kind: human`. Caller kind is provenance, not an authority upgrade.

The first transport is local stdio, not a remote multi-user service. Phase 6 therefore does not silently expand the Phase 5 network/browser trust boundary.

## Local WebUI security boundary

Phase 5 adds a concrete local browser boundary:

```text
DEFAULT_BIND = 127.0.0.1
REMOTE_MULTI_USER_DEPLOYMENT = false
CORS = disabled
SESSION_TOKEN = required after bootstrap
NON_LOOPBACK_HOST = rejected
STATE_CHANGING_ORIGIN = same loopback host/port when supplied
```

Responses also use Content Security Policy, `nosniff`, no-referrer, same-origin resource policy, and `no-store` caching. Retrieved records enter the DOM through `textContent`; the client does not use `innerHTML` for untrusted records.

The Host check is important because loopback binding alone does not prevent straightforward DNS-rebinding attacks where an attacker-controlled hostname resolves to `127.0.0.1`.

This is a Phase 5 local baseline. The broader Phase 10 network/browser threat model remains open.

## Agent API resource boundary

Phase 6 applies deterministic process-local budgets rather than inventing an authorization hierarchy:

```text
request bytes                         8 MiB
response bytes                        8 MiB
File upload                           4 MiB
requests per caller / process         1000
mutating requests per caller/process  200
model states per response             100
lattice records per response          1000
runs per lattice trace                100
```

Quotas control resource consumption only. Remaining quota never changes truth, evidence, vote, provenance, or model-state authority.

The machine request boundary recursively rejects explicit attempts to supply synthetic truth fields, epistemic privilege, ORACLE write controls, WorldStore mutation controls, Council governance overrides, hidden/private reasoning controls, or credential-labelled control fields.

The underlying adapters still revalidate their own authority boundaries. The API firewall is defence in depth, not a replacement for parent validation.

## Query lifecycle

Human WebUI and machine API share the same semantic lifecycle:

```text
1. caller submits bounded question
2. mode is explicit: evidence_only or council
3. attached/source Files are canonical CONTROL Files
4. selected Collection binds to one exact immutable snapshot
5. CONTROL queries read-only ORACLE when configured
6. known / conflict / unknown remain explicit
7. CONTROL creates immutable interaction record with caller kind
8. evidence event preserves the ORACLE result or explicit unknown
9. if mode=council, CONTROL invokes existing verified NEXUS council.run path
10. NEXUS owns roster, phases, ballots, threshold, WorldStore, and receipts
11. CONTROL returns/renders verified externally visible output
12. CONTROL may persist reference-only NEXUS artifacts/events
13. participating executions may have Phase 4 model-state records
14. model-state provenance remains field-specific
15. views keep evidence, Council, provenance, model metadata, memory, and comparison lanes separate
```

Retrieval rank is not evidence status. Council consensus is not evidence status. Model identity/configuration is not evidence status. Machine structure does not create additional epistemic privilege.

## Persistent Files and Collections

```text
FILE
  raw bytes -> sha256 object identity
  immutable metadata -> file_id

COLLECTION
  persistent named set of File references
  immutable membership snapshots
  atomic HEAD pointer
```

A File may belong to several Collections without duplicating raw bytes. Collection membership cannot reduce privacy classification.

The WebUI supports Collection creation, exact snapshot inspection, add/remove membership through compare-and-swap, and deterministic lexical search. The Phase 6 API supports Collection creation with optional initial File membership, exact current/historical snapshot reads, and deterministic lexical search through the same storage implementation.

A run stores the exact Collection snapshot used. Later movement of the Collection `HEAD` does not rewrite historical run context.

```text
RUN_COLLECTION_SNAPSHOT != CURRENT_COLLECTION_HEAD
COLLECTION_MEMBERSHIP != ENDORSEMENT
```

## Search architecture

Search indexes are projections over exact Collection snapshots.

Implemented storage includes a deterministic lexical baseline and externally supplied semantic vector indexes. Embedding generation remains outside canonical storage.

```text
SEARCH_SCORE != TRUTH
SEMANTIC_SIMILARITY != EVIDENCE_STRENGTH
INDEX != CANONICAL_MEMORY
```

## ORACLE boundary

CONTROL's `qsol-control-oracle-adapter/1` is read-only.

Before evidence queries it discovers the parent contract and verifies ORACLE's append-only ledger. Queries preserve exact `known`, `conflict`, or `unknown`, observation refs, provenance, timestamps, freshness, and missing-evidence/search-suggestion state.

Both the WebUI and Phase 6 API use this adapter. Neither has an alternative ORACLE mutation path.

CONTROL may not:

- manufacture or append ORACLE history;
- relabel ORACLE history;
- upgrade a copied receipt into ORACLE authority;
- promote NEXUS output into primary evidence;
- treat a suggested search as evidence;
- treat freshness as truth;
- treat timelock eligibility as publication execution.

```text
ORACLE_REFERENCE != CONTROL_AUTHORITY
ORACLE_RECEIPT_COPY != ORACLE_LEDGER_APPEND
FRESH != TRUE
STALE != FALSE
SUGGESTED_SEARCH != EVIDENCE
ELIGIBLE != EXECUTED
CONTROL_CALL != ORACLE_AUTHORITY
```

## NEXUS governance boundary

CONTROL implements `qsol-control-nexus-adapter/1` over NEXUS local JSONL/stdio.

Each adapter session discovers parent health/operations and requires the operations needed for Council verification. The CONTROL mutation surface exposes only:

```text
council.run
```

The adapter does not expose generic operation passthrough, `world.create`, Stenographer reads, vote-weight mutation, ballot mutation, roster-authority mutation, or consensus-threshold mutation.

After Council execution CONTROL resolves and verifies committed WorldStore session/receipt objects, ballot commitments, tally, exact threshold, minority reports, and optional epoch admission evidence before rendering/persistence.

The WebUI and agent API both delegate Council work to this adapter. They do not create a second governance path.

```text
CONTROL_INVOKES_COUNCIL != CONTROL_OWNS_COUNCIL
CONTROL_CAN_WORLD_CREATE = false
CONTROL_CAN_OVERRIDE_VOTE_WEIGHT = false
CONTROL_CAN_OVERRIDE_BALLOTS = false
CONTROL_CAN_OVERRIDE_CONSENSUS_THRESHOLD = false
NEXUS_OWNS_WORLDSTORE_HISTORY = true
VISIBLE_NEXUS_OUTPUT != HIDDEN_CHAIN_OF_THOUGHT
CONTROL_CALL != NEXUS_GOVERNANCE
```

## Model-state reproducibility boundary

Phase 4 implements immutable `qsol-control-model-state/1` records.

A record may contain externally inspectable provider/runtime/model/revision/quantization data, local artifact hashes, sampling/context/seed data, Council seat/mode, tool permission envelope, system snapshot identities, and relevant runtime hardware metadata.

Every canonical field uses one provenance class:

```text
observed
provider_reported
locally_verified
inferred
unknown
```

The Phase 5 model-state inspector loads the labels directly from `ai/model-state-contract.json` and fails if they drift. Phase 6 exposes the same canonical registry through bounded `control.models.get` views.

```text
Model-state reproducibility metadata
Not model mind
Metadata provenance
Unknown / not established
Locally verified
Provider reported
Inferred - not verified
Observed
```

```text
MODEL_STATE != MODEL_MIND
VISIBLE_OUTPUT != HIDDEN_CHAIN_OF_THOUGHT
RUNTIME_METADATA != CONSCIOUSNESS
PROVIDER_REPORTED != LOCALLY_VERIFIED
HASH_IDENTITY != ARTIFACT_BYTES
MODEL_STATE_COMPARISON != MIND_COMPARISON
```

The full registry record remains canonical. The older Phase 1B model-state event is a compact backward-compatible lineage projection that references the canonical `state_id`.

## Lattice memory

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

The WebUI renders all 27 top-level logical cells and resolves them to ordinary run/event records. Phase 6 exposes the same view plus bounded lattice-prefix tracing with explicit run and record ceilings.

```text
LATTICE_ADDRESS != COLLECTION_MEMBERSHIP
LATTICE_ADDRESS != TRUTH
GEOMETRY != TRUTH
```

## DNA / codon recovery projection

The reversible codec maps File bytes into `A/C/G/T`, codons, and one of two versioned traversals:

```text
qsol.lexicographic-27/1
qsol.phi-stride-27/1
```

The WebUI can inspect and export projections. A RESTRICTED export requires explicit acknowledgement that the projection is reversible sensitive data and emits a CONTROL audit event.

```text
RAW_BYTES = CANONICAL
DNA_PROJECTION = DERIVED
DNA_ENCODING != BIOLOGICAL_CLAIM
PHI_TRAVERSAL != PHYSICAL_TRUTH
CODON_FREQUENCY != EVIDENCE
```

## Interaction and recovery

The Phase 1B interaction core preserves content-addressed runs plus append-only events, exact File refs, exact Collection snapshot refs, ORACLE/NEXUS refs, model-state refs, lattice addresses, timestamps, and replayability class.

The minimum ARK bundle packages one run, its event chain, referenced File/raw objects, exact Collection snapshot lineage, and lattice profile inside `QSOL-RESTORE-DAT/1`, then proves reconstruction with run fingerprint equality.

```text
RECOVERY_BUNDLE != SEMANTIC_AUTHORITY
RECOVERY_HEAD != SOURCE_CURRENT_HEAD
HASH_INTEGRITY != EVIDENCE_AUTHORITY
RESTORED_CONTEXT != ORIGINAL_ASSISTANT_INSTANCE
```

ARK remains the recovery-semantics authority.

## Replay / compare boundary

Phase 5 and Phase 6 expose views comparing immutable stored runs and their model-state metadata.

Neither executes Phase 7 replay:

```text
comparison_is_replay_execution = false
phase7_replay_execution_implemented = false
```

A later run never overwrites an earlier run.

## UI / API invariant

Neither operator surface manufactures a synthetic truth percentage derived from:

```text
votes
confidence
entropy
model count
consensus
retrieval score
embedding similarity
codon frequency
lattice position
```

```text
CONTROL_DISPLAY != AUTHORITY
CONTROL_OPERATION != TRUTH
VOTE != EVIDENCE
CONSENSUS != TRUTH
SEARCH_SCORE != TRUTH
SEMANTIC_SIMILARITY != EVIDENCE_STRENGTH
CODON_FREQUENCY != EVIDENCE
LATTICE_ADDRESS != TRUTH
API_ACCESS != EPISTEMIC_PRIVILEGE
```

## Failure behavior

CONTROL fails closed for authority-sensitive ambiguity and visibly for display/API gaps.

Examples:

- ORACLE unavailable -> evidence remains `unknown`, not invented;
- unknown ORACLE major -> adapter unavailable;
- stale ORACLE observation -> stale indicator, not automatically false;
- NEXUS unavailable -> Council view unavailable, no fake Council result;
- invalid/tampered NEXUS ballot/session/receipt -> reject render/persistence;
- hidden-reasoning-labelled NEXUS field -> reject;
- missing model metadata -> `unknown`;
- provider-reported model metadata -> never auto-promote to locally verified;
- stale semantic index -> unavailable for new snapshot;
- corrupt raw File object -> verification failure;
- malformed DNA projection -> decode failure;
- non-loopback WebUI bind or Host -> reject;
- invalid WebUI session token -> reject browser API access;
- cross-origin browser mutation -> reject;
- malformed/duplicate-member agent JSON -> typed `INVALID_JSON` failure;
- machine authority-escalation fields -> typed `AUTHORITY_ESCALATION` failure;
- caller/request/lattice limits exceeded -> typed quota/resource failure;
- replay comparison -> comparison only, not replay execution.

## Non-goals

QSOL-CONTROL is not:

- another truth engine;
- another ORACLE ledger writer;
- a NEXUS governance fork;
- a hidden chain-of-thought recorder;
- a model-mind or consciousness capture system;
- an embedding provider;
- a literal cognitive geometry claim;
- a biological interpretation of the DNA codec;
- a remote multi-user service in Phase 6;
- the Phase 7 replay engine.

## Implementation map

```text
storage/control_store.py          persistent Files / Collections / indexes
storage/interaction_store.py      immutable runs / append-only events
storage/model_state_registry.py   Phase 4 model-state registry
adapters/oracle.py                read-only ORACLE adapter
adapters/nexus.py                 verified NEXUS Council adapter
storage/dna_lattice.py            reversible DNA/lattice projection
webui/server.py                   Phase 5 Human WebUI facade
webui/http.py                     browser / HTTP security boundary
webui/runtime_*.py                shared WebUI orchestration and inspection
webui/static/                     framework-free browser client
tools/webui.py                    human operator launcher
api/common.py                     Phase 6 protocol, limits, errors
api/runtime.py                    machine facade over shared CONTROL runtime
api/dispatcher.py                 fixed operation dispatcher and quotas
api/stdio.py                      bounded JSONL/stdio transport
tools/agent_api.py                machine API launcher
ai/webui-contract.json            machine-readable Phase 5 boundary
ai/agent-api-contract.json        machine-readable Phase 6 boundary
```

See `README.md`, `README4AI.md`, `docs/WEBUI.md`, `docs/AI-API.md`, `docs/AGENT-API.md`, `docs/MODEL-STATE.md`, `AGENTS.md`, `SECURITY.md`, and `ROADMAP.md` for the corresponding human/machine surfaces.
