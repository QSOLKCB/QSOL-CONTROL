# Changelog

All notable changes to QSOL-CONTROL will be documented here.

## Contract versioning

Public contract/schema versions use `MAJOR.MINOR.PATCH` semantics as declared in `manifest.json`:

- major: breaking schema or authority-contract changes;
- minor: backward-compatible optional fields/capabilities;
- patch: corrections or clarifications that do not change accepted contract meaning.

JSON Schemas use draft 2020-12. Lattice profiles are versioned independently because coordinate semantics must never drift silently.

## Unreleased

### Added

- QSOL-CONTROL human + AI control-plane architecture.
- Full QSOL architecture map and authority boundaries.
- Human WebUI design contract.
- AI/agent machine-interface contract.
- 3×3×3 Sierpinski-derived lattice memory specification.
- AI model-state preservation contract for future computational archaeology.
- ORACLE/NEXUS orchestration boundary.
- Initial query, interaction-record, and model-state JSON Schemas using JSON Schema draft 2020-12.
- Canonical valid and intentionally invalid fixtures for all three public schemas.
- Dependency-free fixture validation and regression coverage.
- Explicit schema SemVer and lattice-profile migration/unknown-version policy.
- Model-state privacy classification, redaction, access-control, and retention guidance.
- Machine-readable constitution and lattice contract.
- Security and contributor documentation.
- Phased implementation roadmap.

### Validation

Phase 0 requires Python 3.11+ and validates with:

```bash
python3 tools/validate_control.py
python3 -W default -m unittest discover -s tests -v
```

### Status

PR #1 is an architecture/contracts bootstrap. It intentionally does not claim a working WebUI, runtime API, live ORACLE/NEXUS transport, or persistent lattice engine yet.
