# QSOL-CONTROL Security

QSOL-CONTROL is a control plane. That makes its most important security property **authority containment**.

A compromised display should not become a compromised ORACLE ledger. A malicious AI response should not become a NEXUS command. A stored interaction should not become trusted evidence merely because it survived disk I/O.

## Trust boundaries

Treat as untrusted by default:

- browser input;
- AI/agent API requests;
- model output;
- imported interaction bundles;
- external source payloads;
- ORACLE/NEXUS transport payloads until validated against their protocol contracts;
- filenames, archive paths, content types, and user-supplied metadata.

## Credentials

Credentials are operational secrets, not lattice memory and not model state.

Credentials must never intentionally enter:

- questions sent to models;
- Council prompts;
- model-state records;
- interaction records;
- ORACLE evidence;
- replay bundles;
- screenshots or browser-export artifacts;
- ordinary logs.

Future runtime work should prefer references to external secret sources rather than copying secret values into CONTROL state.

## Browser/WebUI boundary

When the WebUI is implemented, the default operator deployment should prefer local/loopback binding unless a later threat model explicitly supports remote operation.

Remote or multi-user deployment must not be inferred from the existence of a WebUI.

Future implementation must review:

- CSRF protection;
- CORS policy;
- session/cookie scope;
- websocket/event-stream authorization if used;
- content-security policy;
- output escaping;
- untrusted Markdown/HTML rendering;
- download/import handling;
- clickjacking and framing behavior;
- rate/resource limits.

## AI/agent API boundary

Machine callers are not trusted administrators merely because they can speak JSON.

The AI interface must not expose hidden operations that can:

- modify NEXUS ballots or vote weights;
- rewrite ORACLE history;
- elevate stored content to canonical evidence;
- bypass caller authorization;
- access credentials;
- request hidden chain-of-thought.

## NEXUS boundary

CONTROL should discover supported NEXUS operations and use reviewed public interfaces. Model output remains untrusted data.

CONTROL must not convert free-form model text into executable CONTROL operations without explicit validation and authorization.

## ORACLE boundary

The default ORACLE adapter should be read/query oriented. Any future write/append path requires separate review because witnessing is authority-sensitive even when semantic authority remains limited.

A hash match proves integrity of the hashed bytes, not authorship or truth.

## Storage boundary

The lattice datastore must validate:

- canonical IDs;
- record schemas;
- path confinement;
- maximum record/bundle sizes;
- lineage references;
- duplicate identity behavior;
- atomic write behavior;
- import provenance;
- recursive-address depth limits.

Recursive lattice addressing must not permit unbounded recursion or resource exhaustion.

## Model-state privacy

Model-state capture should be minimized to reproducibility/recovery metadata. Do not record credentials, private provider account details, hidden prompts not intended for preservation, or hidden chain-of-thought.

Hardware/user environment details should be scoped to what materially supports reproducibility and should be reviewable before export.

## Replay boundary

A replay label is a technical claim and must be earned.

Live stochastic inference must not be labelled exact replay merely because the same model name and prompt were used again.

## Security invariants

```text
MODEL_OUTPUT = UNTRUSTED_INPUT
CREDENTIALS != COGNITIVE_STATE
STORED != TRUSTED
HASH_MATCH != TRUTH
UI_ACTION != AUTHORITY_ESCALATION
AI_CALLER != ADMIN_BY_DEFAULT
REPLAY_LABEL_REQUIRES_EVIDENCE
HIDDEN_CHAIN_OF_THOUGHT = OUT_OF_SCOPE
```

## Reporting

For security-sensitive changes, include the affected boundary, threat, mitigation, residual risk, and regression coverage in the pull request description.
