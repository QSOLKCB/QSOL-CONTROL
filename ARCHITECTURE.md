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

The first three remain the Three-Pillar foundation. ORACLE and NEXUS provide the witness/reasoning membrane. CONTROL is the operator surface. Lattice memory, persistent Files/Collections, search indexes, model-state metadata, replay records, and DNA projections are storage/reproducibility mechanisms inside CONTROL, not authority-bearing pillars.

The completed local-core semantic baseline is contract `2.6.0`. Post-roadmap remote/mobile/consensus capabilities are optional extensions registered separately in `extensions/manifest.json`; they do not turn the local WebUI or local Agent API into a different authority system.

```text
CORE_2_6_0 != EXTENSION_SURFACE
OPTIONAL_EXTENSION != CORE_AUTHORITY
```

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
| Replay orchestration/reports | QSOL-CONTROL | classify/rerun/compare/store lineage only |
| Human WebUI | QSOL-CONTROL | local operator interface only |
| AI / agent API | QSOL-CONTROL | structured local orchestration interface only |
| Optional remote Agent gateway | QSOL-CONTROL extension | authenticated transport + record authorization + audit only |
| External consensus coordination | QSOL-CONTROL extension + external provider | intent/receipt validation only; provider owns quorum formation |
| Native mobile reference clients | QSOL-CONTROL extension | thin HTTPS clients only |
| Interaction/lattice placement | CONTROL lattice layer | storage/addressing only |
| Model-state reproducibility registry | QSOL-CONTROL | metadata storage/comparison only |
| Minimum CONTROL recovery packaging | QSOL-CONTROL | packaging/verifier only; ARK retains recovery authority |
| Lexical/vector indexes | CONTROL derived storage | zero semantic authority |
| DNA/codon projection | CONTROL recovery projection | zero semantic authority |

Ownership of storage mechanics does not confer truth authority. Invocation authority does not confer authority to rewrite the invoked system. Recording model/runtime metadata does not confer access to hidden cognition. Replay, network access, and quorum receipts change none of those rules.

## Control surfaces

### Human surface

The local Human WebUI is `qsol-control-webui/1`:

```text
webui/server.py
webui/http.py
webui/runtime_*.py
webui/static/
tools/webui.py
```

The Phase 7 replay panel adds:

```text
CLASSIFY REPLAY
EXECUTE CLASSIFIED REPLAY
COMPARE IMMUTABLE RUNS
RECURRING-QUESTION TIMELINE
```

Replay POST requests use the existing loopback, session-token, and same-origin mutation boundary. The Human WebUI remains loopback-only even when the optional remote Agent gateway is enabled.

### Machine surface

The completed-core machine interface remains `qsol-control-agent-api/1` over bounded JSONL/stdio. Phase 7 extends its exact operation catalogue with:

```text
control.replay.classify
control.replay.execute
control.replay.get
control.research.timeline
```

`control.replay.execute` is quota-governed as a mutation. The API does not gain an alternate ORACLE write path or NEXUS governance path.

```text
HUMAN_CALLER_AUTHORITY == AI_CALLER_AUTHORITY
API_ACCESS != EPISTEMIC_PRIVILEGE
```

### Optional remote Agent API extension

PR #15 adds `qsol-control-remote-gateway/1` as a separately versioned network transport over the existing Agent API dispatcher:

```text
remote/mobile client
      |
      | HTTPS POST /v1/agent
      v
api/remote_http.py
      |
      +-- bearer digest -> fixed principal
      +-- per-principal operation allowlist
      +-- privacy ceiling + record-level ACL
      +-- durable credential-free principal audit
      +-- 60-second renewable quota window
      +-- bounded concurrent connections + socket timeout
      |
      v
AgentAPIDispatcher
      |
      v
same CONTROL runtime
```

The remote request envelope contains no caller object. The gateway creates the local caller identity from authenticated configuration and then authorizes record scope before dispatch. PUBLIC Files/Collections can be shared within the principal privacy ceiling; non-public records require explicit ACL or audit-derived ownership. Runs, replays, and model-state records are never globally readable merely because their IDs are known.

The public server factory revalidates non-loopback/TLS, host, principal, and certificate policy even for programmatically constructed config objects. Non-loopback binds require TLS; the remote gateway never exposes the Human WebUI.

```text
AUTHENTICATION != RECORD_AUTHORIZATION
CLIENT_IDENTITY != SELF_ASSERTED_CALLER_IDENTITY
REMOTE_GATEWAY != REMOTE_WEBUI
REMOTE_ACCESS != EPISTEMIC_PRIVILEGE
```

### Optional external consensus extension

`qsol-control-consensus-adapter/1` does not embed Raft/Paxos or mutate CONTROL storage directly. It accepts only fully validated known CONTROL mutation intents, binds them to the expected current store fingerprint, delegates quorum formation to an external provider, bounds provider stdout/stderr while the child is running, validates the returned receipt, and performs a second provider receipt-verification call.

```text
CONSENSUS_RECEIPT != SEMANTIC_AUTHORITY
QUORUM != TRUTH
COORDINATION != EVIDENCE
EXTERNAL_CONSENSUS != CONTROL_STORAGE_REWRITE
```

## Query lifecycle and replay-basis capture

Human WebUI and machine API share the same semantic question lifecycle:

```text
1. caller submits bounded question
2. mode is explicit: evidence_only or council
3. attached Files are canonical CONTROL Files
4. selected Collection binds to one exact immutable snapshot
5. CONTROL queries read-only ORACLE
6. known / conflict / unknown remain explicit
7. CONTROL creates immutable run
8. CONTROL appends qsol-control-replay-basis/1 receipt
9. evidence event preserves ORACLE result or explicit unknown
10. optional Council goes through verified NEXUS council.run
11. visible outputs/receipts/model-state refs remain separate lanes
```

The replay-basis receipt is append-only and therefore does not change the run ID. It records execution inputs that matter to Phase 7, including the exact Collection ref and declared request configuration.

Current `control.ask` does not perform Collection search. Therefore its replay basis records:

```text
retrieval_index.status = not_used
```

For a pre-Phase-7 run with no replay-basis receipt:

```text
retrieval_index.status = not_recorded
```

These are intentionally different states.

```text
NOT_USED != NOT_RECORDED
LEGACY_MISSING_INDEX != INVENTED_INDEX
```

## Phase 7 replay architecture

```text
ORIGINAL IMMUTABLE RUN
        |
        v
ReplayRuntimeMixin.replay_classify
        |
        +-- inspection/unavailable -> no mutation
        |
        v
ReplayRuntimeMixin.replay_execute
        |
        +-- shared control.ask path
        +-- exact historical Collection snapshot
        +-- current ORACLE evidence
        +-- current configured NEXUS/runtime
        |
        v
NEW IMMUTABLE REPLAY RUN
        |
        v
qsol-control-replay-report/1
        |
        v
qsol-control-replay-record/1
```

Replay metadata storage:

```text
records/replays/<sha256>.json
records/replay-reports/<sha256>.json
```

`ReplayStore` requires canonical JSON and content-addressed identities. The original run/event chain is never stored under these paths and never rewritten by replay.

### Replay classification

Classification is a technical reproducibility label, not an epistemic score. It distinguishes conditions such as:

```text
inspection_only
unavailable_original_context
current_evidence_rerun
legacy_current_evidence_rerun
evidence_refresh_only
council_configuration_unavailable
changed_configuration_rerun
live_stochastic_rerun
legacy_declared_input_reexecution
declared_input_reexecution
```

No Phase 7 classification claims exact reproduction of hidden provider state.

### Exact historical Collection snapshot

A replay run reuses the original run's exact `collection_id` and `snapshot_id`. It does **not** use current Collection HEAD as replay input.

Current HEAD is read separately to report longitudinal membership drift.

```text
REPLAY_COLLECTION_SNAPSHOT = ORIGINAL_COLLECTION_SNAPSHOT
CURRENT_COLLECTION_HEAD != ORIGINAL_COLLECTION_SNAPSHOT
```

### Current evidence

Replay queries ORACLE at replay time through the existing read-only adapter. The report compares original and replay evidence refs/states.

```text
CURRENT_EVIDENCE != ORIGINAL_EVIDENCE
FRESH != TRUE
STALE != FALSE
```

### Council configuration

The original committed Council roster is compared with the currently configured roster. If they differ, execution requires an explicit `allow_changed_configuration` acknowledgement. A changed roster is then recorded as changed configuration, not hidden.

Replay Council execution still uses only the reviewed NEXUS `council.run` adapter surface.

### Model/runtime metadata

Replay reports call the Phase 4 model-state `compare_runs` machinery. Model revision/runtime/configuration differences remain reproducibility metadata only.

```text
MODEL_STATE != MODEL_MIND
MODEL_STATE_COMPARISON != MIND_COMPARISON
```

### Original-result immutability

Before and after replay, CONTROL content-hashes the original:

```text
run record
append-only event chain
model-state records bound to the run
```

A mismatch fails replay. The new replay run receives a `qsol-control-replay-link/1` receipt; the original run receives no replay mutation.

```text
ORIGINAL_RUN != REPLAY_RUN
ORIGINAL_RESULT_IMMUTABLE = true
```

## Deterministic comparison reports

`qsol-control-replay-report/1` is canonical JSON and content-addressed. Its lanes are deliberately independent:

```text
EVIDENCE SET
COLLECTION MEMBERSHIP
RETRIEVAL / INDEX BASIS
COUNCIL ROSTER + NEXUS RUNTIME
MODEL REVISION / RUNTIME METADATA
REQUEST CONFIGURATION
```

There is no aggregate truth/fidelity percentage.

## Longitudinal research

`qsol-control-research-timeline/1` groups exact recurring questions by `question_sha256`, orders runs by `(created_at, run_id)`, and emits adjacent-run transitions.

Transitions may identify evidence additions/removals, Collection snapshot changes, Council roster changes, model-state changes, and runtime changes.

```text
TIMELINE != TRUTH
CHANGE != IMPROVEMENT
CONSENSUS_CHANGE != EVIDENCE_CHANGE
```

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

A run stores the exact Collection snapshot used. Later movement of `HEAD` does not rewrite historical run context.

```text
RUN_COLLECTION_SNAPSHOT != CURRENT_COLLECTION_HEAD
COLLECTION_MEMBERSHIP != ENDORSEMENT
```

## Search architecture

Search indexes are derived projections over exact Collection snapshots. Existing storage has deterministic lexical indexes and externally supplied semantic-vector indexes.

```text
SEARCH_SCORE != TRUTH
SEMANTIC_SIMILARITY != EVIDENCE_STRENGTH
INDEX != CANONICAL_MEMORY
```

A future operation that actually uses an index as replay-critical input must record its exact index descriptor in the replay basis. Phase 7 does not infer past index use from the mere existence of an index.

## ORACLE boundary

CONTROL's ORACLE adapter remains read-only during replay.

CONTROL may not manufacture, append, rewrite, or relabel ORACLE history. Current evidence is a new observation context, not a replacement for historical evidence.

```text
ORACLE_REFERENCE != CONTROL_AUTHORITY
CONTROL_CALL != ORACLE_AUTHORITY
CURRENT_EVIDENCE != ORIGINAL_EVIDENCE
```

## NEXUS governance boundary

CONTROL still exposes only `council.run` as the governance-bearing NEXUS mutation. Replay does not add generic operation passthrough, WorldStore creation, vote-weight changes, ballot changes, roster-authority changes, or threshold changes.

```text
CONTROL_INVOKES_COUNCIL != CONTROL_OWNS_COUNCIL
CONTROL_CALL != NEXUS_GOVERNANCE
CONSENSUS != TRUTH
VOTE != EVIDENCE
```

## Lattice / DNA / recovery boundaries

Lattice addresses and DNA projections remain storage/recovery projections with zero truth authority.

```text
LATTICE_ADDRESS != TRUTH
GEOMETRY != TRUTH
DNA_PROJECTION = DERIVED
CODON_FREQUENCY != EVIDENCE
```

ARK remains recovery-semantics authority. Phase 8 widens the existing one-run recovery machinery into a broader repository/system recovery package.

## Failure behavior

CONTROL fails closed for authority-sensitive or reproducibility-sensitive ambiguity.

Examples:

- original Collection snapshot missing -> `unavailable_original_context`;
- replayability R0 -> inspection only;
- Council requested but NEXUS unconfigured -> evidence refresh only;
- Council roster changed -> explicit authorization required;
- legacy index metadata absent -> `not_recorded`, never invented;
- original run changes during replay -> replay failure;
- ORACLE unavailable -> current evidence remains unknown/unavailable;
- model metadata missing -> remains missing;
- arbitrary run comparison -> still comparison, not replay execution;
- remote record not in principal ACL/ownership -> access denied;
- non-loopback remote config without TLS -> server construction rejected;
- external consensus output exceeds bound -> provider terminated and request fails.

## Non-goals

The completed core QSOL-CONTROL is not:

- a truth engine;
- an ORACLE ledger writer;
- a NEXUS governance fork;
- a hidden chain-of-thought recorder;
- a model-mind capture system;
- an embedding provider;
- a literal cognitive geometry claim;
- a remote Human WebUI;
- an exact-replay oracle for unrecorded historical state.

The optional remote Agent gateway does not change those non-goals. Automatic truth scoring, hidden chain-of-thought capture, literal lattice-cognition claims, biological claims from the DNA codec, and physical-optimality claims from φ traversal are permanent non-goals under `ai/permanent-nongoals.json`.

## Implementation map

```text
storage/control_store.py          Files / Collections / indexes
storage/interaction_store.py      immutable runs / append-only events
storage/model_state_registry.py   model-state registry
storage/replay_store.py           content-addressed replay records/reports
adapters/oracle.py                read-only ORACLE adapter
adapters/nexus.py                 verified NEXUS Council adapter
adapters/consensus.py             optional external quorum coordination adapter
webui/runtime_replay.py           replay classification/execution/report/timeline
webui/http.py                     local browser transport/security
webui/static/                     human replay/compare/timeline surface
api/dispatcher.py                 local machine operation dispatch + quotas
api/remote_http.py                optional authenticated/authorized remote Agent gateway
extensions/manifest.json          optional extension machine registry
extensions/README4AI.md           optional extension AI bootstrap
ai/replay-contract.json           Phase 7 machine contract
ai/remote-gateway-contract.json   optional remote transport/authorization contract
ai/consensus-adapter-contract.json optional consensus adapter contract
schema/replay-record.schema.json  replay record contract
schema/replay-report.schema.json  deterministic report contract
schema/research-timeline.schema.json longitudinal timeline contract
```

See `README.md`, `README4AI.md`, `extensions/manifest.json`, `docs/POST-ROADMAP-EXTENSIONS.md`, `docs/REPLAY.md`, `docs/AGENT-API.md`, `AGENTS.md`, `SECURITY.md`, and `ROADMAP.md`.
