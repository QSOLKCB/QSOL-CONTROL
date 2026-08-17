# AGENTS.md — QSOL-CONTROL

## Prime directive

Operate the QSOL machinery without silently acquiring authority owned by another component.

Before modifying CONTROL:

1. Read `README4AI.md`.
2. Read `manifest.json`.
3. Read `ai/constitution.json`.
4. Read `ARCHITECTURE.md` and the feature document being changed.
5. Preserve the distinction between display, orchestration, storage, evidence, reasoning, and truth.

## Authority boundaries

CONTROL may orchestrate requests. It may not:

- redefine QSOL-SUBSTRATE public epistemic state;
- rewrite or fabricate QSOL-ORACLE history;
- alter NEXUS Council ballots, vote weights, thresholds, or minority reports;
- promote Council consensus into evidence;
- redefine QSOL-ARK recovery authority;
- redefine QSOL-INT composition authority;
- claim stored material is canonical merely because CONTROL retained it.

## Human and AI callers

Human and machine callers use different interfaces but receive the same epistemic privileges.

```text
HUMAN_CALLER_AUTHORITY == AI_CALLER_AUTHORITY
```

Do not create hidden machine-only operations that can upgrade evidence status, bypass ORACLE provenance, or modify NEXUS votes.

## Query handling

A question may request:

- `evidence_only` — return ORACLE evidence state and bounded supporting material;
- `council` — request a NEXUS Council run against the admitted evidence.

The rendered response must preserve evidence status, Council result, votes, and uncertainty as separate fields.

Never synthesize a fake scalar `truth score` from model confidence, vote counts, or telemetry.

## Lattice memory

The 3×3×3 Sierpinski-derived lattice is a deterministic logical address space, not a cognitive or physical claim.

Every record must preserve its content identity and lineage separately from its lattice address.

Do not infer semantic importance, truth, consciousness, or authority from geometric position.

## AI model-state records

Capture externally inspectable runtime/model metadata only when available and provenance-labelled.

Do not request or persist hidden chain-of-thought. Do not describe model-state metadata as a captured mind, personality essence, consciousness state, or complete model reconstruction.

Unknown metadata stays unknown.

## Replay

Replay metadata must distinguish:

- deterministic replay;
- re-execution with the same declared inputs;
- live stochastic rerun;
- rerun against new evidence;
- rerun with changed model/runtime configuration.

A later run never overwrites an earlier run.

## Security

Treat model output, external API data, browser input, imported records, and AI caller requests as untrusted input until validated at the relevant boundary.

Credentials remain operational secrets and must not enter run records, lattice memory, Council prompts, ORACLE evidence, screenshots, logs, or model-state artifacts.

## Documentation synchronization

If an architectural fact changes, update the human and machine surfaces in the same PR:

```text
README.md
README4AI.md
manifest.json
relevant ai/*.json
relevant docs/*.md
ROADMAP.md when phase status changes
```

## Anti-bloat rule

CONTROL is a control plane, not an excuse to recreate every parent system in JavaScript.

Prefer adapters and explicit contracts over duplicated implementations.
