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

- [ ] Discover NEXUS `system.health` and `system.operations` rather than hard-coding capabilities.
- [ ] Implement local JSONL/stdio adapter.
- [ ] Submit Council questions with admitted evidence references.
- [ ] Preserve canonical roster and phase ordering returned by NEXUS.
- [ ] Render sealed votes and exact consensus threshold.
- [ ] Preserve minority reports.
- [ ] Store NEXUS receipts and externally visible outputs.
- [ ] Never capture hidden chain-of-thought.

### Governance gate

CONTROL may invoke Council operations but cannot alter NEXUS vote weights, ballot contents, roster authority, consensus threshold, or WorldStore history.

## Phase 4 — AI model-state registry

- [ ] Implement `qsol-control-model-state/1` records in persistent runtime storage.
- [ ] Capture provider/runtime/model/revision metadata where available.
- [ ] Capture model/weight/tokenizer hashes where locally verifiable.
- [ ] Capture quantization, sampling, context and deterministic seed metadata.
- [ ] Capture Council seat, mode, tool permission envelope, and system snapshot identities.
- [ ] Distinguish observed, provider-reported, inferred, and unknown fields.
- [ ] Add cross-run model-state comparison.
- [ ] Add future-AI archaeology export.

### Epistemic gate

`MODEL_STATE != MODEL_MIND` must be enforced in schemas, docs, UI labels, and exports.

## Phase 5 — Human WebUI

- [ ] Build question composer with explicit `Evidence only` / `Ask Council` modes.
- [ ] Build File attachment flow for immediate context.
- [ ] Build persistent Collection create/browse/search interface.
- [ ] Show exact Collection snapshot used by a run.
- [ ] Build evidence panel.
- [ ] Build Council phase + sealed-vote panel.
- [ ] Build minority-report panel.
- [ ] Build sources/provenance panel.
- [ ] Build ORACLE timeline/receipt view.
- [ ] Build model-state inspector.
- [ ] Build lattice-memory browser.
- [ ] Build DNA/lattice recovery projection inspector/export control.
- [ ] Build replay/compare view.
- [ ] Build health/status page for connected QSOL services.
- [ ] Add accessible keyboard-first interface and mobile fallback.

### UI invariant

Never display a synthetic `truth percentage` derived from votes, confidence, entropy, model count, consensus, retrieval score, embedding similarity, codon frequency, or lattice position.

## Phase 6 — AI / agent API

- [ ] Implement structured request/response API.
- [ ] Implement `control.health` and capability discovery.
- [ ] Implement `control.ask`.
- [ ] Implement File upload/reference operations.
- [ ] Implement Collection create/snapshot/search operations.
- [ ] Implement run retrieval/comparison.
- [ ] Implement evidence/Council/model-state retrieval.
- [ ] Implement bounded lattice traversal.
- [ ] Add caller quotas and resource limits.
- [ ] Add machine-readable error taxonomy.
- [ ] Keep AI caller epistemic privilege equal to human caller privilege.

## Phase 7 — Replay and longitudinal research

- [ ] Implement replay classification.
- [ ] Bind replay to exact Collection snapshot and index descriptor used originally.
- [ ] Compare original run with current evidence.
- [ ] Explain changes in evidence set, Collection membership, Council roster, model revision, runtime, and configuration.
- [ ] Preserve original result immutably.
- [ ] Produce deterministic comparison reports.
- [ ] Add research timeline view for recurring questions.

## Phase 8 — ARK recovery bridge

- [x] Define a reversible DNA/lattice projection for individual File bytes.
- [x] Define deterministic portable CONCAP bundle machinery over `QSOL-RESTORE-DAT/1`.
- [x] Define minimum recoverable CONTROL bundle.
- [ ] Export raw objects, File records, Collection descriptors/snapshots, schemas, run records, model states, and lattice addressing rules as a broader repository-level recovery package.
- [ ] Include optional DNA/lattice projections and search-index descriptors without requiring them as canonical source.
- [ ] Add plain-text recovery map.
- [ ] Add standard-library validator/reconstructor for the broader recovery package.
- [ ] Test reconstruction of the broader package without CONTROL WebUI or original search engine.
- [ ] Add constrained-environment recovery fixtures.

The Phase 1B minimum bundle already provides a standard-library validator/reconstructor for one run and excludes the WebUI/search engine. The remaining Phase 8 items describe a wider repository/system recovery package and are deliberately not marked complete by that narrower proof.

## Phase 9 — INT composition batteries

- [ ] Add cross-repo compatibility receipts for CONTROL↔ORACLE and CONTROL↔NEXUS.
- [ ] Add CONTROL↔THOTH portable CONCAP compatibility receipts.
- [ ] Test authority non-escalation.
- [ ] Test stale-parent handling.
- [ ] Test vote/evidence separation.
- [ ] Test memory/canonical separation.
- [ ] Test model-state/identity separation.
- [ ] Test Collection/search-index authority separation.
- [ ] Test DNA/lattice projection/raw-byte canonical separation.
- [ ] Test schema/version drift.

## Phase 10 — Hardening and release discipline

- [ ] Threat-model network and browser boundaries.
- [ ] Expand secret-scrubbing tests for File metadata/imports.
- [ ] CSRF/CORS/session protection as applicable to chosen runtime.
- [ ] Strict local-bind default for operator service.
- [x] Add portable CONCAP metadata/count limits and hostile-input guards.
- [ ] Import/export decompression-bomb defenses where compressed untrusted inputs are accepted.
- [ ] Fuzz/adversarial storage tests.
- [ ] Reproducible release bundle.
- [ ] Versioned migration policy.
- [ ] Release checklist and changelog discipline.

## Deferred / explicitly not promised yet

- [ ] Remote multi-user deployment.
- [ ] Mobile native applications.
- [ ] Distributed consensus for CONTROL storage.
- [ ] Automatic truth scoring.
- [ ] Hidden chain-of-thought capture.
- [ ] Literal geometric-cognition claims from the lattice.
- [ ] Biological claims from the DNA-symbol codec.
- [ ] Claims that φ traversal is physically optimal storage.

The last four are less "deferred" and more "please do not invent these while nobody is looking."
