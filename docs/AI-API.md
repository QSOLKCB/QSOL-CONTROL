# QSOL-CONTROL AI / Agent API

## Status

Phase 6 is implemented as `qsol-control-agent-api/1`.

The first transport is dependency-free local JSONL over stdin/stdout. Operation semantics are transport-neutral; remote multi-user deployment remains deferred and is not implied by this implementation.

Canonical implementation and detailed protocol documentation:

```text
api/common.py
api/runtime.py
api/dispatcher.py
api/stdio.py
tools/agent_api.py
ai/agent-api-contract.json
schema/agent-api-request.schema.json
schema/agent-api-response.schema.json
docs/AGENT-API.md
```

## Principle

AI callers are clients, not privileged epistemic authorities.

```text
HUMAN_CALLER_AUTHORITY == AI_CALLER_AUTHORITY
API_ACCESS != EPISTEMIC_PRIVILEGE
```

A machine caller may request structured output. It may not bypass evidence, governance, storage, privacy, or provenance rules.

## Transport

Start the local machine interface with:

```bash
python3 tools/agent_api.py --root .qsol-control-store
```

One UTF-8 JSON request is read per line and one canonical JSON response is written per line.

The dispatcher reuses the same CONTROL storage, ORACLE adapter, NEXUS adapter, model-state registry, and lattice runtime as the Human WebUI. It is not a second implementation of those systems.

## Implemented operations

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

`control.replay` is intentionally absent. Actual replay execution remains Phase 7.

## Request envelope

```json
{
  "protocol": "qsol-control-agent-request/1",
  "request_id": "req-1",
  "caller": {
    "kind": "ai",
    "id": "research-agent"
  },
  "operation": "control.ask",
  "params": {
    "question": "Does the admitted evidence support hypothesis X?",
    "mode": "council"
  }
}
```

External caller kinds are `human` and `ai`. AI-originated runs retain `requester_kind: ai`; human-originated machine-API runs retain `requester_kind: human`. The label changes provenance, not authority.

## Response envelope

Successful calls use `qsol-control-agent-response/1`:

```json
{
  "protocol": "qsol-control-agent-response/1",
  "request_id": "req-1",
  "operation": "control.health",
  "ok": true,
  "result": {},
  "authority": "orchestration-only"
}
```

Failures use `qsol-control-agent-error/1` with a stable machine-readable error code.

## Error taxonomy

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

An unavailable parent service remains unavailable. It is never replaced by plausible local invention.

## Resource limits

Phase 6 uses deterministic process-local resource budgets:

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

Quotas are operational controls only. They do not affect epistemic status.

## Unknown handling

An `unknown` evidence result is valid output.

Suggested searches remain explicitly non-evidence:

```text
SUGGESTED_SEARCH != EVIDENCE
```

## Authority firewall

The API exposes no ORACLE write operations and no arbitrary NEXUS operation passthrough. It does not expose WorldStore creation, ballot mutation, vote-weight control, consensus-threshold control, hidden chain-of-thought, model-mind capture, or synthetic truth scoring.

```text
CONTROL_CALL != ORACLE_AUTHORITY
CONTROL_CALL != NEXUS_GOVERNANCE
VOTE != EVIDENCE
CONSENSUS != TRUTH
MODEL_STATE != MODEL_MIND
LATTICE_ADDRESS != TRUTH
```

See `docs/AGENT-API.md` for operation-by-operation behavior and exact limits.
