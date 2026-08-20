# QSOL-CONTROL Roadmap

## Phase 0 — Architecture and contracts

- [x] Define CONTROL as the human + AI operator plane.
- [x] Preserve Three-Pillar / ORACLE / NEXUS authority boundaries.
- [x] Define human WebUI and machine API surfaces.
- [x] Define 3×3×3 Sierpinski-derived lattice memory semantics.
- [x] Define AI model-state preservation boundary.
- [x] Add human and machine bootstrap documentation.
- [x] Add initial schemas and constitutional contracts.
- [x] Add dependency-free repository validator and CI contract checks.

## Phase 1A — Persistent Files and Collections

- [x] Implement content-addressed raw File objects.
- [x] Separate raw object identity from immutable File metadata identity.
- [x] Implement persistent named Collections.
- [x] Implement immutable Collection membership snapshots with atomic `HEAD` updates.
- [x] Keep Collection membership lexicographically ordered by `file_id`.
- [x] Implement deterministic lexical retrieval baseline.
- [x] Implement externally supplied semantic-vector index registration and cosine retrieval.
- [x] Bind every search index to an exact Collection snapshot.
- [x] Fail closed on stale semantic indexes after membership changes.
- [x] Mark search indexes derived, rebuildable, and authority-free.
- [x] Implement canonical storage fingerprint and integrity verification.
- [x] Add adversarial tests for mutation/corruption, duplicate identities, stale indexes, and snapshot lineage.
- [x] Add storage operator CLI.
- [x] Define schemas and canonical fixtures for Files, Collections, snapshots, and indexes.

### DNA/lattice recovery projection

- [x] Implement reversible `A/C/G/T` 2-bit encoding (`qsol.dna-2bit-codon64/1`).
- [x] Group three bases into one 0–63 codon slot.
- [x] Map codons over the 27-cell 3×3×3 lattice.
- [x] Implement canonical lexicographic 27-cell traversal.
- [x] Implement optional deterministic φ-gated single path (`qsol.phi-stride-27/1`, stride 17).
- [x] Preserve original byte length/hash and verify exact round-trip decode.
- [x] Make the DNA/lattice form explicitly derived and rebuildable.
- [x] Refuse biological, physical, compression, or truth-authority claims from the encoding.
- [x] Add CLI export/decode operations and regression tests.

### Portable CONCAP delivery

- [x] Reuse `QSOL-RESTORE-DAT/1` as the immutable portable object container.
- [x] Define `qsol-control-concap-export-spec/1` with explicit role-to-pack bindings.
- [x] Strip private `source_ref` metadata while preserving approved payload bytes exactly.
- [x] Content-address portable objects as `sha256(exact object bytes)`.
- [x] Deduplicate one object satisfying multiple semantic roles.
- [x] Emit transport-neutral `BOOTSTRAP.json`, `OBJECTS.json`, and content-derived object paths.
- [x] Add deterministic ZIP packaging with stable member ordering, timestamps and permissions.
- [x] Require explicit acknowledgement for RESTRICTED exports in both runtime and JSON Schema.
- [x] Create RESTRICTED bundle directories/files/ZIPs private-by-default (`0700`/`0600`).
- [x] Bound imported bootstrap/index bytes plus object/role counts before verifier iteration.
- [x] Reject ZIP outputs placed inside the verified bundle tree.
- [x] Register the runtime, CLI, schema, docs and machine contract in `manifest.json` and `README4AI.md`.
- [x] Preserve `ROUTING != RESOLUTION != TRANSPORT != AUTHORITY` across the THOTH handoff.

### Phase 1A gate

The persistent document layer must round-trip canonical fixtures offline, detect corruption, preserve immutable Collection history, and never depend on one embedding vendor. Raw bytes remain canonical; lexical/vector/DNA representations are projections. Portable CONCAP bundles are transport artifacts, not new semantic authority.

## Phase 1B — Interaction and lattice persistence

- [x] Implement canonical JSON interaction records in the runtime store.
- [x] Implement content-addressed run IDs.
- [x] Implement deterministic epistemic lattice-address assignment for questions/responses/evidence.
- [x] Link run records to File IDs and exact Collection snapshot IDs.
- [x] Implement immutable lineage between questions, evidence, responses, receipts, model states, and Files.
- [x] Implement append-only run/event persistence with atomic writes.
- [x] Add run-level storage integrity/fingerprint command.
- [x] Add adversarial tests for path traversal, duplicate identities, lineage loops, and malformed imports.
- [x] Define the minimum storage export bundle for ARK recovery.

### Phase 1B gate

**Satisfied by `qsol-control-ark-minimum-bundle/1`.** A run, its append-only event lineage, referenced File records/raw objects, exact Collection snapshot lineage, and lattice profile can now be reconstructed into a fresh CONTROL store and verified deterministically offline. The reconstructed Collection `HEAD` is the exact snapshot the run used, not a later source `HEAD`.

No live model integration is permitted merely because the storage gate is satisfied. Live adapters must independently preserve their parent authority boundaries.

## Phase 2 — ORACLE adapter

- [x] Discover ORACLE protocol/version at runtime.
- [x] Query evidence-only state: `known`, `conflict`, `unknown`.
- [x] Preserve ORACLE provenance/event references without copying authority.
- [x] Store ORACLE receipts by reference + verified payload identity.
- [x] Surface suggested searches as non-evidence.
- [x] Add ORACLE availability/freshness indicators.
- [x] Add timelock status view for QSOL-CONTEXT 2056 publication contract.

### Security gate

**Satisfied by a read-only adapter surface.** `qsol-control-oracle-adapter/1` exposes no ORACLE write operations, verifies the parent append-only ledger before evidence queries, and forbids CONTROL receipt storage from overlapping the ORACLE repository tree.

```text
CONTROL_CAN_APPEND_ORACLE_HISTORY = false
CONTROL_CAN_REWRITE_ORACLE_HISTORY = false
CONTROL_CAN_RELABEL_ORACLE_HISTORY = false
ORACLE_REFERENCE != CONTROL_AUTHORITY
```

## Phase 3 — NEXUS Council adapter

- [x] Discover NEXUS `system.health` and `system.operations` rather than hard-coding capabilities.
- [x] Implement local JSONL/stdio adapter.
- [x] Submit Council questions with admitted evidence references.
- [x] Preserve canonical roster and phase ordering returned by NEXUS.
- [x] Render sealed votes and exact consensus threshold.
- [x] Preserve minority reports.
- [x] Store NEXUS receipts and externally visible outputs.
- [x] Never capture hidden chain-of-thought.

### Governance gate

**Satisfied by `qsol-control-nexus-adapter/1`.** CONTROL discovers the live NEXUS operation surface, exposes only `council.run` as a governance-bearing mutation, then resolves and verifies the committed NEXUS session and receipts before rendering or storing results. It does not expose direct WorldStore creation, generic operation passthrough, ballot mutation, roster-authority mutation, vote-weight mutation, or consensus-threshold mutation.

```text
CONTROL_INVOKES_COUNCIL != CONTROL_OWNS_COUNCIL
CONTROL_CAN_WORLD_CREATE = false
CONTROL_CAN_OVERRIDE_VOTE_WEIGHT = false
CONTROL_CAN_OVERRIDE_BALLOTS = false
CONTROL_CAN_OVERRIDE_CONSENSUS_THRESHOLD = false
NEXUS_OWNS_WORLDSTORE_HISTORY = true
VISIBLE_NEXUS_OUTPUT != HIDDEN_CHAIN_OF_THOUGHT
```

## Phase 4 — AI model-state registry

- [x] Implement `qsol-control-model-state/1` records in persistent runtime storage.
- [x] Capture provider/runtime/model/revision metadata where available.
- [x] Capture model/weight/tokenizer hashes where locally verifiable.
- [x] Capture quantization, sampling, context and deterministic seed metadata.
- [x] Capture Council seat, mode, tool permission envelope, and system snapshot identities.
- [x] Distinguish observed, provider-reported, inferred, and unknown fields.
- [x] Add cross-run model-state comparison.
- [x] Add future-AI archaeology export.

### Epistemic gate

**Satisfied at the storage, schema, export, documentation, and WebUI layers.** `qsol-control-model-state/1` records are immutable reproducibility metadata with explicit per-field provenance. The runtime and schemas require `MODEL_STATE != MODEL_MIND`, `hidden_chain_of_thought_captured = false`, and `model_mind_captured = false`. Archaeology exports preserve the same boundary, contain no model artifact bytes or local artifact paths, and require explicit acknowledgement for RESTRICTED material.

Phase 5 consumes the pinned labels directly in the implemented model-state inspector:

```text
MODEL_STATE != MODEL_MIND
VISIBLE_OUTPUT != HIDDEN_CHAIN_OF_THOUGHT
RUNTIME_METADATA != CONSCIOUSNESS
PROVIDER_REPORTED != LOCALLY_VERIFIED
MODEL_STATE_COMPARISON != MIND_COMPARISON
```

## Phase 5 — Human WebUI

- [x] Build question composer with explicit `Evidence only` / `Ask Council` modes.
- [x] Build File attachment flow for immediate context.
- [x] Build persistent Collection create/browse/search interface.
- [x] Show exact Collection snapshot used by a run.
- [x] Build evidence panel.
- [x] Build Council phase + sealed-vote panel.
- [x] Build minority-report panel.
- [x] Build sources/provenance panel.
- [x] Build ORACLE timeline/receipt view.
- [x] Build model-state inspector.
- [x] Build lattice-memory browser.
- [x] Build DNA/lattice recovery projection inspector/export control.
- [x] Build replay/compare view.
- [x] Build health/status page for connected QSOL services.
- [x] Add accessible keyboard-first interface and mobile fallback.

### UI invariant

Never display a synthetic `truth percentage` derived from votes, confidence, entropy, model count, consensus, retrieval score, embedding similarity, codon frequency, or lattice position.

**Satisfied by `qsol-control-webui/1`.** The implemented local WebUI is loopback-only, requires a same-origin session token for API access, reuses the existing CONTROL/ORACLE/NEXUS runtimes, and keeps every displayed quantity in its original semantic lane. It does not expose generic parent mutation operations or invent a new authority-bearing API.

The model-state inspector preserves the Phase 4 label contract exactly: reproducibility metadata is not a model mind, provider-reported metadata is not locally verified metadata, inferred values remain visibly inferred, and unknown stays unknown.

```text
CONTROL_DISPLAY != AUTHORITY
VOTE != EVIDENCE
CONSENSUS != TRUTH
SEARCH_SCORE != TRUTH
SEMANTIC_SIMILARITY != EVIDENCE_STRENGTH
MODEL_STATE != MODEL_MIND
PROVIDER_REPORTED != LOCALLY_VERIFIED
LATTICE_ADDRESS != TRUTH
CODON_FREQUENCY != EVIDENCE
```

Phase 5's replay/compare surface compares immutable stored runs only. Actual replay execution remains Phase 7.

## Phase 6 — AI / agent API

- [x] Implement structured request/response API.
- [x] Implement `control.health` and capability discovery.
- [x] Implement `control.ask`.
- [x] Implement File upload/reference operations.
- [x] Implement Collection create/snapshot/search operations.
- [x] Implement run retrieval/comparison.
- [x] Implement evidence/Council/model-state retrieval.
- [x] Implement bounded lattice traversal.
- [x] Add caller quotas and resource limits.
- [x] Add machine-readable error taxonomy.
- [x] Keep AI caller epistemic privilege equal to human caller privilege.

### Phase 6 gate

**Satisfied by `qsol-control-agent-api/1`.** The first machine transport is bounded dependency-free JSONL/stdio over a transport-neutral dispatcher. It reuses the Phase 5 CONTROL runtime, read-only ORACLE adapter, governed NEXUS Council adapter, model-state registry, Files/Collections, run storage, and lattice memory rather than creating a parallel authority path.

External `human` and `ai` caller kinds receive the same orchestration-only epistemic privilege. AI-originated runs are recorded as `requester_kind: ai`, but that label does not upgrade evidence, Council authority, storage authority, or truth status.

```text
HUMAN_CALLER_AUTHORITY == AI_CALLER_AUTHORITY
API_ACCESS != EPISTEMIC_PRIVILEGE
CONTROL_CALL != ORACLE_AUTHORITY
CONTROL_CALL != NEXUS_GOVERNANCE
```

The Phase 6 transport does not implement remote multi-user deployment. Replay execution is added only by the separately versioned Phase 7 contract.

## Phase 7 — Replay and longitudinal research

- [x] Implement replay classification.
- [x] Bind replay to exact Collection snapshot and index descriptor used originally.
- [x] Compare original run with current evidence.
- [x] Explain changes in evidence set, Collection membership, Council roster, model revision, runtime, and configuration.
- [x] Preserve original result immutably.
- [x] Produce deterministic comparison reports.
- [x] Add research timeline view for recurring questions.

### Phase 7 gate

**Satisfied by `qsol-control-replay/1`.** Replay is classified before execution, creates a new immutable run, and fingerprints the original run/event/model-state set before and after execution. A replay never rewrites the original result.

If a run used a Collection, execution is bound to the original exact Collection snapshot while current `HEAD` is compared separately. Current `control.ask` does not execute Collection search, so new Phase 7 replay-basis receipts explicitly record the retrieval/index descriptor as `not_used`; pre-Phase-7 runs with no recorded index-use metadata remain `not_recorded`. Missing historical metadata is never reconstructed by assumption.

The deterministic report keeps evidence, Collection membership, retrieval/index basis, Council roster/runtime, model-state/runtime metadata, and request configuration in separate lanes. Current ORACLE evidence is compared with the original evidence set but is never relabelled as the original observation.

```text
ORIGINAL_RUN != REPLAY_RUN
ORIGINAL_RESULT_IMMUTABLE = true
CURRENT_EVIDENCE != ORIGINAL_EVIDENCE
CURRENT_COLLECTION_HEAD != ORIGINAL_COLLECTION_SNAPSHOT
LEGACY_MISSING_INDEX != INVENTED_INDEX
REPLAY_CLASSIFICATION != TRUTH
MODEL_STATE_COMPARISON != MIND_COMPARISON
```

Recurring-question timelines group exact question identities by `question_sha256` and report longitudinal changes without assigning truth meaning to change.

## Phase 8 — ARK recovery bridge

- [x] Define a reversible DNA/lattice projection for individual File bytes.
- [x] Define deterministic portable CONCAP bundle machinery over `QSOL-RESTORE-DAT/1`.
- [x] Define minimum recoverable CONTROL bundle.
- [x] Export raw objects, File records, Collection descriptors/snapshots, schemas, run records, model states, and lattice addressing rules as a broader repository-level recovery package.
- [x] Include optional DNA/lattice projections and search-index descriptors without requiring them as canonical source.
- [x] Add plain-text recovery map.
- [x] Add standard-library validator/reconstructor for the broader recovery package.
- [x] Test reconstruction of the broader package without CONTROL WebUI or original search engine.
- [x] Add constrained-environment recovery fixtures.

### Phase 8 gate

**Satisfied by `qsol-control-ark-repository-recovery/1`.** The broader recovery package preserves canonical raw objects, File records, Collection descriptors plus full snapshot/HEAD lineage, interaction runs/events/heads, model states, and Phase 7 replay records/reports. Public JSON schemas and the supported lattice profile travel as recovery support contracts. The package is split deterministically across bounded `QSOL-RESTORE-DAT/1` capsules, and raw objects are streamed into transport chunks while retaining their original SHA-256 identity.

Search-index descriptors and DNA/lattice projections are optional derived aids and are excluded from the canonical source fingerprint. Reconstruction requires neither the CONTROL WebUI nor the original search engine. A plain-text `RECOVERY-MAP.txt`, a standard-library verifier/reconstructor, and a constrained recovery fixture make the recovery order inspectable outside the original application stack.

Import and restore fail closed: the source root must already exist, every canonical registry entry must be semantically valid and reachable, orphan replay reports/events/snapshots/heads are rejected, schemas and lattice support contracts are revalidated, untrusted bootstrap/map/capsule sizes are bounded before read, and the strictest privacy class is recomputed from restored canonical state rather than trusted from package metadata.

```text
RECOVERY_PACKAGE != SEMANTIC_AUTHORITY
RAW_OBJECT_BYTES = CANONICAL
SEARCH_INDEX_DESCRIPTOR != CANONICAL_MEMORY
DNA_PROJECTION != CANONICAL_SOURCE
LATTICE_ADDRESS != TRUTH
HASH_INTEGRITY != EVIDENCE_AUTHORITY
RESTORED_CONTEXT != ORIGINAL_ASSISTANT_INSTANCE
```

## Phase 9 — INT composition batteries

- [x] Add cross-repo compatibility receipts for CONTROL↔ORACLE and CONTROL↔NEXUS.
- [x] Add CONTROL↔THOTH portable CONCAP compatibility receipts.
- [x] Test authority non-escalation.
- [x] Test stale-parent handling.
- [x] Test vote/evidence separation.
- [x] Test memory/canonical separation.
- [x] Test model-state/identity separation.
- [x] Test Collection/search-index authority separation.
- [x] Test DNA/lattice projection/raw-byte canonical separation.
- [x] Test schema/version drift.

### Phase 9 gate

**Satisfied by `qsol-control-int-composition-report/1`.** CONTROL runs eleven deterministic, standard-library conformance cases using exact parent and local-contract pins. The three cross-repository receipts cover CONTROL↔ORACLE, CONTROL↔NEXUS, and CONTROL↔THOTH portable CONCAP compatibility for the exact pinned commits/artifacts only. QSOL-INT's pinned compatibility report supplies the composition methodology and the governing rule `INTEGRATION_MUST_NOT_INCREASE_SEMANTIC_AUTHORITY`; CONTROL does not inherit or claim QSOL-INT composition authority.

The default report scope is `pinned_parent_evidence_only`. Without a separately supplied current-parent observation, `current_parent_compatibility` remains `not_claimed`. If current identities are supplied, exact commit/blob equality yields `NO_DRIFT`; missing parents become `SOURCE_UNAVAILABLE`; changed content becomes `CONTENT_DRIFT`; schema-major drift remains untested pending review; and protocol-major drift is incompatible. Pins are never silently refreshed to make a battery green.

The separation batteries independently preserve vote/evidence, lattice-memory/content identity, model-state/model-mind, Collection/index, and DNA/raw-byte boundaries. Passing a compatibility battery is conformance evidence, not truth, endorsement, or inherited authority.

```text
INTEGRATION_MUST_NOT_INCREASE_SEMANTIC_AUTHORITY
COMPATIBLE != TRUE
BATTERY_PASS != TRUTH
COMPATIBILITY_RECEIPT != PARENT_AUTHORITY
PINNED_PARENT_COMPATIBILITY != CURRENT_PARENT_COMPATIBILITY
DRIFT_IS_NEVER_SILENTLY_ACCEPTED
UNAVAILABLE != CONTRADICTED
VOTE != EVIDENCE
INDEX != CANONICAL_MEMORY
MODEL_STATE != MODEL_MIND
RAW_OBJECT_BYTES = CANONICAL
```

## Phase 10 — Hardening and release discipline

- [x] Threat-model network and browser boundaries.
- [x] Expand secret-scrubbing tests for File metadata/imports.
- [x] Add same-origin session-token / no-CORS baseline for the local WebUI.
- [x] Strict local-bind default for operator service.
- [x] Add portable CONCAP metadata/count limits and hostile-input guards.
- [x] Import/export decompression-bomb defenses where compressed untrusted inputs are accepted.
- [x] Fuzz/adversarial storage tests.
- [x] Reproducible release bundle.
- [x] Versioned migration policy.
- [x] Release checklist and changelog discipline.

### Phase 10 gate

**Satisfied by `qsol-control-phase10-hardening/1`.** The actual network/browser surface is threat-modelled as a loopback-only operator service plus local JSONL/stdio machine API; CONTROL does not claim remote multi-user authentication, authorization, TLS termination, browser-extension isolation, or host-malware resistance. Existing same-origin/session-token/no-CORS and strict local-bind protections remain the concrete WebUI baseline.

File/Collection metadata now has a deterministic read/import-side secret audit in addition to existing write-time marker rejection. The audit rejects credential-labelled keys, high-confidence token markers, credential-bearing locators, duplicate JSON members, malformed identities, and rehashed hostile records without silently redacting canonical history.

Compressed untrusted archive input is default-deny. The Phase 10 release verifier accepts bounded `ZIP_STORED` members only, rejects traversal/symlinks/duplicates/unexpected members, and performs no decompression or extraction. A future compressed import path would require its own separately reviewed bounded decoder rather than silently widening this contract.

The deterministic adversarial storage battery is a CI gate. `qsol-control-migration/1` is forward-only, source-preserving, fail-closed on downgrades/unknown majors, and emits content-addressed procedure receipts without in-place canonical rewrites. `qsol-control-release-bundle/1` produces byte-reproducible fixed-metadata source ZIPs whose `RELEASE.json` binds the declared release version/source commit, exact per-file hashes, and deterministic source-tree SHA-256. Release checklist/changelog discipline preserves implementation/merge/release state distinctions.

```text
LOOPBACK != REMOTE_AUTH
SESSION_TOKEN != EPISTEMIC_PRIVILEGE
COMPRESSED_UNTRUSTED_INPUT != ACCEPTED_BY_DEFAULT
MIGRATION != REINTERPRETATION
RELEASE_HASH != SEMANTIC_TRUTH
MERGED_MAIN != PUBLISHED_RELEASE
GREEN_CI != RELEASED
```

The numbered QSOL-CONTROL roadmap is complete through Phase 10. Post-roadmap extensions are separately versioned so the completed `2.6.0` core does not silently acquire new transport or deployment semantics.

## Post-roadmap deferred resolution — PR #15

- [x] Remote multi-user deployment: resolved by the optional authenticated remote Agent API gateway (`qsol-control-remote-gateway/1`). The local WebUI remains local-only.
- [x] Mobile native applications: resolved by thin native iOS/SwiftUI and Android/Kotlin reference clients speaking `qsol-control-remote-request/1` over HTTPS. Signed store releases are not claimed.
- [x] Distributed consensus for CONTROL storage: resolved by an external consensus coordination adapter (`qsol-control-consensus-adapter/1`). CONTROL does not embed a consensus algorithm or let a quorum receipt directly mutate core storage.
- [x] Automatic truth scoring: resolved as a permanent forbidden non-goal.
- [x] Hidden chain-of-thought capture: resolved as a permanent forbidden non-goal.
- [x] Literal geometric-cognition claims from the lattice: resolved as a permanent forbidden non-goal.
- [x] Biological claims from the DNA-symbol codec: resolved as a permanent forbidden non-goal.
- [x] Claims that φ traversal is physically optimal storage: resolved as a permanent forbidden non-goal.

### Post-roadmap extension gate

Machine entrypoint: `extensions/manifest.json` (`qsol-control-post-roadmap-extensions/1`), explicitly bound to core contract `2.6.0`.

The remote gateway reuses the reviewed Agent API dispatcher, maps digest-authenticated principals to fixed caller identities, enforces per-principal operation allowlists and Host allowlisting, and requires explicit TLS-enabled configuration for non-loopback binds. Remote access does not expose the local WebUI and does not add epistemic privilege.

The native clients remain presentation/transport shells. The external consensus adapter content-addresses exact mutation intents and validates quorum receipts, but quorum formation, cryptographic membership, liveness and fault tolerance remain responsibilities of the external consensus provider.

The five epistemic/ontological items are not features with a future implementation date. They are pinned by `ai/permanent-nongoals.json` as permanent prohibitions.

```text
CORE_2_6_0 != EXTENSION_SURFACE
REMOTE_ACCESS != EPISTEMIC_PRIVILEGE
AUTHENTICATED != AUTHORITATIVE
MOBILE_CLIENT != CONTROL_AUTHORITY
CONSENSUS_RECEIPT != SEMANTIC_AUTHORITY
QUORUM != TRUTH
AUTOMATIC_TRUTH_SCORING = FORBIDDEN
HIDDEN_CHAIN_OF_THOUGHT_CAPTURE = FORBIDDEN
LATTICE_GEOMETRY != COGNITION_CLAIM
DNA_CODEC != BIOLOGICAL_CLAIM
PHI_TRAVERSAL != PHYSICAL_OPTIMALITY
```

See `docs/POST-ROADMAP-EXTENSIONS.md` for deployment boundaries and exact dispositions.
