# QSOL-CONTROL Phase 7 Replay and Longitudinal Research

Phase 7 adds classified replay, immutable replay records, deterministic comparison reports, and recurring-question research timelines.

Replay does not mean “run the same prompt again and call it identical.” CONTROL classifies the available evidence for reproducibility before it executes anything.

```text
ORIGINAL_RUN != REPLAY_RUN
CURRENT_EVIDENCE != ORIGINAL_EVIDENCE
REPLAY_CLASSIFICATION != TRUTH
MODEL_STATE_COMPARISON != MIND_COMPARISON
```

## Replay lifecycle

```text
original immutable run
        |
        v
replay classification
        |
        +--> non-executable -> explain why, write nothing
        |
        v
new replay run
        |
        +--> exact original Collection snapshot
        +--> current ORACLE evidence
        +--> current configured Council/runtime where requested
        |
        v
deterministic comparison report
        |
        v
immutable replay record + replay-run lineage receipt
```

The original run record and original event chain are never rewritten. Phase 7 fingerprints the original run, events, and model-state metadata before and after replay execution and fails if they changed.

## Replay classification

`qsol-control-replay-classification/1` distinguishes:

```text
inspection_only
unavailable_original_context
current_evidence_rerun
legacy_current_evidence_rerun
evidence_refresh_only
council_configuration_unavailable
changed_configuration_rerun
live_stochastic_rerun
legacy_declared_input_reexecution
declared_input_reexecution
```

These labels describe reproducibility conditions. They do not grade truth or scientific quality.

A changed Council roster is never silently accepted. Replay execution requires explicit `allow_changed_configuration=true` when the current configured roster differs from the original committed roster.

## Exact Collection snapshot

If the original run used a Collection, replay passes the original exact:

```text
collection_id
snapshot_id
```

back into the normal `control.ask` path.

The current Collection `HEAD` is inspected separately for longitudinal comparison.

```text
REPLAY_COLLECTION_SNAPSHOT = ORIGINAL_COLLECTION_SNAPSHOT
CURRENT_COLLECTION_HEAD != ORIGINAL_COLLECTION_SNAPSHOT
```

A newer Collection HEAD never silently replaces the historical input.

## Retrieval / index descriptor

Phase 7 does not manufacture historical retrieval metadata.

Current `control.ask` does not execute Collection search. New Phase 7 runs therefore record:

```json
{
  "status": "not_used",
  "index_id": null,
  "descriptor": null,
  "reason": "control.ask does not execute Collection search"
}
```

Pre-Phase-7 runs do not contain a replay-basis receipt. Their index status is:

```text
not_recorded
```

This distinction is deliberate:

```text
NOT_USED != NOT_RECORDED
LEGACY_MISSING_INDEX != INVENTED_INDEX
```

If a future CONTROL operation actually uses a search index as an execution input, its replay basis must preserve the exact content-addressed index descriptor before that operation can claim same-index re-execution.

## Current evidence comparison

Replay queries ORACLE at replay time using the original recorded query configuration when available.

The report preserves:

- original evidence state;
- replay-time evidence state;
- evidence refs added;
- evidence refs removed;
- evidence refs unchanged.

```text
CURRENT_EVIDENCE != ORIGINAL_EVIDENCE
FRESH != TRUE
STALE != FALSE
```

A legacy run may lack the original ORACLE age/search-suggestion configuration. That absence remains explicit in its replay basis and classification.

## Council comparison

For Council runs the report keeps separate:

- original committed roster identity;
- replay committed roster identity;
- added/removed/changed seats;
- original NEXUS protocol/runtime version;
- replay NEXUS protocol/runtime version;
- original and replay consensus records.

Consensus remains a Council output, not evidence or truth.

```text
VOTE != EVIDENCE
CONSENSUS != TRUTH
CONTROL_INVOKES_COUNCIL != CONTROL_OWNS_COUNCIL
```

Phase 7 never requests hidden chain-of-thought.

## Model/runtime comparison

Replay reports reuse the Phase 4 model-state registry comparison machinery. Differences may include model ID, revision, runtime/runtime version, quantization, sampling, seed, context, tool permissions, and system identities where recorded.

```text
MODEL_STATE != MODEL_MIND
MODEL_STATE_COMPARISON != MIND_COMPARISON
PROVIDER_REPORTED != LOCALLY_VERIFIED
```

Missing model-state metadata stays missing.

## Deterministic comparison report

`qsol-control-replay-report/1` is canonical JSON and content-addressed.

It has independent lanes for:

1. evidence set;
2. Collection membership;
3. retrieval/index basis;
4. Council roster and NEXUS runtime;
5. model-state/runtime metadata;
6. request configuration.

No combined truth, confidence, fidelity, or quality percentage is derived from these differences.

## Replay storage

Replay metadata is stored separately from run history:

```text
records/replays/<sha256>.json
records/replay-reports/<sha256>.json
```

The replay run itself is an ordinary immutable CONTROL run. A `qsol-control-replay-link/1` receipt on the replay run links it back to the original and the deterministic report.

The original run receives no replay mutation.

## Recurring-question timeline

`qsol-control-research-timeline/1` groups runs by exact `question_sha256` and orders them by creation time then run ID.

Each run entry records available longitudinal state such as:

- evidence state and refs;
- Collection snapshot;
- Council roster/disposition;
- NEXUS runtime version;
- model-state summary;
- replay parent/children.

Transitions identify changes between adjacent runs without assigning truth meaning to the change.

```text
TIMELINE != TRUTH
CHANGE != IMPROVEMENT
CONSENSUS_CHANGE != EVIDENCE_CHANGE
```

## Human and machine interfaces

WebUI:

- Classify replay
- Execute classified replay
- Compare arbitrary immutable runs
- Recurring-question timeline

Agent API:

```text
control.replay.classify
control.replay.execute
control.replay.get
control.research.timeline
```

AI and human callers keep equal epistemic privilege. Replay execution is quota-governed like other machine mutations.

## Nonclaims

Phase 7 does not claim:

- deterministic reproduction of live stochastic inference merely because a model name matches;
- exact reproduction where historical runtime/configuration metadata is absent;
- an index was used when no index use was recorded;
- current evidence is the same evidence observed historically;
- changed consensus implies changed truth;
- model-state metadata captures a mind;
- replay reconstructs hidden provider state or hidden chain-of-thought.
