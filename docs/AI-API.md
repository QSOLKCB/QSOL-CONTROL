# QSOL-CONTROL AI / Agent API

## Status

This document defines the target machine interface for future runtime implementation. PR #1 does not claim that a network API already exists.

## Principle

AI callers are clients, not privileged epistemic authorities.

```text
HUMAN_CALLER_AUTHORITY == AI_CALLER_AUTHORITY
```

A machine caller may ask for more structured output. It may not bypass evidence, governance, or storage rules.

## Transport

Transport is intentionally deferred. Candidate implementations may include local JSONL/stdin-stdout, loopback HTTP, or an MCP-compatible adapter, but the operation contract should remain transport-neutral.

## Core operations

```text
control.health
control.capabilities
control.ask
control.run.get
control.run.compare
control.evidence.get
control.council.get
control.models.get
control.memory.get
control.memory.trace
control.replay
```

## `control.ask`

Conceptual request:

```json
{
  "operation": "control.ask",
  "question": "Does the admitted evidence support hypothesis X?",
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

`mode` is one of:

```text
evidence_only
council
```

## Conceptual response envelope

```json
{
  "protocol": "QSOL-CONTROL/0.1",
  "run_id": "sha256:...",
  "question": "...",
  "mode": "council",
  "evidence": {
    "state": "known|conflict|unknown",
    "refs": []
  },
  "council": {
    "status": "completed|unavailable|not_requested",
    "roster": [],
    "votes": [],
    "consensus": null,
    "minority_reports": []
  },
  "receipts": [],
  "model_state_refs": [],
  "lattice_refs": [],
  "replayability": "R0|R1|R2|R3"
}
```

Exact runtime fields remain schema/version controlled when implementation begins.

## Error philosophy

Errors should be typed and useful. Examples:

```text
unsupported_operation
invalid_request
oracle_unavailable
nexus_unavailable
evidence_unavailable
storage_unavailable
schema_mismatch
version_mismatch
authorization_denied
resource_limit
```

Do not replace an unavailable parent service with invented local output unless the caller explicitly requests a labelled simulation mode defined by a future protocol.

## Unknown handling

An `unknown` evidence result is valid output.

The API may return bounded `suggested_searches`, but it must retain:

```json
{"search_suggestions_are_evidence": false}
```

or an equivalent versioned invariant.

## Security

Machine input is untrusted. Future runtime implementations must bound:

- question size;
- include-list size;
- recursion depth;
- memory traversal breadth;
- run comparison cardinality;
- imported payload size;
- concurrency;
- model/Council resource use.

API access must not imply credential access or administrative authority.
