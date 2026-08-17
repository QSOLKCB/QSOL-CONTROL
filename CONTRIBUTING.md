# Contributing to QSOL-CONTROL

QSOL-CONTROL is an authority-sensitive control plane. Contributions should improve orchestration, inspection, storage, or operator usability without silently moving responsibilities out of their owning QSOL systems.

## Before opening a change

Read:

1. `README4AI.md`
2. `AGENTS.md`
3. `ARCHITECTURE.md`
4. `SECURITY.md`
5. the relevant document under `docs/`

## Local validation

Phase 0 validation requires **Python 3.11+** and intentionally has no third-party Python dependencies.

Run before opening or updating a PR:

```bash
python3 -m compileall -q tools tests
python3 tools/validate_control.py
python3 -W default -m unittest discover -s tests -v
```

The validator checks the architecture/authority invariants, JSON Schema draft declaration, SemVer-shaped schema version, lattice contract, declared files, and canonical valid/invalid schema fixtures.

If you change a schema, update its canonical examples in `examples/schema/` in the same PR. A valid fixture must remain accepted and its paired invalid fixture must remain rejected.

## Pull request expectations

A substantial PR should state:

- what changed;
- which authority boundary it touches;
- whether human and machine surfaces remain synchronized;
- whether stored/replayed records change shape;
- security implications;
- tests/validation used;
- migration implications if a versioned schema changes.

## Architecture changes

If a change modifies the role of CONTROL, ORACLE, NEXUS, SUBSTRATE, ARK, INT, or lattice memory, update all relevant human and machine contracts in the same PR.

Do not redefine parent-system behavior from memory. Inspect the current parent contract first.

## Schema/version changes

QSOL-CONTROL uses JSON Schema draft 2020-12. `manifest.json` declares semantic versioning rules for public contracts:

- major for breaking contract changes;
- minor for backward-compatible additions;
- patch for non-semantic corrections/clarifications.

Do not silently reinterpret an existing lattice coordinate or public field. If meaning changes, version the contract/profile and document migration behavior.

## Storage changes

Storage changes must preserve:

```text
content identity != lattice address
storage != evidence authority
model state != model mind
history != mutable convenience
```

Prefer immutable records plus new correction/derivation records over silent historical rewrites.

## Privacy/security changes

Read `SECURITY.md` before adding new stored metadata. New fields must answer:

- why the field is required;
- whether it may contain PII/account/device identifiers;
- its redaction behavior;
- its access class;
- its retention expectation;
- whether it is safe for ARK/public export.

Credentials and hidden chain-of-thought are forbidden persistence classes, not merely fields to document carefully.

## UI changes

Do not introduce visual language implying that:

- model confidence is probability of truth;
- Council majority is evidence status;
- consensus means verification;
- `unknown` means system failure.

## AI/API changes

Machine clients must not receive hidden epistemic or administrative privileges unavailable to equivalent authorized human workflows.

## Dependencies

Prefer small, inspectable components. Every dependency should justify the attack surface, maintenance burden, and long-horizon recovery cost it adds.

In short: **thou shalt not write bloat, especially in the control plane.**
