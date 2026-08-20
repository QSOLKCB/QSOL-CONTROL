# QSOL-CONTROL

**A human + AI control plane for the QSOL ecosystem, orchestrating ORACLE evidence, NEXUS Council reasoning, persistent Files and Collections, model-state reproducibility metadata, classified replay, lattice memory, deterministic recovery, INT-style composition conformance, and release/recovery hardening.**

> **CONTROL controls the machinery, not reality.**
>
> A green button does not make a claim true. Six models agreeing does not make it true. A retrieval score of `0.97` does not make it true either. We remain committed to disappointing the dashboard industry.

QSOL-CONTROL has two completed core operator surfaces over the same runtime plus a separately versioned optional extension surface:

- **Human control plane:** Phase 5 local loopback WebUI, extended with Phase 7 replay/longitudinal views.
- **AI control plane:** Phase 6 structured JSONL/stdio agent API, extended with Phase 7 replay operations.
- **Optional post-roadmap extension:** authenticated remote Agent API gateway, thin native reference clients, and external consensus coordination. The local WebUI is **not** exposed remotely.

CONTROL owns orchestration, its own storage mechanics, recovery/release bundle construction, migration-plan mechanics, and execution of local conformance/hardening batteries. It does **not** own scientific truth, public epistemic authority, QSOL-INT composition authority, NEXUS governance, ORACLE history, ARK recovery authority, publication authority, hidden chain-of-thought, or a model mind.

```text
CORE_LOCAL_OPERATOR_SURFACES != OPTIONAL_EXTENSION_SURFACE
REMOTE_GATEWAY != REMOTE_WEBUI
REMOTE_ACCESS != EPISTEMIC_PRIVILEGE
```

The machine entrypoint for the completed core remains [`manifest.json`](manifest.json). Optional post-roadmap surfaces are registered in [`extensions/manifest.json`](extensions/manifest.json) and [`extensions/README4AI.md`](extensions/README4AI.md).

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

Files, Collections, replay records, model-state records, lattice addresses, indexes, DNA projections, recovery packages, compatibility receipts, migration receipts, and release manifests are storage/reproducibility/conformance mechanisms, not new truth authorities.

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

The **core WebUI remains loopback-only**. PR #15 does not make the WebUI remote. It adds a separately versioned authenticated remote **Agent API gateway** under the post-roadmap extension contract.

### Browser security baseline

The local server enforces loopback-only binds, an unpredictable per-process session token, token authentication after bootstrap, no CORS, non-loopback `Host` rejection, same-origin mutation checks, strict security headers, no-store responses, and text-only DOM rendering for retrieved/untrusted values.

```text
LOOPBACK != REMOTE_AUTH
SESSION_TOKEN != MULTI_USER_AUTHORIZATION
CONTROL_DISPLAY != AUTHORITY
VOTE != EVIDENCE
CONSENSUS != TRUTH
SEARCH_SCORE != TRUTH
```

See [`docs/WEBUI.md`](docs/WEBUI.md) and the Phase 10 [`docs/THREAT-MODEL.md`](docs/THREAT-MODEL.md).

## Phase 6 AI / Agent API

Phase 6 implements `qsol-control-agent-api/1` as dependency-free JSONL over local stdin/stdout:

```bash
python3 tools/agent_api.py --root .qsol-control-store
```

The operation surface includes Files/Collections, `control.ask`, run/evidence/Council/model views, bounded lattice traversal, Phase 7 replay operations, and longitudinal timeline retrieval. Human and AI callers have equal epistemic privilege.

```text
HUMAN_CALLER_AUTHORITY == AI_CALLER_AUTHORITY
API_ACCESS != EPISTEMIC_PRIVILEGE
CONTROL_CALL != ORACLE_AUTHORITY
CONTROL_CALL != NEXUS_GOVERNANCE
```

See [`docs/AGENT-API.md`](docs/AGENT-API.md) and [`ai/agent-api-contract.json`](ai/agent-api-contract.json).

## Phase 7 Replay and longitudinal research

Phase 7 implements `qsol-control-replay/1`.

Replay is **classified before execution**, creates a new immutable run, and never rewrites the original result. If a run used a Collection, replay binds to its exact historical snapshot; current Collection `HEAD` and current ORACLE evidence are compared separately.

```text
ORIGINAL_RUN != REPLAY_RUN
ORIGINAL_RESULT_IMMUTABLE = true
CURRENT_EVIDENCE != ORIGINAL_EVIDENCE
CURRENT_COLLECTION_HEAD != ORIGINAL_COLLECTION_SNAPSHOT
LEGACY_MISSING_INDEX != INVENTED_INDEX
REPLAY_CLASSIFICATION != TRUTH
MODEL_STATE_COMPARISON != MIND_COMPARISON
```

Deterministic replay reports keep evidence, Collection membership, retrieval/index basis, Council runtime/roster, model-state metadata, and request configuration in separate lanes. Recurring-question timelines group exact question identities by `question_sha256` without assigning truth meaning to change.

See [`docs/REPLAY.md`](docs/REPLAY.md) and [`ai/replay-contract.json`](ai/replay-contract.json).

## Phase 4 model-state registry and inspector

CONTROL persists immutable `qsol-control-model-state/1` reproducibility records with explicit field provenance.

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

Raw bytes remain canonical. Search indexes are derived and rebuildable.

```text
SEARCH_SCORE != TRUTH
SEMANTIC_SIMILARITY != EVIDENCE_STRENGTH
INDEX != CANONICAL_MEMORY
COLLECTION_MEMBERSHIP != ENDORSEMENT
```

See [`docs/PERSISTENT-STORAGE.md`](docs/PERSISTENT-STORAGE.md).

## ORACLE boundary

CONTROL implements the read-only `qsol-control-oracle-adapter/1` against `QSOL-ORACLE/1`. It verifies the parent ledger before evidence queries, preserves provenance/event references, and never exposes ORACLE writes.

```text
ORACLE_REFERENCE != CONTROL_AUTHORITY
ORACLE_RECEIPT_COPY != ORACLE_LEDGER_APPEND
FRESH != TRUE
STALE != FALSE
SUGGESTED_SEARCH != EVIDENCE
```

See [`docs/ORACLE-ADAPTER.md`](docs/ORACLE-ADAPTER.md).

## NEXUS governance boundary

CONTROL implements `qsol-control-nexus-adapter/1` over NEXUS local JSONL/stdio and exposes only the reviewed Council path rather than generic governance mutation.

```text
CONTROL_INVOKES_COUNCIL != CONTROL_OWNS_COUNCIL
CONTROL_CAN_WORLD_CREATE = false
CONTROL_CAN_OVERRIDE_VOTE_WEIGHT = false
CONTROL_CAN_OVERRIDE_BALLOTS = false
CONTROL_CAN_OVERRIDE_CONSENSUS_THRESHOLD = false
NEXUS_OWNS_WORLDSTORE_HISTORY = true
```

See [`docs/NEXUS-ADAPTER.md`](docs/NEXUS-ADAPTER.md).

## Lattice memory and DNA projection

The 3 × 3 × 3 lattice is a deterministic logical address space. The DNA codec is a reversible derived File-byte projection.

```text
LATTICE_ADDRESS != COLLECTION_MEMBERSHIP
LATTICE_ADDRESS != TRUTH
GEOMETRY != TRUTH
RAW_BYTES = CANONICAL
DNA_PROJECTION = DERIVED
DNA_ENCODING != BIOLOGICAL_CLAIM
PHI_TRAVERSAL != PHYSICAL_TRUTH
CODON_FREQUENCY != EVIDENCE
```

See [`docs/LATTICE-MEMORY.md`](docs/LATTICE-MEMORY.md).

## Phase 8 ARK repository recovery

Phase 8 adds `qsol-control-ark-repository-recovery/1` while preserving the earlier one-run `qsol-control-ark-minimum-bundle/1`.

```text
CONTROL-recovery-package/
├── CONTROL-REPOSITORY-RECOVERY.json
├── RECOVERY-MAP.txt
└── capsules/
    ├── 000000.dat
    └── ...
```

The package preserves canonical raw objects, File records, Collection descriptors/snapshot lineage/current HEADs, runs/events/heads, model states, and replay records/reports. Raw objects are streamed into bounded `QSOL-RESTORE-DAT/1` chunks while retaining original SHA-256 identity. Search-index descriptors and DNA projections remain optional derived material.

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

Phase 9 implements `qsol-control-int-composition-report/1` as an offline deterministic conformance layer over exact pinned parent evidence.

```bash
python3 tools/int_composition.py validate
python3 tools/int_composition.py run --json
```

Eleven cases cover exact-pinned CONTROL↔ORACLE, CONTROL↔NEXUS, CONTROL↔THOTH portable-CONCAP receipts plus authority, stale-parent, vote/evidence, memory/canonical, model-state/identity, Collection/index, DNA/raw-byte, and schema/version boundaries.

```text
INTEGRATION_MUST_NOT_INCREASE_SEMANTIC_AUTHORITY
COMPATIBLE != TRUE
BATTERY_PASS != TRUTH
COMPATIBILITY_RECEIPT != PARENT_AUTHORITY
PINNED_PARENT_COMPATIBILITY != CURRENT_PARENT_COMPATIBILITY
DRIFT_IS_NEVER_SILENTLY_ACCEPTED
UNAVAILABLE != CONTRADICTED
```

See [`docs/INT-COMPOSITION.md`](docs/INT-COMPOSITION.md) and [`ai/int-composition-contract.json`](ai/int-composition-contract.json).

## Phase 10 Hardening and release discipline

Phase 10 implements `qsol-control-phase10-hardening/1` and closes the final numbered roadmap phase without widening the completed local core into a remote multi-user WebUI/service.

### Threat model and secret auditing

[`docs/THREAT-MODEL.md`](docs/THREAT-MODEL.md) documents the completed-core browser/network boundary: local loopback WebUI plus local JSONL/stdio machine API. The optional post-roadmap remote gateway has its own separately versioned contract and threat boundary.

Phase 10 adds a deterministic read/import-side File/Collection metadata audit:

```bash
python3 tools/file_metadata_audit.py --root .qsol-control-store --json
```

It rejects credential-labelled keys, high-confidence token markers, credential-bearing locators, duplicate JSON members, malformed identities, and rehashed hostile metadata without silently redacting canonical history.

### Archive safety

Compressed untrusted archive input is default-deny. `storage/archive_safety.py` accepts only bounded `ZIP_STORED` members for the Phase 10 release verifier, rejects traversal/symlinks/duplicates/oversize inputs, and performs no decompression or extraction.

```text
COMPRESSED_UNTRUSTED_INPUT != ACCEPTED_BY_DEFAULT
ARCHIVE_VERIFY != ARCHIVE_EXECUTE
```

### Deterministic adversarial battery

```bash
python3 tools/adversarial_storage.py --iterations 256
```

The battery uses a fixed seed to exercise malformed identities, path traversal, secret metadata, and object corruption as a deterministic CI gate.

### Versioned migration

`qsol-control-migration/1` provides forward-only, source-preserving migration plans and content-addressed receipts:

```bash
python3 tools/migration.py validate
python3 tools/migration.py plan --from-version 2.5.0 --to-version 2.6.0 --json
```

Downgrades, unknown majors, undeclared steps, and in-place canonical rewrites fail closed.

```text
MIGRATION != REINTERPRETATION
SOURCE_STATE != MUTATED_IN_PLACE
```

See [`docs/MIGRATIONS.md`](docs/MIGRATIONS.md) and [`ai/migration-policy.json`](ai/migration-policy.json).

### Reproducible release bundle

`qsol-control-release-bundle/1` creates fixed-metadata `ZIP_STORED` source bundles with exact per-file SHA-256, a deterministic source-tree SHA-256, a declared source commit/release version, and content-addressed `RELEASE.json`.

```bash
python3 tools/release_bundle.py check
python3 tools/release_bundle.py build \
  --release-version 1.0.0 \
  --source-commit <40-lowercase-hex-release-commit> \
  --output ../QSOL-CONTROL-1.0.0.zip
python3 tools/release_bundle.py verify ../QSOL-CONTROL-1.0.0.zip
```

The release checklist requires two independent byte-identical builds before publication.

```text
RELEASE_HASH != SEMANTIC_TRUTH
REPRODUCIBLE_BYTES != REPRODUCIBLE_LIVE_INFERENCE
MERGED_MAIN != PUBLISHED_RELEASE
GREEN_CI != RELEASED
```

See [`docs/RELEASE.md`](docs/RELEASE.md), [`ai/release-contract.json`](ai/release-contract.json), and [`RELEASE-CHECKLIST.md`](RELEASE-CHECKLIST.md).

## Post-roadmap optional extensions — PR #15

PR #15 resolves the old deferred engineering items through an **optional extension layer**, while converting the epistemic/ontological items into permanent non-goals. The extension entrypoint is `extensions/manifest.json`.

### Authenticated remote Agent API gateway

`qsol-control-remote-gateway/1` exposes only `POST /v1/agent`, never the Human WebUI. A bearer-token digest selects a fixed principal identity. Every principal has an operation allowlist, a privacy ceiling, and explicit record ACLs. Successful gateway-created resources are associated with the principal through credential-free content-addressed remote audit records.

The gateway additionally enforces:

- TLS for non-loopback binds;
- Host allowlisting and no CORS;
- 32-character minimum presented bearer token;
- private TLS key permissions on POSIX;
- record-level authorization for Files, Collections, runs, replays, and model states;
- a renewable 60-second Agent API quota window rather than process-lifetime exhaustion;
- at most 64 concurrent accepted connections and 10-second accepted-socket timeouts;
- fail-closed policy revalidation inside the public `build_server()` factory;
- durable principal/request/operation audit without bearer material.

```text
AUTHENTICATION != RECORD_AUTHORIZATION
REMOTE_GATEWAY != REMOTE_WEBUI
REMOTE_ACCESS != EPISTEMIC_PRIVILEGE
```

### Native reference clients

The iOS/SwiftUI and Android/Kotlin reference clients are thin HTTPS clients of the remote request protocol. They do not reimplement CONTROL semantics, invent truth scores, or expose hidden reasoning. App Store / Play Store packaging is not claimed.

### External consensus coordination

`qsol-control-consensus-adapter/1` content-addresses mutation intents and delegates quorum formation to an external provider. Supplied intents are fully revalidated as known CONTROL mutations before provider invocation. Provider stdout/stderr are bounded while the child is running, and returned receipts require a second provider verification call.

```text
CONSENSUS_RECEIPT != SEMANTIC_AUTHORITY
QUORUM != TRUTH
EXTERNAL_CONSENSUS != CONTROL_STORAGE_REWRITE
```

### Permanent non-goals

Automatic truth scoring, hidden chain-of-thought capture, literal lattice-cognition claims, biological claims from the DNA codec, and physical-optimality claims from φ traversal are explicitly **forbidden**, not unfinished features.

See [`EXTENSIONS.md`](EXTENSIONS.md), [`extensions/manifest.json`](extensions/manifest.json), [`extensions/README4AI.md`](extensions/README4AI.md), and [`docs/POST-ROADMAP-EXTENSIONS.md`](docs/POST-ROADMAP-EXTENSIONS.md).

## Validation

Validation is dependency-free and requires Python 3.11 or newer. CI uses Python 3.12.

```bash
python3 tools/validate_control.py
python3 tools/validate_restore_contracts.py
python3 tools/agent_api.py --help
python3 tools/repository_recovery.py --help
python3 tools/int_composition.py validate
python3 tools/migration.py validate
python3 tools/adversarial_storage.py --iterations 256
python3 tools/release_bundle.py check
python3 tools/validate_extensions.py
python3 -W default -m unittest discover -s tests -v
```

Repository contract version is `2.6.0` for the completed local core. Optional post-roadmap extensions are separately versioned by `qsol-control-post-roadmap-extensions/1`. Public JSON Schemas use Draft 2020-12.

## Documentation map

- [`README4AI.md`](README4AI.md): compact machine bootstrap for the completed core plus extension pointer.
- [`manifest.json`](manifest.json): canonical completed-core machine map.
- [`extensions/manifest.json`](extensions/manifest.json): optional post-roadmap extension machine map.
- [`extensions/README4AI.md`](extensions/README4AI.md): compact extension bootstrap.
- [`EXTENSIONS.md`](EXTENSIONS.md): extension entrypoint for humans.
- [`docs/POST-ROADMAP-EXTENSIONS.md`](docs/POST-ROADMAP-EXTENSIONS.md): remote/mobile/consensus extension boundaries.
- [`AGENTS.md`](AGENTS.md): contributor/agent rules.
- [`ARCHITECTURE.md`](ARCHITECTURE.md): system design and authority boundaries.
- [`ROADMAP.md`](ROADMAP.md): phase sequence and post-roadmap dispositions.
- [`SECURITY.md`](SECURITY.md): security boundary summary.
- [`docs/THREAT-MODEL.md`](docs/THREAT-MODEL.md): Phase 10 completed-core browser/network threat model.
- [`docs/RELEASE.md`](docs/RELEASE.md): reproducible release workflow.
- [`RELEASE-CHECKLIST.md`](RELEASE-CHECKLIST.md): release gate discipline.
- [`docs/MIGRATIONS.md`](docs/MIGRATIONS.md): versioned migration policy.
- [`docs/WEBUI.md`](docs/WEBUI.md): local Human WebUI.
- [`docs/AGENT-API.md`](docs/AGENT-API.md): structured local machine API.
- [`docs/REPLAY.md`](docs/REPLAY.md): Phase 7 classified replay and longitudinal research.
- [`docs/INT-COMPOSITION.md`](docs/INT-COMPOSITION.md): Phase 9 composition receipts and drift batteries.
- [`docs/MODEL-STATE.md`](docs/MODEL-STATE.md): model-state registry and provenance.
- [`docs/PERSISTENT-STORAGE.md`](docs/PERSISTENT-STORAGE.md): Files, Collections, snapshots, and search.
- [`docs/ORACLE-ADAPTER.md`](docs/ORACLE-ADAPTER.md): read-only ORACLE adapter.
- [`docs/NEXUS-ADAPTER.md`](docs/NEXUS-ADAPTER.md): verified NEXUS Council adapter.
- [`docs/ARK-MINIMUM-BUNDLE.md`](docs/ARK-MINIMUM-BUNDLE.md): one-run offline recovery.
- [`docs/ARK-REPOSITORY-RECOVERY.md`](docs/ARK-REPOSITORY-RECOVERY.md): repository-level Phase 8 recovery.

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
- PR #13: Phase 9 INT composition batteries, merged.
- PR #14: Phase 10 hardening and release discipline, merged.
- PR #15: post-roadmap optional extensions and permanent non-goals, current implementation branch.

The **numbered roadmap is complete through Phase 10**. The former deferred engineering items now have explicit optional-extension dispositions, while the five epistemic/ontological items are permanent non-goals. No public release is claimed merely because implementation and CI are complete.

```text
NUMBERED_ROADMAP_COMPLETE != PUBLISHED_RELEASE
OPTIONAL_EXTENSION != CORE_AUTHORITY
```

---

**QSOL-CONTROL controls the machinery, not reality. Network access, quorum, or a native app icon still do not earn a Ministry of Truth badge.**
