# QSOL-CONTROL — NEXUS / ORACLE Boundary

## The short version

```text
ORACLE provides evidence.
NEXUS provides governed reasoning.
CONTROL operates the workflow.
```

CONTROL is not allowed to blur those responsibilities merely because it can display them on the same screen.

## Evidence-only path

```text
caller
  -> CONTROL
  -> ORACLE
  -> evidence state + provenance + gaps
  -> CONTROL
  -> caller
```

No Council run is required.

## Council path

```text
caller
  -> CONTROL
  -> ORACLE evidence retrieval / admitted refs
  -> CONTROL
  -> NEXUS Council invocation
  -> visible phase outputs / ballots / minority reports / receipts
  -> optional ORACLE witness receipt
  -> CONTROL storage + rendering
  -> caller
```

## NEXUS ownership

CONTROL must treat the following as NEXUS-owned behavior:

- Council roster semantics;
- phase order;
- same-phase blindness/barriers;
- sealed ballot mechanics;
- vote weights;
- consensus threshold;
- minority reports;
- WorldStore identity/lineage;
- NEXUS receipts;
- model adapter/governance behavior.

CONTROL may display or request these. It may not reimplement a contradictory version and call it NEXUS.

## ORACLE ownership

CONTROL must treat the following as ORACLE-owned behavior:

- witnessed observations;
- evidence provenance classification;
- append-only ledger semantics;
- `known`, `conflict`, `unknown` evidence responses;
- temporal-contract state such as the QSOL-CONTEXT 2056 publication directive;
- ORACLE event identities/receipts.

CONTROL storage may cache or reference ORACLE results, but cached copies do not become new ORACLE authority.

## Stenographer relationship

NEXUS's Courtroom Stenographer is a passive local AI-action study ledger with zero control authority. ORACLE generalizes ecosystem witnessing outside NEXUS.

CONTROL may expose both where useful, but must label provenance clearly so a user can tell whether a record came from:

```text
NEXUS Stenographer
QSOL-ORACLE
CONTROL interaction storage
```

`stored in CONTROL` is not equivalent to `witnessed by ORACLE`.

## Claim boundary

A rendered answer may have several independent dimensions:

```text
ORACLE evidence state: CONFLICT
NEXUS Council result: 5/6 support interpretation A
Consensus threshold: met
Minority report: present
```

CONTROL must preserve the tension. It must **not** rewrite that as:

```text
VERIFIED TRUE: interpretation A
```

## Availability behavior

If ORACLE is unavailable:

- mark evidence path unavailable;
- do not manufacture evidence;
- Council invocation should follow an explicit policy about whether an evidence-unavailable run is permitted and how it is labelled.

If NEXUS is unavailable:

- evidence-only mode may still work;
- Council mode is unavailable;
- CONTROL must not silently substitute its own local vote simulation.

## Version drift

Adapters should discover/report parent protocol versions and preserve them in run records. Later INT integration should test compatibility and stale-parent conditions.
