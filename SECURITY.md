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

## Data classification

Before persistence or export, CONTROL data should be classified into one of these operational classes:

```text
PUBLIC      safe for deliberate public export
INTERNAL    operator-owned local state; not public by default
RESTRICTED  sensitive metadata requiring explicit access and export approval
FORBIDDEN   credentials, hidden chain-of-thought, or other material CONTROL must not retain
```

`FORBIDDEN` material must be rejected or redacted before persistence. A hash of forbidden plaintext is not a safe substitute for removing the plaintext when the hash itself could disclose a sensitive identifier or permit guessing attacks.

## Redaction policy

Redaction happens **before** durable storage, content hashing, lattice placement, export, screenshots, or ordinary logs whenever the sensitive value is not required for reproducibility.

At minimum, redact or omit:

- API keys, bearer tokens, cookies, OAuth refresh/access tokens and session identifiers;
- authorization headers and secret environment variables;
- account/billing identifiers not required for the research record;
- email addresses, usernames, hostnames, filesystem paths, IP addresses or device identifiers when they are incidental rather than reproducibility-critical;
- command-line arguments containing credentials;
- provider request IDs that are account-linkable unless explicitly required and reviewed;
- unreviewed free-form metadata copied from provider responses.

Prefer coarse reproducibility metadata such as `accelerator_class = RTX-50-series` over unnecessary machine serial numbers or host fingerprints.

Redaction must be explicit and inspectable. Do not silently replace sensitive material with invented values that could later be mistaken for source data.

## Access-control policy

Phase 0 defines contracts only; it does not claim a deployed access-control system. A future runtime must fail closed and should default to a **single local operator on loopback**.

Any remote or multi-user deployment must define and test:

- authentication;
- authorization by operation and record class;
- least-privilege access to `INTERNAL` and `RESTRICTED` records;
- separation between read/query operations and authority-sensitive writes;
- audit records for export, deletion, retention-class changes and privileged operations;
- session expiry and credential rotation.

AI callers do not become administrators merely because they are machine clients.

## Retention policy

CONTROL exists partly to preserve research history, but **retention must be intentional rather than accidental**.

Future runtime records should carry or inherit a retention decision equivalent to:

```text
TRANSIENT  process only; do not persist after the operation
SESSION    retain for the bounded operator session/workspace
ARCHIVE    intentionally preserve for longitudinal research/recovery
```

Recommended defaults:

- credentials and `FORBIDDEN` material: never persist;
- incidental transport/debug data: `TRANSIENT`;
- unreviewed operator queries or model-state metadata: no stronger than `SESSION` by default;
- curated research records: `ARCHIVE` only after classification/redaction succeeds;
- public ARK/export bundles: contain only material explicitly cleared for that export surface.

Changing a record from `TRANSIENT` or `SESSION` to `ARCHIVE` is a publication/retention decision, not a side effect of successful execution.

Deletion or expiry policy must not rewrite ORACLE history or pretend an absent CONTROL copy means the underlying witnessed event never existed.

## Model-state privacy

Model-state capture must be minimized to reproducibility/recovery metadata. Do not record credentials, private provider account details, hidden prompts not intended for preservation, or hidden chain-of-thought.

Model-state fields should prefer allowlisted structured metadata over arbitrary provider-response blobs. Hardware/user environment details should be scoped to what materially supports reproducibility and should be reviewable before export.

Fields may contain sensitive identifiers even when they look technical. In particular, review provider request IDs, workspace IDs, model endpoints, local paths, usernames, IP addresses, machine names and tool configuration before persistence.

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
- recursive-address depth limits;
- classification/redaction status before archival persistence.

Recursive lattice addressing must not permit unbounded recursion or resource exhaustion.

## Replay boundary

A replay label is a technical claim and must be earned.

Live stochastic inference must not be labelled exact replay merely because the same model name and prompt were used again.

## Secret scanning and fixture discipline

Examples and tests must use obviously synthetic placeholders, never copied production credentials or private provider payloads. CI should remain safe to run on forks and public runners.

Before release or public export, scan tracked content and generated bundles for common credential patterns and review any detected high-entropy or account-linked values.

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
FORBIDDEN_DATA != ARCHIVAL_MATERIAL
ARCHIVE_REQUIRES_CLASSIFICATION_AND_REDACTION
```

## Reporting

For security-sensitive changes, include the affected boundary, threat, mitigation, residual risk, and regression coverage in the pull request description.
