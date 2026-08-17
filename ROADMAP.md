# QSOL-CONTROL Roadmap

## Phase 0 — Architecture and contracts

- [x] Define CONTROL as the human + AI operator plane.
- [x] Preserve Three-Pillar / ORACLE / NEXUS authority boundaries.
- [x] Define human WebUI and machine API surfaces.
- [x] Define 3×3×3 Sierpinski-derived lattice memory semantics.
- [x] Define AI model-state preservation boundary.
- [x] Add human and machine bootstrap documentation.
- [x] Add initial schemas and constitutional contracts.
- [ ] Add dependency-free repository validator and CI contract checks.

## Phase 1 — Deterministic storage substrate

- [ ] Implement canonical JSON interaction records.
- [ ] Implement content-addressed run IDs.
- [ ] Implement deterministic lattice-address assignment.
- [ ] Implement immutable lineage between questions, evidence, responses, receipts, and model states.
- [ ] Implement append-only local persistence with atomic writes.
- [ ] Add storage integrity/fingerprint command.
- [ ] Add adversarial tests for mutation, path traversal, duplicate identities, and lineage loops.
- [ ] Define storage export bundle for ARK recovery.

### Gate

No network or model integration until the storage layer can round-trip and verify deterministic fixtures offline.

## Phase 2 — ORACLE adapter

- [ ] Discover ORACLE protocol/version at runtime.
- [ ] Query evidence-only state: `known`, `conflict`, `unknown`.
- [ ] Preserve ORACLE provenance/event references without copying authority.
- [ ] Store ORACLE receipts by reference + verified payload identity.
- [ ] Surface suggested searches as non-evidence.
- [ ] Add ORACLE availability/freshness indicators.
- [ ] Add timelock status view for QSOL-CONTEXT 2056 publication contract.

### Security gate

CONTROL must be unable to append, rewrite, or relabel ORACLE history through the read/query adapter.

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

- [ ] Implement `qsol-control-model-state/1` records.
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
- [ ] Build evidence panel.
- [ ] Build Council phase + sealed-vote panel.
- [ ] Build minority-report panel.
- [ ] Build sources/provenance panel.
- [ ] Build ORACLE timeline/receipt view.
- [ ] Build model-state inspector.
- [ ] Build lattice-memory browser.
- [ ] Build replay/compare view.
- [ ] Build health/status page for connected QSOL services.
- [ ] Add accessible keyboard-first interface and mobile fallback.

### UI invariant

Never display a synthetic `truth percentage` derived from votes, confidence, entropy, model count, or consensus.

## Phase 6 — AI / agent API

- [ ] Implement structured request/response API.
- [ ] Implement `control.health` and capability discovery.
- [ ] Implement `control.ask`.
- [ ] Implement run retrieval/comparison.
- [ ] Implement evidence/Council/model-state retrieval.
- [ ] Implement bounded lattice traversal.
- [ ] Add caller quotas and resource limits.
- [ ] Add machine-readable error taxonomy.
- [ ] Keep AI caller epistemic privilege equal to human caller privilege.

## Phase 7 — Replay and longitudinal research

- [ ] Implement replay classification.
- [ ] Compare original run with current evidence.
- [ ] Explain changes in evidence set, Council roster, model revision, runtime, and configuration.
- [ ] Preserve original result immutably.
- [ ] Produce deterministic comparison reports.
- [ ] Add research timeline view for recurring questions.

## Phase 8 — ARK recovery bridge

- [ ] Define minimum recoverable CONTROL bundle.
- [ ] Export schemas, contracts, run records, model states, and lattice addressing rules.
- [ ] Add plain-text recovery map.
- [ ] Add standard-library validator/reconstructor.
- [ ] Test reconstruction without CONTROL WebUI.
- [ ] Add constrained-environment recovery fixtures.

## Phase 9 — INT composition batteries

- [ ] Add cross-repo compatibility receipts for CONTROL↔ORACLE and CONTROL↔NEXUS.
- [ ] Test authority non-escalation.
- [ ] Test stale-parent handling.
- [ ] Test vote/evidence separation.
- [ ] Test memory/canonical separation.
- [ ] Test model-state/identity separation.
- [ ] Test schema/version drift.

## Phase 10 — Hardening and release discipline

- [ ] Threat-model network and browser boundaries.
- [ ] Secret-scrubbing tests.
- [ ] CSRF/CORS/session protection as applicable to chosen runtime.
- [ ] Strict local-bind default for operator service.
- [ ] Import/export size limits and decompression-bomb defenses.
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

The last three are less "deferred" and more "please do not invent these while nobody is looking."
