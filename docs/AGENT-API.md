# QSOL-CONTROL Phase 6 AI / Agent API

Phase 6 implements `qsol-control-agent-api/1` as a dependency-free structured machine interface over the same CONTROL runtime used by the Phase 5 Human WebUI.

The first transport is local JSONL over stdin/stdout:

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
    +--> lattice memory
```

Remote multi-user deployment is not implemented by Phase 6. The operation semantics are transport-neutral so a later hardened transport can reuse them without creating a second authority model.

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

`caller.id` exists for bounded process-local quota attribution and storage provenance. It does not create identity, truth, evidence, or governance authority.

## Operations

Phase 6 freezes these operations:

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
control.evidence.get
control.council.get
control.models.get
control.memory.get
control.memory.trace
```

### Health and capabilities

`control.health` returns CONTROL storage and configured parent availability without treating availability as truth.

`control.capabilities` returns the exact Phase 6 operation catalogue, limits, question modes, parent configuration, and negative capabilities such as `oracle_write_operations: []`.

### Ask

`control.ask` accepts the same bounded question modes as the WebUI:

```text
evidence_only
council
```

AI requests are persisted as `requester_kind: ai`; human machine-API requests are persisted as `requester_kind: human`. Both use the same ORACLE and NEXUS paths.

ORACLE remains read-only. Council invocation remains the existing verified `council.run` path. The API does not expose raw NEXUS operation passthrough, WorldStore mutation, vote weights, ballot overrides, or threshold overrides.

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

`control.run.compare` compares two runs without executing replay. Actual replay execution remains Phase 7.

`control.evidence.get` returns evidence state, ORACLE refs/events, and provenance sources as a separate view.

`control.council.get` returns externally visible Council response/receipt events and NEXUS object references. It does not expose hidden chain-of-thought.

`control.models.get` returns bounded model-state reproducibility metadata by run or exact state ID.

```text
VOTE != EVIDENCE
CONSENSUS != TRUTH
MODEL_STATE != MODEL_MIND
VISIBLE_OUTPUT != HIDDEN_CHAIN_OF_THOUGHT
```

### Lattice memory

`control.memory.get` returns a bounded 27-cell logical-memory view.

`control.memory.trace` accepts a lattice address prefix plus optional run binding and explicit `max_runs` / `max_records` limits. It never infers importance, cognition, or truth from coordinates.

```text
LATTICE_ADDRESS != TRUTH
GEOMETRY != TRUTH
```

## Quotas and resource limits

Phase 6 enforces deterministic process-local budgets rather than time-window rate limits:

```text
request bytes                         8 MiB
response bytes                        8 MiB
File upload                           4 MiB
requests per caller / process         1000
mutating requests per caller/process  200
model states per response             100
lattice records per response          1000
runs per lattice trace                100
```

Quotas are operational resource controls only. A higher or lower remaining quota does not alter epistemic authority.

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

The request validator recursively rejects machine-side attempts to inject fields for synthetic truth scoring, epistemic privilege, ORACLE writes, WorldStore mutation, Council governance overrides, hidden/private reasoning, or credential-labelled controls.

This is defence in depth. The underlying ORACLE/NEXUS/storage adapters still enforce their own contracts.

```text
CONTROL_CALL != ORACLE_AUTHORITY
CONTROL_CALL != NEXUS_GOVERNANCE
CONTROL_OPERATION != TRUTH
```

## Phase boundary

Phase 6 does not implement:

- Phase 7 replay execution;
- remote multi-user deployment;
- ORACLE writes;
- direct NEXUS WorldStore mutation;
- hidden chain-of-thought capture;
- model-mind capture;
- automatic truth scoring.
