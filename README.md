# QSOL-CONTROL

**A human + AI control plane for the QSOL ecosystem, orchestrating ORACLE evidence, NEXUS Council reasoning, persistent Files and Collections, model-state reproducibility metadata, lattice memory, and deterministic recovery machinery.**

> **CONTROL controls the machinery, not reality.**
>
> A green button does not make a claim true. Six models agreeing does not make it true. A retrieval score of `0.97` does not make it true either. We remain committed to disappointing the dashboard industry.

QSOL-CONTROL now has two implemented operator surfaces over the same runtime:

- **Human control plane:** Phase 5 local loopback WebUI.
- **AI control plane:** Phase 6 structured JSONL/stdio agent API.

CONTROL owns orchestration and its own storage mechanics. It does **not** own scientific truth, public epistemic authority, NEXUS governance, ORACLE history, ARK recovery authority, hidden chain-of-thought, or a model mind.

## Architecture verbs

```text
QSOL-SUBSTRATE  KNOWS
QSOL-ARK        SURVIVES
QSOL-INT        COMPOSES
QSOL-ORACLE     WITNESSES
QSOL-NEXUS      REASONS
QSOL-CONTROL    OPERATES
LATTICE MEMORY  REMEMBERS
```

The first three remain the Three-Pillar foundation. ORACLE and NEXUS provide the witness/reasoning membrane. CONTROL is the operator surface. Files, Collections, model-state records, lattice addresses, indexes, and DNA projections are storage/reproducibility mechanisms, not new truth authorities.

## Phase 5 Human WebUI

Phase 5 implements `qsol-control-webui/1` as a standard-library Python loopback service plus a framework-free browser client.

```text
browser
  -> CONTROL WebUI
      -> CONTROL File / Collection / interaction storage
      -> read-only ORACLE adapter
      -> governance-preserving NEXUS Council adapter
      -> Phase 4 model-state registry
      -> lattice / DNA projection runtime
```

Start the storage-only UI:

```bash
python3 tools/webui.py --root .qsol-control-store
```

Add ORACLE:

```bash
python3 tools/webui.py \
  --root .qsol-control-store \
  --oracle-root /path/to/QSOL-ORACLE
```

Add ORACLE and local NEXUS:

```bash
python3 tools/webui.py \
  --root .qsol-control-store \
  --oracle-root /path/to/QSOL-ORACLE \
  --nexus-command-json '["python3","-m","nexus_runtime","--world","/secure/nexus-world"]' \
  --nexus-members council-members.json
```

Default address:

```text
http://127.0.0.1:8765
```

Phase 5 deliberately supports loopback only. Remote multi-user deployment remains deferred.

### WebUI views

The implemented browser surface provides:

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

The composer has exactly two modes:

```text
Evidence only
Ask Council
```

Browser attachments become ordinary content-addressed CONTROL Files. A selected Collection is bound to its exact immutable snapshot when the run is created. If the Collection later advances, the historical run still renders the snapshot it actually used.

The Collection UI supports create, browse, immutable membership snapshot updates with compare-and-swap, and deterministic lexical search.

### Browser security baseline

The local server enforces:

- loopback binds only: `127.0.0.1`, `::1`, or `localhost`;
- an unpredictable per-process WebUI session token;
- token authentication on API requests after session bootstrap;
- no CORS;
- non-loopback `Host` rejection to block the straightforward DNS-rebinding path;
- same-origin checks for state-changing browser requests when `Origin` is supplied;
- Content Security Policy with `frame-ancestors 'none'`, `object-src 'none'`, and `base-uri 'none'`;
- `X-Content-Type-Options: nosniff`;
- `Referrer-Policy: no-referrer`;
- `Cross-Origin-Resource-Policy: same-origin`;
- `Cache-Control: no-store`;
- DOM `textContent` for retrieved/untrusted record rendering rather than `innerHTML`.

This is a concrete local baseline, not a claim that the broader Phase 10 browser/network threat model is complete.

### UI invariant

CONTROL never manufactures a synthetic truth percentage from:

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
```

## Phase 6 AI / Agent API

Phase 6 implements `qsol-control-agent-api/1` as a dependency-free structured machine interface over the same runtime used by the Human WebUI.

The first transport is local JSONL over stdin/stdout:

```text
AI / AGENT
  -> qsol-control-agent-request/1
      -> AgentAPIDispatcher
          -> CONTROL storage/runtime
          -> read-only ORACLE adapter
          -> governed NEXUS Council adapter
          -> model-state registry
          -> lattice memory
```

Start it with:

```bash
python3 tools/agent_api.py --root .qsol-control-store
```

The operation surface is frozen and machine-readable:

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

The API uses deterministic process-local quotas, bounded request/response sizes, stable machine-readable error codes, and bounded lattice traversal. It exposes no ORACLE write operation, raw NEXUS passthrough, WorldStore mutation, ballot override, vote-weight control, threshold control, hidden chain-of-thought, or synthetic truth score.

AI-originated runs are recorded as `requester_kind: ai`, but AI callers receive exactly the same epistemic privilege as human callers:

```text
HUMAN_CALLER_AUTHORITY == AI_CALLER_AUTHORITY
API_ACCESS != EPISTEMIC_PRIVILEGE
CONTROL_CALL != ORACLE_AUTHORITY
CONTROL_CALL != NEXUS_GOVERNANCE
```

Remote multi-user deployment and actual replay execution are not implemented by Phase 6.

See [`docs/AI-API.md`](docs/AI-API.md), [`docs/AGENT-API.md`](docs/AGENT-API.md), and [`ai/agent-api-contract.json`](ai/agent-api-contract.json).

## Phase 4 model-state registry and inspector

CONTROL persists immutable `qsol-control-model-state/1` records for reproducibility and computational archaeology.

Records may preserve, where available:

```text
provider / runtime / runtime version / model ID / revision
model / weight / tokenizer hashes when locally verifiable
quantization
sampling configuration
context limit and seed
Council seat / NEXUS mode
tool permission envelope
CONTROL / NEXUS / ORACLE / SUBSTRATE / ARK / INT identities
exact Collection snapshot identity
relevant runtime hardware metadata
```

Every canonical field has explicit provenance:

```text
observed
provider_reported
locally_verified
inferred
unknown
```

The Phase 5 inspector loads the pinned labels directly from `ai/model-state-contract.json`:

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

The runtime fails if those Phase 4 labels drift. The UI never silently promotes provenance.

```text
MODEL_STATE != MODEL_MIND
VISIBLE_OUTPUT != HIDDEN_CHAIN_OF_THOUGHT
RUNTIME_METADATA != CONSCIOUSNESS
PROVIDER_REPORTED != LOCALLY_VERIFIED
HASH_IDENTITY != ARTIFACT_BYTES
MODEL_STATE_COMPARISON != MIND_COMPARISON
```

See [`docs/MODEL-STATE.md`](docs/MODEL-STATE.md), [`docs/WEBUI.md`](docs/WEBUI.md), and [`ai/model-state-contract.json`](ai/model-state-contract.json).

## Files, Collections, and retrieval

```text
FILE
= immutable raw content object + immutable metadata record
= may be attached directly to a run

COLLECTION
= persistent named group of File references
= immutable membership snapshots + atomic HEAD
= may have derived searchable indexes
```

Raw bytes remain canonical. Collection membership is not endorsement.

Search provides a deterministic lexical baseline and externally supplied semantic vector indexes bound to exact Collection snapshots.

```text
SEARCH_SCORE != TRUTH
SEMANTIC_SIMILARITY != EVIDENCE_STRENGTH
INDEX != CANONICAL_MEMORY
COLLECTION_MEMBERSHIP != ENDORSEMENT
```

See [`docs/PERSISTENT-STORAGE.md`](docs/PERSISTENT-STORAGE.md).

## ORACLE boundary

CONTROL implements the read-only `qsol-control-oracle-adapter/1` against `QSOL-ORACLE/1`.

The adapter verifies ORACLE's append-only ledger before evidence queries, preserves event/provenance references, exposes `known` / `conflict` / `unknown`, reports freshness separately from truth, and exposes the QSOL-CONTEXT 2056 timelock view.

CONTROL has no ORACLE write operation.

```text
ORACLE_REFERENCE != CONTROL_AUTHORITY
ORACLE_RECEIPT_COPY != ORACLE_LEDGER_APPEND
FRESH != TRUE
STALE != FALSE
SUGGESTED_SEARCH != EVIDENCE
ELIGIBLE != EXECUTED
```

See [`docs/ORACLE-ADAPTER.md`](docs/ORACLE-ADAPTER.md).

## NEXUS governance boundary

CONTROL implements `qsol-control-nexus-adapter/1` over NEXUS local JSONL/stdio.

The adapter discovers live operations, exposes only `council.run` as its governance-bearing mutation, resolves committed WorldStore session/receipt objects, verifies ballot commitments/tally/threshold/minority reports, and preserves NEXUS roster/phase order.

CONTROL does not expose direct `world.create`, generic NEXUS operation passthrough, Stenographer reads, vote-weight override, ballot override, roster-authority override, or consensus-threshold override.

```text
CONTROL_INVOKES_COUNCIL != CONTROL_OWNS_COUNCIL
CONTROL_CAN_WORLD_CREATE = false
CONTROL_CAN_OVERRIDE_VOTE_WEIGHT = false
CONTROL_CAN_OVERRIDE_BALLOTS = false
CONTROL_CAN_OVERRIDE_CONSENSUS_THRESHOLD = false
NEXUS_OWNS_WORLDSTORE_HISTORY = true
VISIBLE_NEXUS_OUTPUT != HIDDEN_CHAIN_OF_THOUGHT
```

See [`docs/NEXUS-ADAPTER.md`](docs/NEXUS-ADAPTER.md).

## Lattice memory

CONTROL defines a 3 x 3 x 3 logical interaction-memory lattice:

```text
X = information role   question | response | evidence
Y = epistemic role     observed | derived | unresolved
Z = temporal role      current | historical | recovery
```

The WebUI and agent API navigate the same 27-cell logical address space. Phase 6 additionally exposes bounded prefix tracing over stored run/event addresses.

```text
LATTICE_ADDRESS != COLLECTION_MEMBERSHIP
LATTICE_ADDRESS != TRUTH
GEOMETRY != TRUTH
```

See [`docs/LATTICE-MEMORY.md`](docs/LATTICE-MEMORY.md).

## DNA / lattice recovery projection

The reversible codec maps File bytes into `A/C/G/T`, codons, and one of the existing 27-cell traversal profiles:

```text
qsol.lexicographic-27/1
qsol.phi-stride-27/1
```

The WebUI can inspect and export the deterministic projection. RESTRICTED export requires explicit acknowledgement that the projection is reversible sensitive data and records an audit event.

```text
RAW_BYTES = CANONICAL
DNA_PROJECTION = DERIVED
DNA_ENCODING != BIOLOGICAL_CLAIM
PHI_TRAVERSAL != PHYSICAL_TRUTH
CODON_FREQUENCY != EVIDENCE
```

## Replay / comparison

Phase 5 and Phase 6 expose inspection/comparison views over immutable stored runs and model-state metadata.

They do **not** implement Phase 7 replay execution:

```text
comparison_is_replay_execution = false
phase7_replay_execution_implemented = false
```

The original runs remain immutable.

## Recovery

Phase 1B's `qsol-control-ark-minimum-bundle/1` provides deterministic offline reconstruction of one run, its event chain, referenced File/raw objects, exact Collection snapshot lineage, and lattice profile inside `QSOL-RESTORE-DAT/1`.

```text
RECOVERY_BUNDLE != SEMANTIC_AUTHORITY
RECOVERY_HEAD != SOURCE_CURRENT_HEAD
RESTORED_CONTEXT != ORIGINAL_ASSISTANT_INSTANCE
```

See [`docs/ARK-MINIMUM-BUNDLE.md`](docs/ARK-MINIMUM-BUNDLE.md).

## Validation

Validation is dependency-free and requires Python 3.11 or newer. CI uses Python 3.12.

```bash
python3 tools/validate_control.py
python3 tools/validate_restore_contracts.py
python3 tools/agent_api.py --help
python3 -W default -m unittest discover -s tests -v
```

Repository contract version is `2.2.0`. Public JSON Schemas use Draft 2020-12.

## Documentation map

- [`README4AI.md`](README4AI.md): compact machine bootstrap.
- [`AGENTS.md`](AGENTS.md): contributor/agent rules.
- [`ARCHITECTURE.md`](ARCHITECTURE.md): system design and authority boundaries.
- [`ROADMAP.md`](ROADMAP.md): phase sequence and completion state.
- [`SECURITY.md`](SECURITY.md): repository security boundaries.
- [`docs/WEBUI.md`](docs/WEBUI.md): implemented Phase 5 local Human WebUI.
- [`ai/webui-contract.json`](ai/webui-contract.json): machine-readable WebUI boundary.
- [`docs/AI-API.md`](docs/AI-API.md): implemented Phase 6 AI/agent interface overview.
- [`docs/AGENT-API.md`](docs/AGENT-API.md): exact Phase 6 protocol and operation behavior.
- [`ai/agent-api-contract.json`](ai/agent-api-contract.json): machine-readable Phase 6 boundary.
- [`docs/MODEL-STATE.md`](docs/MODEL-STATE.md): model-state registry and provenance.
- [`docs/PERSISTENT-STORAGE.md`](docs/PERSISTENT-STORAGE.md): Files, Collections, snapshots, and search.
- [`docs/ORACLE-ADAPTER.md`](docs/ORACLE-ADAPTER.md): read-only ORACLE adapter.
- [`docs/NEXUS-ADAPTER.md`](docs/NEXUS-ADAPTER.md): verified NEXUS Council adapter.
- [`docs/ARK-MINIMUM-BUNDLE.md`](docs/ARK-MINIMUM-BUNDLE.md): one-run offline recovery.
- [`manifest.json`](manifest.json): canonical machine map.

## Status

- PR #1: Phase 0 architecture/contracts bootstrap, merged.
- PR #2: Phase 1A persistent Files/Collections/retrieval/DNA projection, merged.
- PR #4: portable CONCAP delivery, merged.
- PR #5: Phase 1B interaction/lattice persistence, merged.
- PR #6: minimum ARK recovery gate + Phase 2 ORACLE adapter, merged.
- PR #7: Phase 3 NEXUS Council adapter, merged.
- PR #8: Phase 4 AI model-state registry, merged.
- PR #9: Phase 5 Human WebUI, merged.
- PR #10: Phase 6 structured AI / agent API, current implementation branch.

After Phase 6, the roadmap proceeds through Phase 7 replay/longitudinal research, the partly completed Phase 8 broader ARK recovery bridge, Phase 9 INT composition batteries, and the partly completed Phase 10 hardening/release discipline.

---

**QSOL-CONTROL controls the machinery, not reality. If the Council votes that the Moon is cheese and the retrieval engine returns `0.999`, CONTROL preserves what the systems did. It does not update astronomy. A model-state hash is paperwork, not a seance.**
