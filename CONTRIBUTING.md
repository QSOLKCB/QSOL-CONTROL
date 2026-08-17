# Contributing to QSOL-CONTROL

QSOL-CONTROL is an authority-sensitive control plane. Contributions should improve orchestration, inspection, storage, or operator usability without silently moving responsibilities out of their owning QSOL systems.

## Before opening a change

Read:

1. `README4AI.md`
2. `AGENTS.md`
3. `ARCHITECTURE.md`
4. `SECURITY.md`
5. the relevant document under `docs/`

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

## Storage changes

Storage changes must preserve:

```text
content identity != lattice address
storage != evidence authority
model state != model mind
history != mutable convenience
```

Prefer immutable records plus new correction/derivation records over silent historical rewrites.

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
