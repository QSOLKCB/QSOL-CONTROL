# QSOL-CONTROL Security

QSOL-CONTROL is a control plane. Its most important security property is **authority containment**.

A compromised display must not become a compromised ORACLE ledger. A malicious model response must not become a NEXUS command. A stored File, Collection membership, search hit, vector similarity, or DNA projection must not become trusted evidence merely because it survived disk I/O.

## Trust boundaries

Treat as untrusted by default:

- browser input;
- AI/agent API requests;
- model output;
- File uploads/imports;
- Collection metadata;
- semantic vectors supplied by external adapters;
- imported interaction/recovery bundles;
- external source payloads;
- ORACLE/NEXUS transport payloads until validated against their protocol contracts;
- filenames, archive paths, content types, source locators and user-supplied metadata.

## Credentials

Credentials are operational secrets, not lattice memory, Files, Collections or model state.

Credentials must never intentionally enter:

- questions sent to models;
- Council prompts;
- persistent File content intended for archival storage;
- File/Collection metadata;
- search indexes or embedding descriptors;
- DNA/lattice recovery projections;
- model-state records;
- interaction records;
- ORACLE evidence;
- replay bundles;
- screenshots/browser exports;
- ordinary logs.

Prefer references to external secret stores rather than copying secret values into CONTROL state.

## Data classification

Before persistence or export, classify CONTROL data as:

```text
PUBLIC      safe for deliberate public export
INTERNAL    operator-owned local state; not public by default
RESTRICTED  sensitive metadata/content requiring explicit access/export approval
FORBIDDEN   credentials, hidden chain-of-thought, or material CONTROL must not retain
```

`FORBIDDEN` material must be rejected or redacted before persistence.

A hash of forbidden plaintext is not automatically safe: hashes can disclose sensitive identifiers or permit guessing attacks when the input space is small.

## Monotonic Collection privacy

Phase 1 enforces this ordering:

```text
PUBLIC < INTERNAL < RESTRICTED
```

A Collection may be equally or **more restrictive** than its member Files; it may never make a File less restricted.

Therefore:

```text
PUBLIC Collection     -> PUBLIC Files only
INTERNAL Collection   -> PUBLIC or INTERNAL Files
RESTRICTED Collection -> PUBLIC, INTERNAL or RESTRICTED Files
```

This rule is checked during Collection updates and again during store verification.

```text
COLLECTION_MEMBERSHIP != DECLASSIFICATION
```

## Search-index confidentiality

Lexical indexes and semantic vectors are derived, but derived data can still leak source content.

Examples:

- term-frequency maps reveal vocabulary;
- embeddings can encode sensitive semantic information;
- nearest-neighbour outputs reveal Collection membership and relationships;
- embedding descriptors may expose provider/workspace identifiers.

Search indexes therefore inherit the access/export restrictions of the Collection snapshot from which they were built.

```text
DERIVED != PUBLIC
VECTOR != SAFE_TO_DISCLOSE
SEARCHABLE != AUTHORITATIVE
```

A future multi-user runtime must authorize search operations against Collection privacy, not merely hide raw File download buttons.

## DNA/lattice projection confidentiality

The `A/C/G/T` projection is reversible. Anyone with the full projection can reconstruct the source bytes.

Encoding data into DNA symbols does **not** redact, anonymize, encrypt or declassify it.

```text
ENCODED != ENCRYPTED
ENCODED != REDACTED
DNA_PROJECTION_INHERITS_SOURCE_PRIVACY
```

A `RESTRICTED` File remains restricted when represented as codons or distributed over 27 lattice cells.

The φ-gated traversal is an addressing order only and provides no security property.

## Redaction policy

Redaction happens **before** durable storage, content hashing, lattice placement, embedding generation, DNA export, screenshots or ordinary logs whenever the sensitive value is not required for reproducibility.

At minimum, redact or omit:

- API keys, bearer tokens, cookies, OAuth refresh/access tokens and session identifiers;
- authorization headers and secret environment variables;
- account/billing identifiers not required for the research record;
- email addresses, usernames, hostnames, filesystem paths, IP addresses or device identifiers when incidental;
- command-line arguments containing credentials;
- provider request IDs that are account-linkable unless explicitly required and reviewed;
- unreviewed free-form metadata copied from provider responses.

Prefer coarse reproducibility metadata such as `accelerator_class = RTX-50-series` over unnecessary machine serial numbers or host fingerprints.

Redaction must be explicit and inspectable. Do not silently replace sensitive material with invented values that could later be mistaken for source data.

## Access-control policy

Phase 1 implements a local filesystem storage core but **does not claim a deployed authentication/authorization system**.

The intended default remains a single local operator. A future WebUI/service should bind to loopback unless a later threat model explicitly supports remote operation.

Any remote or multi-user deployment must define and test:

- authentication;
- authorization by operation and record class;
- least-privilege access to `INTERNAL` and `RESTRICTED` records;
- Collection-aware search authorization;
- separation between read/query operations and authority-sensitive writes;
- audit records for export, deletion, retention-class changes and privileged operations;
- session expiry and credential rotation.

AI callers do not become administrators merely because they are machine clients.

## Retention policy

CONTROL exists partly to preserve research history, but **retention must be intentional rather than accidental**.

Records carry one of:

```text
TRANSIENT  process only / intended short-lived lifecycle
SESSION    bounded operator session/workspace
ARCHIVE    intentionally preserved for longitudinal research/recovery
```

Important Phase-1 limitation: these labels are persisted as policy metadata; automatic expiry/garbage collection is **not yet implemented**. Do not interpret a `TRANSIENT` label as proof that bytes have already been deleted.

Recommended defaults:

- credentials and `FORBIDDEN` material: never persist;
- incidental transport/debug data: `TRANSIENT`;
- unreviewed operator queries/model-state metadata: no stronger than `SESSION` by default;
- curated research records: `ARCHIVE` only after classification/redaction succeeds;
- public ARK/export bundles: only material explicitly cleared for that export surface.

Changing data from `TRANSIENT`/`SESSION` to `ARCHIVE` is a retention decision, not a side effect of successful execution.

Deletion/expiry must not rewrite ORACLE history or imply an underlying witnessed event never existed.

## Model-state privacy

Model-state capture must be minimized to reproducibility/recovery metadata. Do not record credentials, private provider account details, hidden prompts not intended for preservation, or hidden chain-of-thought.

Prefer allowlisted structured metadata over arbitrary provider-response blobs. Review provider request IDs, workspace IDs, endpoints, local paths, usernames, IP addresses, machine names and tool configuration before persistence.

## Browser/WebUI boundary

When the WebUI is implemented, review at minimum:

- CSRF protection;
- CORS policy;
- session/cookie scope;
- websocket/event-stream authorization;
- content-security policy;
- output escaping;
- untrusted Markdown/HTML rendering;
- download/import handling;
- clickjacking/framing behavior;
- rate/resource limits.

Remote or multi-user deployment must not be inferred merely from the existence of a WebUI.

## AI/agent API boundary

Machine callers are not trusted administrators merely because they can speak JSON.

The AI interface must not expose hidden operations that can:

- modify NEXUS ballots or vote weights;
- rewrite ORACLE history;
- elevate stored/search-retrieved content to canonical evidence;
- bypass caller authorization;
- access credentials;
- request hidden chain-of-thought.

## NEXUS boundary

CONTROL should discover supported NEXUS operations and use reviewed public interfaces. Model output remains untrusted data.

CONTROL must not convert free-form model text into executable CONTROL operations without explicit validation and authorization.

## ORACLE boundary

The default ORACLE adapter should be read/query oriented. Any future write/append path requires separate review because witnessing is authority-sensitive even when semantic authority remains limited.

A hash match proves integrity of hashed bytes, not authorship or truth.

## Persistent storage boundary

The storage core must validate:

- canonical IDs;
- object byte hashes and sizes;
- record schemas;
- path confinement through content IDs;
- immutable Collection descriptor/snapshot identities;
- snapshot revision continuity and lineage loops;
- Collection-member privacy monotonicity;
- duplicate identity behavior;
- atomic pointer/write behavior;
- import provenance;
- maximum future record/bundle sizes;
- classification/redaction before archival persistence.

Recursive lattice addressing and imported recovery data must not permit unbounded recursion or resource exhaustion.

## Replay boundary

A replay label is a technical claim and must be earned.

Live stochastic inference must not be labelled exact replay merely because the same model name and prompt were used again.

A future replay involving Collections must record the exact historical Collection snapshot rather than silently using current membership.

## Secret scanning and fixtures

Examples/tests must use synthetic placeholders, never copied production credentials or private provider payloads. CI should remain safe on forks/public runners.

Before release/public export, scan tracked content and generated bundles for common credential patterns and review detected high-entropy/account-linked values.

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
COLLECTION_MEMBERSHIP != DECLASSIFICATION
DERIVED_INDEX != PUBLIC_DATA
ENCODED != ENCRYPTED
DNA_PROJECTION_INHERITS_SOURCE_PRIVACY
```

## Reporting

For security-sensitive changes, include the affected boundary, threat, mitigation, residual risk, and regression coverage in the pull request description.
