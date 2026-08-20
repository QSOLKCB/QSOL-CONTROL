# QSOL-CONTROL AI / Agent API

Phase 6 established `qsol-control-agent-api/1` as a dependency-free structured machine interface over the same CONTROL runtime used by the Human WebUI. Phase 7 extends that exact API with classified replay and longitudinal-research operations. It does not create a second machine interface or a privileged replay channel.

The transport remains local JSONL over stdin/stdout:

```text
AI / AGENT
    |
    v
qsol-control-agent-request/1
    |
    v
AgentAPIDispatcher
    |
    +--> CONTROL File / Collection / interaction storage
    +--> read-only ORACLE adapter
    +--> governance-preserving NEXUS Council adapter
    +--> model-state registry
    +--> Phase 7 replay runtime
    +--> lattice memory
```

Remote multi-user deployment is not implemented. The operation semantics remain transport-neutral so a later hardened transport can reuse them without creating a second authority model.

## Start

```bash
python3 tools/agent_api.py --root .qsol-control-store
```

Optional ORACLE and NEXUS configuration uses the same local paths and command descriptors as the WebUI:

```bash
python3 tools/agent_api.py \
  --root .qsol-control-store \
  --oracle-root /path/to/QSOL-ORACLE \
  --nexus-command-json '["python3","-m","nexus_runtime","--world","/secure/nexus-world"]' \
  --nexus-members council-members.json
```

Each input line is exactly one UTF-8 JSON request and each output line is exactly one canonical JSON response.

## Request envelope

```json
{
  "protocol": "qsol-control-agent-request/1",
  "request_id": "example-1",
  "caller": {
    "kind": "ai",
    "id": "research-agent"
  },
  "operation": "control.health",
  "params": {}
}
```

External caller kinds are `human` and `ai`. They deliberately receive equal epistemic authority:

```text
HUMAN_CALLER_AUTHORITY == AI_CALLER_AUTHORITY
API_ACCESS != EPISTEMIC_PRIVILEGE
```

`caller.id` exists for process-local attribution and diagnostics. It is not trusted as the sole quota identity; hard process-wide request and mutation ceilings remain in force.

## Operations

The current exact operation catalogue is:

```text
control.health
control.capabilities
control.ask
control.file.put
control.file.get
control.collection.create
control.collection.snapshot
control.collection.search
control.run.get
control.run.compare
control.replay.classify
control.replay.execute
control.replay.get
control.research.timeline
control.evidence.get
control.council.get
control.models.get
control.memory.get
control.memory.trace
```

### Health and capabilities

`control.health` returns CONTROL storage and configured parent availability without treating availability as truth.

`control.capabilities` returns the exact operation catalogue, limits, question modes, replay implementation state, and negative capabilities such as `oracle_write_operations: []`.

### Ask

`control.ask` accepts the same bounded question modes as the WebUI:

```text
evidence_only
council
```

AI requests are persisted as `requester_kind: ai`; human machine-API requests are persisted as `requester_kind: human`. Both use the same ORACLE and NEXUS paths.

ORACLE remains read-only. Council invocation remains the existing verified `council.run` path. The API does not expose raw NEXUS operation passthrough, WorldStore mutation, vote weights, ballot overrides, or threshold overrides.

New Phase 7 runs also capture one append-only `qsol-control-replay-basis/1` receipt describing the reproducibility inputs available to later replay classification.

### Files

`control.file.put` stores exact decoded bytes as ordinary content-addressed CONTROL Files. Maximum input payload is 4 MiB.

Example parameters:

```json
{
  "filename": "evidence.txt",
  "media_type": "text/plain",
  "content_base64": "ZXZpZGVuY2U=",
  "privacy_class": "INTERNAL",
  "retention_class": "SESSION"
}
```

`control.file.get` returns immutable File metadata and optionally the exact raw bytes as base64.

```text
RAW_BYTES = CANONICAL
STORED != TRUE
```

### Collections

`control.collection.create` creates a persistent Collection and may accept an initial `file_ids` array. Initial members are committed through the same compare-and-swap snapshot machinery used by the WebUI.

`control.collection.snapshot` reads the current or an exact historical immutable snapshot.

`control.collection.search` uses the deterministic lexical baseline against one locked exact Collection HEAD.

```text
COLLECTION_MEMBERSHIP != ENDORSEMENT
SEARCH_SCORE != TRUTH
SEMANTIC_SIMILARITY != EVIDENCE_STRENGTH
```

### Runs, evidence, Council, and model state

`control.run.get` returns an immutable stored run view.

`control.run.compare` remains a non-executing comparison of two arbitrary immutable runs. The fact that Phase 7 replay exists does not turn this operation into replay execution.

`control.evidence.get` returns evidence state, ORACLE refs/events, and provenance sources as a separate view.

`control.council.get` returns externally visible Council response/receipt events and NEXUS object references. It does not expose hidden chain-of-thought.

`control.models.get` returns bounded model-state reproducibility metadata by run or exact state ID.

```text
VOTE != EVIDENCE
CONSENSUS != TRUTH
MODEL_STATE != MODEL_MIND
VISIBLE_OUTPUT != HIDDEN_CHAIN_OF_THOUGHT
```

## Phase 7 replay operations

### `control.replay.classify`

Parameters:

```json
{"run_id":"sha256:..."}
```

Classification happens before execution and describes the reproducibility conditions actually present. It may classify a run as executable, inspection-only, missing original context, a current-evidence rerun, a changed-configuration rerun, a live stochastic rerun, or another versioned Phase 7 class.

Classification is not truth scoring:

```text
REPLAY_CLASSIFICATION != TRUTH
```

### `control.replay.execute`

Parameters:

```json
{
  "run_id":"sha256:...",
  "allow_changed_configuration":false
}
```

This is a mutation and consumes ordinary caller/process mutation quota.

Execution creates a **new** immutable CONTROL run. It never rewrites the original. If the original run used a Collection, replay is bound to that exact historical Collection snapshot while current Collection HEAD is compared separately.

If the currently configured Council roster differs from the original committed roster, execution fails unless `allow_changed_configuration` is explicitly true.

```text
ORIGINAL_RUN != REPLAY_RUN
CURRENT_COLLECTION_HEAD != ORIGINAL_COLLECTION_SNAPSHOT
```

Replay queries current ORACLE evidence through the same read-only adapter:

```text
CURRENT_EVIDENCE != ORIGINAL_EVIDENCE
```

Phase 7 never sets `exact_replay_claimed=true` merely because execution succeeded.

### `control.replay.get`

Parameters:

```json
{"replay_id":"sha256:..."}
```

Returns the immutable content-addressed replay record plus its deterministic comparison report.

### `control.research.timeline`

Parameters:

```json
{
  "run_id":"sha256:...",
  "limit":100
}
```

Groups exact recurring questions by `question_sha256` and returns chronological runs plus adjacent-run transitions in evidence, Collection snapshot, Council roster/runtime, and model-state metadata.

```text
TIMELINE != TRUTH
CHANGE != IMPROVEMENT
```

See `docs/REPLAY.md` and `ai/replay-contract.json` for the full Phase 7 contract.

### Retrieval/index replay honesty

Current `control.ask` does not perform Collection search, so Phase 7 replay-basis receipts explicitly record its index status as `not_used`.

Pre-Phase-7 runs without a replay-basis receipt remain `not_recorded`.

```text
NOT_USED != NOT_RECORDED
LEGACY_MISSING_INDEX != INVENTED_INDEX
```

A future operation that actually consumes a search index as execution input must record the exact index descriptor before same-index re-execution can be claimed.

### Lattice memory

`control.memory.get` returns a bounded 27-cell logical-memory view.

`control.memory.trace` accepts a lattice address prefix plus optional run binding and explicit `max_runs` / `max_records` limits. It never infers importance, cognition, or truth from coordinates.

```text
LATTICE_ADDRESS != TRUTH
GEOMETRY != TRUTH
```

## Quotas and resource limits

The API enforces deterministic process-local budgets rather than time-window rate limits. Relevant ceilings include:

```text
request bytes                         8 MiB
response bytes                        8 MiB
File upload                           4 MiB
requests per caller / process         1000
mutating requests per caller/process  200
hard process requests                 1000
hard process mutations                200
model states per response             100
lattice records per response          1000
runs per lattice trace                100
research timeline runs                500
```

Caller IDs are request-supplied provenance and therefore cannot reset the hard process-wide ceilings.

Quotas are operational resource controls only. Remaining quota does not alter epistemic authority.

## Machine-readable errors

Failures use `qsol-control-agent-error/1` with one stable code:

```text
INVALID_JSON
INVALID_REQUEST
UNSUPPORTED_PROTOCOL
UNKNOWN_OPERATION
AUTHORITY_ESCALATION
RESOURCE_LIMIT
QUOTA_EXCEEDED
OPERATION_FAILED
```

Errors never upgrade missing evidence into a guess.

## Authority firewall

The request validator rejects machine-side attempts to inject synthetic truth scoring, epistemic privilege, ORACLE writes, WorldStore mutation, Council governance overrides, hidden/private reasoning, or credential-labelled controls.

Replay reuses the same firewall and underlying ORACLE/NEXUS/storage validators.

```text
CONTROL_CALL != ORACLE_AUTHORITY
CONTROL_CALL != NEXUS_GOVERNANCE
CONTROL_OPERATION != TRUTH
```

## Current phase boundary

Implemented through Phase 7:

- structured local machine API;
- classified replay;
- replay execution as a new run;
- deterministic replay reports;
- recurring-question timelines.

Still not implemented by this surface:

- remote multi-user deployment;
- ORACLE writes;
- direct NEXUS WorldStore mutation;
- hidden chain-of-thought capture;
- model-mind capture;
- automatic truth scoring;
- exact reconstruction of historical state that was never recorded.
