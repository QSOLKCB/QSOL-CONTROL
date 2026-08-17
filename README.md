# QSOL-CONTROL

**A human + AI control plane for the QSOL ecosystem, orchestrating NEXUS Council reasoning, ORACLE evidence, deterministic votes, replayable queries, and 3×3×3 lattice memory for preserving questions, responses, provenance, and AI model states.**

> **CONTROL controls the machinery, not reality.**
>
> A button becoming green does not make a claim true. Six models agreeing does not make a claim true either. It merely means six models have found a way to agree, which is interesting evidence about six models.

QSOL-CONTROL is the operator layer for the wider QSOL architecture. It exposes the same underlying system through two deliberately separate surfaces:

- **Human control plane** — browser/WebUI for asking questions, inspecting evidence, viewing Council votes, minority reports, timelines, receipts, model-state records, and replays.
- **AI control plane** — structured machine interface for agents or other AI systems to submit questions, inspect evidence, request Council runs, retrieve receipts, and traverse stored interaction history.

CONTROL does **not** own scientific truth, public epistemic authority, Council vote mechanics, ORACLE history, or recovery authority. It orchestrates systems that already own those responsibilities.

## Full architecture

```text
                                      HUMAN OPERATOR
                                           |
                                   browser / WebUI
                                           |
                                           v
                             +-----------------------------+
                             |        QSOL-CONTROL         |
                             |           OPERATES          |
                             |-----------------------------|
                             | Human WebUI                 |
                             | AI / agent API              |
                             | query router                |
                             | run orchestration           |
                             | vote / evidence views       |
                             | replay / comparison         |
                             | model-state inspection      |
                             +--------------+--------------+
                                            |
                         +------------------+------------------+
                         |                                     |
                 evidence-only                         Council reasoning
                         |                                     |
                         v                                     v
              +----------------------+              +----------------------+
              |     QSOL-ORACLE      |<------------>|      QSOL-NEXUS      |
              |      WITNESSES       |   receipts   |       REASONS        |
              |----------------------|              |----------------------|
              | provenance           |              | AI Council           |
              | observations         |              | WHITE -> RED         |
              | conflicts            |              | -> BLACK -> YELLOW   |
              | unknowns             |              | -> GREEN -> BLUE     |
              | append-only ledger   |              | -> SEALED BALLOT     |
              | temporal contracts   |              | minority reports     |
              +----------+-----------+              +-----------+----------+
                         |                                          |
                         |         witnessed records / runs         |
                         |                                          |
                         +------------------+-----------------------+
                                            |
                                            v
                             +-----------------------------+
                             |  3 x 3 x 3 LATTICE MEMORY   |
                             |        REMEMBERS            |
                             |-----------------------------|
                             | questions                   |
                             | responses                   |
                             | evidence refs               |
                             | Council ballots             |
                             | minority reports            |
                             | AI model-state records      |
                             | provenance / lineage        |
                             | recovery metadata           |
                             +--------------+--------------+
                                            |
                              preservation / reconstruction
                                            |
                                            v
                                   +----------------+
                                   |    QSOL-ARK    |
                                   |    SURVIVES    |
                                   +----------------+

        +----------------------+     +----------------------+     +----------------------+
        |   QSOL-SUBSTRATE     |     |       QSOL-ARK       |     |       QSOL-INT       |
        |        KNOWS         |     |       SURVIVES       |     |       COMPOSES        |
        | public epistemic     |     | recovery contracts   |     | cross-repo integrity |
        | state + provenance   |     | reconstruction       |     | drift + handoff      |
        +-----------+----------+     +-----------+----------+     +-----------+----------+
                    \___________________________|___________________________/
                                                |
                                      THREE-PILLAR FOUNDATION

       QSOL-CONTEXT (private working context)
             |
             | explicit/publication-safe projections only
             v
       QSOL-SUBSTRATE

       QSOL-ORACLE publication contract:
       QSOL-CONTEXT -> eligible for public release on 18 Aug 2056
       ELIGIBLE != EXECUTED
```

## The verbs

```text
QSOL-SUBSTRATE  KNOWS
QSOL-ARK        SURVIVES
QSOL-INT        COMPOSES
QSOL-ORACLE     WITNESSES
QSOL-NEXUS      REASONS
QSOL-CONTROL    OPERATES
LATTICE MEMORY  REMEMBERS
```

The lattice memory is a CONTROL storage protocol, **not another authority-bearing pillar**.

## Human question flow

```text
Human
  -> CONTROL receives question
  -> ORACLE supplies bounded evidence / known / conflict / unknown state
  -> NEXUS runs the Council against the admitted evidence
  -> sealed ballots and minority reports are preserved
  -> ORACLE witnesses externally visible run receipts
  -> CONTROL renders evidence, reasoning outputs, votes, uncertainty, and provenance
  -> LATTICE stores the interaction and model-state records
```

A typical result should expose dimensions separately:

```text
QUESTION
EVIDENCE STATE
SOURCES
COUNCIL OUTPUTS
SEALED VOTES
CONSENSUS STATUS
MINORITY REPORTS
ORACLE RECEIPT
MODEL STATES
REPLAY ID
```

CONTROL must never collapse those into a fake meter such as `TRUTH = 87%`.

## AI question flow

Another AI or automated system may use the machine interface:

```json
{
  "operation": "control.ask",
  "question": "Does the current admitted evidence support hypothesis X?",
  "mode": "council",
  "include": [
    "oracle_evidence",
    "votes",
    "minority_reports",
    "model_states",
    "receipts"
  ]
}
```

The caller receives structured results rather than privileged truth access. AI callers receive **no more epistemic authority than human callers**.

## 3×3×3 Sierpinski-derived lattice memory

CONTROL defines a **3×3×3 Sierpinski-derived logical lattice** with 27 top-level cells. The term is deliberately `Sierpinski-derived`: this is an information architecture inspired by recursive/fractal partitioning, not a claim that the datastore is literally a mathematical Sierpinski triangle.

The first-level axes are:

```text
X = information role   question | response | evidence
Y = epistemic role     observed | derived | unresolved
Z = temporal role      current | historical | recovery
```

A record therefore receives a deterministic logical coordinate:

```text
L[x,y,z]
```

Cells may recursively expose another 3×3×3 namespace when a future storage profile needs subdivision:

```text
L[2,1,0]/[0,2,1]/...
```

Geometry is an addressing and recovery discipline. **GEOMETRY != TRUTH.**

See [`docs/LATTICE-MEMORY.md`](docs/LATTICE-MEMORY.md).

## AI model-state preservation

For every participating model, CONTROL should preserve externally inspectable state sufficient for future archaeology where available:

```text
provider / runtime
model identifier + revision
open/closed-weight status when known
model or weight hashes when available
architecture/tokenizer identity when available
quantization
context limits
sampling parameters
seed when deterministic
NEXUS protocol/runtime identity
ORACLE snapshot / receipt identity
SUBSTRATE snapshot identity
CONTROL run identity
Council seat / mode
allowed tools
execution timestamp
relevant hardware/runtime metadata
```

CONTROL does **not** claim to store a model's mind or hidden reasoning.

```text
MODEL_STATE != MODEL_MIND
VISIBLE_OUTPUT != HIDDEN_CHAIN_OF_THOUGHT
RUNTIME_METADATA != CONSCIOUSNESS
```

See [`docs/MODEL-STATE.md`](docs/MODEL-STATE.md).

## Constitutional invariants

```text
CONTROL_DISPLAY != AUTHORITY
CONTROL_OPERATION != TRUTH
VOTE != EVIDENCE
CONSENSUS != TRUTH
CONFIDENCE != PROBABILITY
STORED != TRUE
PERSISTED != CANONICAL
MODEL_STATE != EVIDENCE
AI_RESPONSE != FACT
MEMORY != AUTHORITY
HUMAN_CALLER == AI_CALLER_FOR_EPISTEMIC_AUTHORITY
CONTROL_MUST_NOT_REWRITE_ORACLE_HISTORY
CONTROL_MUST_NOT_CHANGE_NEXUS_VOTES
```

## Replay instead of chat amnesia

Each completed run should receive a content-bound identifier and preserve enough public metadata to compare the same question over time.

A future interface may offer:

```text
REPLAY ORIGINAL RUN
RE-RUN WITH CURRENT EVIDENCE
COMPARE RESULTS
EXPLAIN WHAT CHANGED
```

The comparison must distinguish changes caused by new evidence, different model roster, model/version drift, configuration changes, or stochastic inference. A later result does not rewrite an earlier result.

## Documentation map

- [`README4AI.md`](README4AI.md) — compact machine bootstrap.
- [`AGENTS.md`](AGENTS.md) — contributor/agent operating rules.
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — authority boundaries and system design.
- [`ROADMAP.md`](ROADMAP.md) — implementation sequence.
- [`SECURITY.md`](SECURITY.md) — control-plane and storage threat boundaries.
- [`docs/WEBUI.md`](docs/WEBUI.md) — human operator surface.
- [`docs/AI-API.md`](docs/AI-API.md) — machine caller contract.
- [`docs/LATTICE-MEMORY.md`](docs/LATTICE-MEMORY.md) — 27-cell recursive storage model.
- [`docs/MODEL-STATE.md`](docs/MODEL-STATE.md) — future-AI model-state preservation.
- [`docs/NEXUS-ORACLE.md`](docs/NEXUS-ORACLE.md) — orchestration boundary.
- [`manifest.json`](manifest.json) — canonical machine map.

## Status

**PR #1 bootstrap:** documentation, machine contracts, architecture, schemas, and roadmap. Runtime adapters, WebUI implementation, persistent storage engine, live ORACLE transport, and NEXUS Council invocation are intentionally sequenced after the contracts are reviewable.

---

**QSOL-CONTROL controls the machinery, not reality. If the Council unanimously votes that the Moon is made of cheese, CONTROL's job is to preserve the vote — not update astronomy.**
