# QSOL-CONTROL WebUI

## Goal

The WebUI is the human operator surface for asking the QSOL system questions and inspecting how the result was produced.

It must not reduce a multi-dimensional result to a single authoritative-looking confidence meter.

## Primary workflow

The question composer should expose two explicit modes:

```text
[ Show me the evidence ]
[ Ask the Council ]
```

### Evidence-only

Display:

- ORACLE state (`known`, `conflict`, `unknown`);
- source/provenance references;
- freshness and observation metadata when available;
- evidence gaps;
- suggested searches clearly marked non-evidence.

### Ask Council

Display evidence plus:

- NEXUS Council roster;
- phase outputs that NEXUS exposes;
- sealed ballots;
- exact consensus threshold;
- consensus/no-consensus result;
- minority reports;
- NEXUS receipts;
- ORACLE witness receipts where available;
- participating model-state records.

## Suggested navigation

```text
ASK | EVIDENCE | COUNCIL | MINORITY | SOURCES | TIMELINE | RECEIPTS | MODELS | MEMORY | REPLAY
```

## Result hierarchy

The UI should visually separate:

```text
Question
Evidence status
Evidence
Council reasoning outputs
Votes
Consensus status
Minority reports
Receipts
Model/runtime state
Replayability
```

A vote visualization is a vote visualization. It must not be labelled `truth probability`.

## Evidence states

### Known

Show what ORACLE can establish and why.

### Conflict

Show competing evidence without averaging the conflict away.

### Unknown

Show:

- what is unavailable;
- what evidence would help;
- possible search targets;
- a clear indication that search suggestions are not evidence.

`UNKNOWN` should be a first-class, visually normal result — not styled as system failure.

## Council visualization

The Council view should preserve NEXUS phase ordering and sealed-vote semantics. CONTROL must not reorder votes to make a narrative look cleaner.

Potential display:

```text
WHITE   [output]
RED     [output]
BLACK   [output]
YELLOW  [output]
GREEN   [output]
BLUE    [output]

SEALED BALLOT
SUPPORT      3
UNCERTAIN    2
REJECT       1

Threshold: 4/6
Result: NO CONSENSUS
```

The actual ballot vocabulary must come from the NEXUS operation/result contract rather than being invented by the frontend.

## Model-state inspector

Phase 4 defines the model-state inspector's labels before the Phase 5 WebUI exists. The frontend must consume the same label contract from `ai/model-state-contract.json` rather than inventing a more anthropomorphic presentation.

Required visible labels:

```text
Panel title:        Model-state reproducibility metadata
Boundary badge:     Not model mind
Provenance heading: Metadata provenance
Unknown:            Unknown / not established
Locally verified:   Locally verified
Provider reported:  Provider reported
Inferred:           Inferred — not verified
Observed:           Observed
```

For each state, show externally inspectable metadata together with its field-level provenance classification. Missing or unclassified fields render `Unknown / not established`; they do not become false, absent, or provider-verified by implication.

Locally hash-verified artifact identities should be distinguishable from provider-reported model names/revisions. Hashes may be displayed as artifact identities, but the UI must not imply that CONTROL stores the underlying model/weight/tokenizer bytes when it does not.

Comparison views may show configuration and provenance changes, but must retain:

```text
MODEL_STATE != MODEL_MIND
MODEL_STATE_COMPARISON != MIND_COMPARISON
RUNTIME_METADATA != CONSCIOUSNESS
```

Never render hidden-chain-of-thought placeholders, expandable `private reasoning` panels, `AI mind`, `internal thoughts`, consciousness indicators, or equivalent wording implying that CONTROL possesses private cognition.

## Lattice browser

The memory view may visualize the 3×3×3 logical cells and recursive children, but every visual cell must resolve to ordinary inspectable records.

The geometry is navigation, not metaphysics.

## Replay / comparison

A comparison view should separate changes in:

- evidence;
- ORACLE snapshot;
- NEXUS version;
- Council roster;
- model/runtime revisions;
- sampling/configuration;
- outputs and votes.

Suggested comparison labels:

```text
ORIGINAL RUN
CURRENT RERUN
CHANGED EVIDENCE
CHANGED MODELS
CHANGED CONFIGURATION
RESULT DIFFERENCE
```

## Accessibility

Implementation should target:

- keyboard operation;
- semantic HTML;
- screen-reader labels;
- non-colour-only status indicators;
- readable raw JSON views for technical inspection;
- mobile fallback for basic evidence/Council inspection.

The `Not model mind` boundary must remain available to assistive technology; it must not be conveyed only by colour or iconography.

## Forbidden UI shortcuts

Do not display:

```text
AI TRUTH SCORE: 87%
PROBABILITY TRUE: <derived from model confidence>
6/6 MODELS AGREE -> VERIFIED
AI MIND STATE
HIDDEN THOUGHTS AVAILABLE
CONSCIOUSNESS LEVEL
```

unless a future protocol supplies an independently meaningful, correctly defined quantity with provenance. Council agreement alone is not such a quantity, and Phase 4 model-state metadata is not a cognition or consciousness measure.
