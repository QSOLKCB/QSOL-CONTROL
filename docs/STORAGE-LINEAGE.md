# QSOL-CONTROL Storage Lineage

QSOL-CONTROL Phase 1 reuses several ideas from earlier QSOL projects as **conceptual design lineage**. No source code from the projects below is copied into the persistent-storage runtime by this PR.

The purpose of this document is to preserve where the ideas came from while keeping their original domain claims separate from CONTROL's storage contracts.

## QSOLAI

Repository: `QSOLKCB/QSOLAI`

Relevant ideas:

- strict canonical JSON;
- deterministic post-capture processing;
- integer/lexicographic ranking;
- stable hash tie-breaking;
- forward-only state transitions;
- manifest and replay discipline.

CONTROL reuses this **deterministic orchestration discipline**, especially lexicographic ordering and content-bound identity.

It does not import QSOLAI's worker/runtime architecture as the storage engine.

## QAI-UFT

Repository: `QSOLKCB/QAI-UFT`

Relevant published design vocabulary:

- trinary Digital DNA / base-3 representation;
- codon wheel / mod-64 slots;
- deterministic numeric mappings.

CONTROL adapts these ideas into a storage codec with a deliberately narrower meaning:

```text
outer structure:
  3 x 3 x 3 lattice
  = ternary coordinate space
  = 27 cells

inner payload projection:
  A C G T
  = four symbols
  = two bits per symbol

three DNA symbols:
  3 x 2 bits
  = 6 bits
  = 64 possible codon slots
```

The coincidence between 64 codons and a six-bit digital group is used as a deterministic encoding convenience. CONTROL makes no biological or unified-field claim from it.

## supreme-engine

Repository: `QSOLKCB/supreme-engine`

Public description:

> A lightweight AI simplification module enforcing single-path responses with φ-spiral gating.

CONTROL borrows only the **single-path φ-gating concept** for an optional deterministic lattice traversal.

For the fixed 27-cell lattice, the profile uses:

```text
phi_stride = 17
```

where 17 is the protocol constant corresponding to `round(27 / φ)`. Because `gcd(17, 27) = 1`, repeated modular stepping visits every cell exactly once.

```text
index(n) = (17 * n) mod 27
```

This is named `qsol.phi-stride-27/1`.

The traversal is an addressing/read-order projection only. It is not evidence that φ is physically optimal for storage, cognition, memory, biology, or anything else.

## THESIS

Repository: `QSOLKCB/THESIS`

The thesis uses golden-ratio scaling as part of a broader speculative cosmological framework.

CONTROL takes only the **mathematical φ-scaling motif** as historical design lineage for the optional traversal name and fixed stride derivation.

The storage implementation does not import or validate the thesis's cosmological claims.

## Why the boundaries matter

The same symbol can be useful in multiple fields without carrying authority between them.

```text
USEFUL_ENCODING_ANALOGY != EMPIRICAL_VALIDATION
DNA_SYMBOL != BIOLOGICAL_DNA_OBJECT
PHI_TRAVERSAL != PHYSICAL_LAW
CODON_SLOT != GENETIC_FUNCTION
LATTICE_COORDINATE != COGNITIVE_LOCATION
```

CONTROL therefore keeps the storage mechanism testable in ordinary computer-science terms:

- byte-exact round trips;
- canonical ordering;
- immutable snapshots;
- SHA-256 verification;
- finite bounded traversal;
- schema validation;
- stale-index detection;
- explicit provenance.

## License boundary

The Phase-1 implementation is original QSOL-CONTROL code under this repository's MPL-2.0 license.

The referenced repositories remain governed by their own licenses and records. This document records conceptual lineage and does not relicense their content.
