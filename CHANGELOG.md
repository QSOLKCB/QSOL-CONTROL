# Changelog

All notable changes to QSOL-CONTROL will be documented here.

## Contract versioning

Public contract/schema versions use `MAJOR.MINOR.PATCH` semantics as declared in `manifest.json`:

- major: breaking schema or authority-contract changes;
- minor: backward-compatible optional fields/capabilities;
- patch: corrections or clarifications that do not change accepted contract meaning.

JSON Schemas use draft 2020-12. Lattice profiles are versioned independently because coordinate semantics must never drift silently.

## Unreleased

### Added — Phase 1A persistent storage

- Content-addressed raw File objects using SHA-256.
- Immutable File metadata records separate from raw object identity.
- Persistent named Collections.
- Immutable Collection membership snapshot chains with atomic `HEAD` updates.
- Lexicographically sorted Collection membership and deterministic search tie-breaking.
- Dependency-free lexical retrieval baseline (`qsol.term-frequency-cosine/1`).
- Semantic-vector index registration/search (`qsol.cosine-vector-search/1`) with explicit provider/model/revision metadata.
- Exact Collection-snapshot binding for every derived search index.
- Fail-closed stale semantic-index behavior after Collection membership changes.
- Canonical storage verification and deterministic fingerprinting.
- `tools/storage_cli.py` operator interface.
- File, Collection, Collection Snapshot, Search Index, and DNA Lattice JSON Schemas.
- Runtime/adversarial tests for corruption, immutable history, stale indexes, semantic-vector dimensions and storage identity.

### Added — DNA/codon lattice projection

- Reversible `A/C/G/T` two-bit byte encoding (`A=00`, `C=01`, `G=10`, `T=11`).
- Three-base codon mapping to exact six-bit / 0–63 slots.
- Round-robin codon distribution over the 27-cell 3×3×3 lattice.
- Canonical lexicographic traversal (`qsol.lexicographic-27/1`).
- Optional deterministic φ-gated traversal (`qsol.phi-stride-27/1`) using fixed stride 17.
- Byte-length, content-hash, codon-count and histogram verification.
- `dna-export` and `dna-decode` CLI operations.
- Explicit boundaries: raw bytes remain canonical; DNA is derived/rebuildable; no compression, biological, physical or authority claim is inferred.
- Storage-lineage documentation connecting the design to QSOLAI, QAI-UFT, `supreme-engine`, and THESIS while preserving domain boundaries.

### Added — Phase 0 foundation (PR #1)

- QSOL-CONTROL human + AI control-plane architecture.
- Full QSOL architecture map and authority boundaries.
- Human WebUI design contract.
- AI/agent machine-interface contract.
- 3×3×3 Sierpinski-derived lattice memory specification.
- AI model-state preservation contract for future computational archaeology.
- ORACLE/NEXUS orchestration boundary.
- Initial query, interaction-record, and model-state JSON Schemas.
- Canonical valid and intentionally invalid fixtures.
- Dependency-free fixture validation and regression coverage.
- Explicit schema SemVer and lattice-profile migration/unknown-version policy.
- Model-state privacy classification, redaction, access-control, and retention guidance.
- Machine-readable constitution and lattice contract.
- Security and contributor documentation.
- Phased implementation roadmap.

### Validation

Requires Python 3.11+ and validates with:

```bash
python3 tools/validate_control.py
python3 -W default -m unittest discover -s tests -v
```

### Status

- PR #1: architecture/contracts bootstrap — merged.
- PR #2: persistent Files/Collections, retrieval indexes, and DNA/lattice recovery projection — in development.
- Live ORACLE/NEXUS adapters, persistent interaction/run lattice, WebUI and network AI API remain deferred to later roadmap phases.
