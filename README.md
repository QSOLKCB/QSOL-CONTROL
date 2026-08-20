# QSOL-CONTROL

**A human + AI control plane for the QSOL ecosystem, orchestrating ORACLE evidence, NEXUS Council reasoning, persistent Files and Collections, model-state reproducibility metadata, classified replay, lattice memory, deterministic recovery machinery, and INT-style composition conformance batteries.**

> **CONTROL controls the machinery, not reality.**
>
> A green button does not make a claim true. Six models agreeing does not make it true. A retrieval score of `0.97` does not make it true either. We remain committed to disappointing the dashboard industry.

QSOL-CONTROL has two implemented operator surfaces over the same runtime:

- **Human control plane:** Phase 5 local loopback WebUI, extended with Phase 7 replay/longitudinal views.
- **AI control plane:** Phase 6 structured JSONL/stdio agent API, extended with Phase 7 replay operations.

CONTROL owns orchestration, its own storage mechanics, recovery-package construction, and execution of its local conformance batteries. It does **not** own scientific truth, public epistemic authority, QSOL-INT composition authority, NEXUS governance, ORACLE history, ARK recovery authority, hidden chain-of-thought, or a model mind.

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

The first three remain the Three-Pillar foundation. ORACLE and NEXUS provide the witness/reasoning membrane. CONTROL is the operator surface. Files, Collections, replay records, model-state records, lattice addresses, indexes, DNA projections, recovery packages, and compatibility receipts are storage/reproducibility/conformance mechanisms, not new truth authorities.

## Phase 5 Human WebUI

Phase 5 implements `qsol-control-webui/1` as a standard-library Python loopback service plus a framework-free browser client.

```text
browser
  -> CONTROL WebUI
      -> CONTROL File / Collection / interaction storage
      -> read-only ORACLE adapter
      -> governance-preserving NEXUS Council adapter
      -> Phase 4 model-state registry
      -> Phase 7 replay runtime
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

Remote multi-user deployment remains deferred.

### WebUI views

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
REPLAY / COMPARE / LONGITUDINAL
COLLECTIONS
HEALTH
```

The composer has exactly two question modes:

```text
Evidence only
Ask Council
```

Browser attachments become ordinary content-addressed CONTROL Files. A selected Collection is bound to its exact immutable snapshot when the run is created. If the Collection later advances, the historical run still renders the snapshot it actually used.

### Browser security baseline

The local server enforces:

- loopback binds only: `127.0.0.1`, `::1`, or `localhost`;
- an unpredictable per-process WebUI session token;
- token authentication on API requests after session bootstrap;
- no CORS;
- non-loopback `Host` rejection;
- same-origin checks for state-changing browser requests when `Origin` is supplied;
- Content Security Policy with `frame-ancestors 'none'`, `object-src 'none'`, and `base-uri 'none'`;
- `X-Content-Type-Options: nosniff`;
- `Referrer-Policy: no-referrer`;
- `Cross-Origin-Resource-Policy: same-origin`;
- `Cache-Control: no-store`;
- DOM `textContent` for retrieved/untrusted record rendering rather than `innerHTML`.

Phase 7 replay execution is a state-changing WebUI request and therefore inherits the same token and same-origin boundary.

### UI invariant

CONTROL never manufactures a synthetic truth percentage from votes, confidence, entropy, model count, consensus, retrieval similarity, codon frequency, lattice position, replay differences, or compatibility batteries.

```text
CONTROL_DISPLAY != AUTHORITY
CONTROL_OPERATION != TRUTH
VOTE != EVIDENCE
CONSENSUS != TRUTH
SEARCH_SCORE != TRUTH
REPLAY_CLASSIFICATION != TRUTH
BATTERY_PASS != TRUTH
```

## Phase 6 AI / Agent API

Phase 6 implements `qsol-control-agent-api/1` as a dependency-free structured machine interface over the same runtime used by the Human WebUI.

The first transport is local JSONL over stdin/stdout:

```bash
python3 tools/agent_api.py --root .qsol-control-store
```

The current operation surface is:

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
control.replay.classify
control.replay.execute
control.replay.get
control.research.timeline
control.evidence.get
control.council.get
control.models.get
control.memory.get
control.memory.trace
```

Replay execution is a normal quota-governed mutation. It receives no machine-only epistemic privilege.

```text
HUMAN_CALLER_AUTHORITY == AI_CALLER_AUTHORITY
API_ACCESS != EPISTEMIC_PRIVILEGE
CONTROL_CALL != ORACLE_AUTHORITY
CONTROL_CALL != NEXUS_GOVERNANCE
```

See [`docs/AI-API.md`](docs/AI-API.md), [`docs/AGENT-API.md`](docs/AGENT-API.md), and [`ai/agent-api-contract.json`](ai/agent-api-contract.json).

## Phase 7 Replay and longitudinal research

Phase 7 implements `qsol-control-replay/1`.

Replay is **classified before execution**. CONTROL does not equate “same question” or “same model name” with an exact replay.

```text
ORIGINAL RUN
   |
   v
CLASSIFY REPLAY CONDITIONS
   |
   +--> unavailable / inspection only
   |
   v
NEW REPLAY RUN
   |
   +--> original exact Collection snapshot
   +--> current ORACLE evidence
   +--> current configured Council/runtime
   |
   v
CONTENT-ADDRESSED COMPARISON REPORT
```

The original run and its event chain are never rewritten. Phase 7 fingerprints the original run, events, and model-state metadata before and after replay and fails if they changed.

```text
ORIGINAL_RUN != REPLAY_RUN
ORIGINAL_RESULT_IMMUTABLE = true
CURRENT_EVIDENCE != ORIGINAL_EVIDENCE
```

### Exact Collection and retrieval basis

If the original run used a Collection, replay binds to its exact historical `collection_id` + `snapshot_id`. The current Collection `HEAD` is compared separately for longitudinal drift.

```text
REPLAY_COLLECTION_SNAPSHOT = ORIGINAL_COLLECTION_SNAPSHOT
CURRENT_COLLECTION_HEAD != ORIGINAL_COLLECTION_SNAPSHOT
```

Current `control.ask` does not perform Collection search, so new replay-basis receipts explicitly record retrieval/index status as `not_used`. Pre-Phase-7 runs without recorded index provenance remain `not_recorded`.

```text
NOT_USED != NOT_RECORDED
LEGACY_MISSING_INDEX != INVENTED_INDEX
```

### Deterministic comparison reports

`qsol-control-replay-report/1` is canonical JSON and content-addressed. It keeps six lanes separate:

1. evidence-set changes;
2. Collection-membership changes;
3. retrieval/index basis;
4. Council roster and NEXUS runtime;
5. model revision/runtime/configuration;
6. request configuration.

No combined truth or quality score is derived. Replay reports are semantically revalidated on read, including lane-level authority boundaries such as `CONSENSUS != TRUTH` and `MODEL_STATE != MODEL_MIND`.

A changed Council roster requires explicit authorization before replay execution. The report then records that changed configuration rather than hiding it.

### Recurring-question research timeline

`qsol-control-research-timeline/1` groups exact recurring questions by `question_sha256` and reports chronological runs plus transitions in evidence, Collection snapshot, Council roster, model state, and runtime.

```text
TIMELINE != TRUTH
CHANGE != IMPROVEMENT
CONSENSUS_CHANGE != EVIDENCE_CHANGE
```

See [`docs/REPLAY.md`](docs/REPLAY.md) and [`ai/replay-contract.json`](ai/replay-contract.json).

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

```text
MODEL_STATE != MODEL_MIND
VISIBLE_OUTPUT != HIDDEN_CHAIN_OF_THOUGHT
RUNTIME_METADATA != CONSCIOUSNESS
PROVIDER_REPORTED != LOCALLY_VERIFIED
HASH_IDENTITY != ARTIFACT_BYTES
MODEL_STATE_COMPARISON != MIND_COMPARISON
```

See [`docs/MODEL-STATE.md`](docs/MODEL-STATE.md).

## Files, Collections, and retrieval

```text
FILE
= immutable raw content object + immutable metadata record

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

CONTROL has no ORACLE write operation. Replay queries current evidence through this same read-only path.

```text
ORACLE_REFERENCE != CONTROL_AUTHORITY
ORACLE_RECEIPT_COPY != ORACLE_LEDGER_APPEND
FRESH != TRUE
STALE != FALSE
SUGGESTED_SEARCH != EVIDENCE
CURRENT_EVIDENCE != ORIGINAL_EVIDENCE
```

See [`docs/ORACLE-ADAPTER.md`](docs/ORACLE-ADAPTER.md).

## NEXUS governance boundary

CONTROL implements `qsol-control-nexus-adapter/1` over NEXUS local JSONL/stdio.

Replay Council execution uses the same reviewed `council.run` path. CONTROL still does not expose direct `world.create`, generic NEXUS operation passthrough, Stenographer reads, vote-weight override, ballot override, roster-authority override, or consensus-threshold override.

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

CONTROL defines a 3 × 3 × 3 logical interaction-memory lattice:

```text
X = information role   question | response | evidence
Y = epistemic role     observed | derived | unresolved
Z = temporal role      current | historical | recovery
```

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

```text
RAW_BYTES = CANONICAL
DNA_PROJECTION = DERIVED
DNA_ENCODING != BIOLOGICAL_CLAIM
PHI_TRAVERSAL != PHYSICAL_TRUTH
CODON_FREQUENCY != EVIDENCE
```

## Phase 8 ARK repository recovery

Phase 1B's `qsol-control-ark-minimum-bundle/1` remains the narrow deterministic offline reconstruction format for one run. Phase 8 adds `qsol-control-ark-repository-recovery/1` for the broader CONTROL repository state.

```text
CONTROL-recovery-package/
├── CONTROL-REPOSITORY-RECOVERY.json
├── RECOVERY-MAP.txt
└── capsules/
    ├── 000000.dat
    └── ...
```

The package preserves canonical raw objects, File records, Collection descriptors/snapshot lineage/current HEADs, runs/events/heads, model states, and replay records/reports. Public schemas and the supported lattice descriptor travel as recovery support contracts.

Raw objects are hashed and streamed into bounded `QSOL-RESTORE-DAT/1` transport chunks without changing their canonical SHA-256 identity. Search-index descriptors and DNA/lattice projections are optional derived aids and never enter the canonical source fingerprint.

```bash
python3 tools/repository_recovery.py export \
  --root .qsol-control-store \
  --output control-recovery

python3 tools/repository_recovery.py verify control-recovery

python3 tools/repository_recovery.py restore control-recovery \
  --target restored-control
```

Verification and restore fail closed on nonexistent source roots, malformed or orphaned canonical records, authority-escalating replay reports, unsupported schema/lattice contracts, unbounded capsule metadata, capsule tampering, and privacy downgrades. The strictest privacy class is recomputed from reconstructed canonical state rather than trusted from the bootstrap.

```text
RECOVERY_PACKAGE != SEMANTIC_AUTHORITY
RAW_OBJECT_BYTES = CANONICAL
SEARCH_INDEX_DESCRIPTOR != CANONICAL_MEMORY
DNA_PROJECTION != CANONICAL_SOURCE
HASH_INTEGRITY != EVIDENCE_AUTHORITY
RESTORED_CONTEXT != ORIGINAL_ASSISTANT_INSTANCE
```

See [`docs/ARK-REPOSITORY-RECOVERY.md`](docs/ARK-REPOSITORY-RECOVERY.md) and [`ai/ark-repository-recovery-contract.json`](ai/ark-repository-recovery-contract.json).

## Phase 9 INT composition batteries

Phase 9 implements `qsol-control-int-composition-report/1` as an offline, deterministic conformance layer over exact pinned parent evidence.

```bash
python3 tools/int_composition.py validate
python3 tools/int_composition.py run --json
```

The battery contains eleven cases. Three produce exact-pinned compatibility receipts for CONTROL↔ORACLE, CONTROL↔NEXUS, and CONTROL↔THOTH portable CONCAP. The remaining cases test authority non-escalation, stale-parent handling, vote/evidence separation, memory/canonical separation, model-state/identity separation, Collection/index authority separation, DNA/raw-byte canonical separation, and schema/version drift.

The methodology is pinned to QSOL-INT and preserves its governing rule:

```text
INTEGRATION_MUST_NOT_INCREASE_SEMANTIC_AUTHORITY
```

CONTROL executes the batteries but does not acquire QSOL-INT composition authority. The default report says `current_parent_compatibility = not_claimed`; pinned compatibility is never silently widened into a live-parent claim.

An optional observed-parent identity file can be checked with:

```bash
python3 tools/int_composition.py check-drift \
  --observed-parents observed.json \
  --json
```

Exact commit/blob identity yields `NO_DRIFT`. Missing parents remain `SOURCE_UNAVAILABLE`/unknown. Changed content or schema requires review. Protocol-major drift is incompatible. Pins are never silently rewritten.

```text
COMPATIBLE != TRUE
BATTERY_PASS != TRUTH
COMPATIBILITY_RECEIPT != PARENT_AUTHORITY
PINNED_PARENT_COMPATIBILITY != CURRENT_PARENT_COMPATIBILITY
DRIFT_IS_NEVER_SILENTLY_ACCEPTED
UNAVAILABLE != CONTRADICTED
```

See [`docs/INT-COMPOSITION.md`](docs/INT-COMPOSITION.md) and [`ai/int-composition-contract.json`](ai/int-composition-contract.json).

## Validation

Validation is dependency-free and requires Python 3.11 or newer. CI uses Python 3.12.

```bash
python3 tools/validate_control.py
python3 tools/validate_restore_contracts.py
python3 tools/agent_api.py --help
python3 tools/repository_recovery.py --help
python3 tools/int_composition.py validate
python3 -W default -m unittest discover -s tests -v
```

Repository contract version is `2.5.0`. Public JSON Schemas use Draft 2020-12.

## Documentation map

- [`README4AI.md`](README4AI.md): compact machine bootstrap.
- [`AGENTS.md`](AGENTS.md): contributor/agent rules.
- [`ARCHITECTURE.md`](ARCHITECTURE.md): system design and authority boundaries.
- [`ROADMAP.md`](ROADMAP.md): phase sequence and completion state.
- [`SECURITY.md`](SECURITY.md): repository security boundaries.
- [`docs/WEBUI.md`](docs/WEBUI.md): local Human WebUI.
- [`docs/AGENT-API.md`](docs/AGENT-API.md): structured machine API.
- [`docs/REPLAY.md`](docs/REPLAY.md): Phase 7 classified replay and longitudinal research.
- [`ai/replay-contract.json`](ai/replay-contract.json): machine-readable Phase 7 boundary.
- [`docs/INT-COMPOSITION.md`](docs/INT-COMPOSITION.md): Phase 9 composition receipts and drift batteries.
- [`ai/int-composition-contract.json`](ai/int-composition-contract.json): machine-readable Phase 9 boundary.
- [`docs/MODEL-STATE.md`](docs/MODEL-STATE.md): model-state registry and provenance.
- [`docs/PERSISTENT-STORAGE.md`](docs/PERSISTENT-STORAGE.md): Files, Collections, snapshots, and search.
- [`docs/ORACLE-ADAPTER.md`](docs/ORACLE-ADAPTER.md): read-only ORACLE adapter.
- [`docs/NEXUS-ADAPTER.md`](docs/NEXUS-ADAPTER.md): verified NEXUS Council adapter.
- [`docs/ARK-MINIMUM-BUNDLE.md`](docs/ARK-MINIMUM-BUNDLE.md): one-run offline recovery.
- [`docs/ARK-REPOSITORY-RECOVERY.md`](docs/ARK-REPOSITORY-RECOVERY.md): repository-level Phase 8 recovery.
- [`ai/ark-repository-recovery-contract.json`](ai/ark-repository-recovery-contract.json): machine-readable Phase 8 recovery boundary.
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
- PR #10: Phase 6 structured AI / agent API, merged.
- PR #11: Phase 7 replay and longitudinal research, merged.
- PR #12: Phase 8 repository-level ARK recovery bridge, merged.
- PR #13: Phase 9 INT composition batteries, current implementation branch.

With Phase 9 complete on this branch, the only unfinished numbered roadmap phase is the partly completed **Phase 10 hardening and release discipline**.

---

**QSOL-CONTROL controls the machinery, not reality. If eleven composition batteries go green, CONTROL records compatibility. It does not promote itself to Minister for Truth.**
