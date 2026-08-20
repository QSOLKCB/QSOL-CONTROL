# QSOL-CONTROL Security

QSOL-CONTROL is a control plane. Its most important security property is **authority containment**.

A compromised display must not become a compromised ORACLE ledger. A malicious model response must not become a NEXUS command. A stored File, Collection membership, search hit, replay difference, vector similarity, or DNA projection must not become trusted evidence merely because it survived disk I/O.

## Trust boundaries

Treat as untrusted by default:

- browser input;
- AI/agent API requests;
- replay execution requests and changed-configuration acknowledgements;
- model output;
- File uploads/imports;
- Collection metadata;
- semantic vectors supplied by external adapters;
- imported interaction/recovery bundles;
- external source payloads;
- ORACLE/NEXUS transport payloads until validated against their protocol contracts;
- filenames, archive paths, content types, source locators and user-supplied metadata.

## Credentials

Credentials are operational secrets, not lattice memory, Files, Collections, replay state, or model state.

Credentials must never intentionally enter questions, Council prompts, persistent archival content/metadata, search descriptors, replay basis/reports, DNA projections, model-state records, interaction records, ORACLE evidence, screenshots/browser exports, or ordinary logs.

Prefer references to external secret stores rather than copying secret values into CONTROL state.

## Data classification

```text
PUBLIC      safe for deliberate public export
INTERNAL    operator-owned local state; not public by default
RESTRICTED  sensitive metadata/content requiring explicit access/export approval
FORBIDDEN   credentials, hidden chain-of-thought, or material CONTROL must not retain
```

`FORBIDDEN` material must be rejected or redacted before persistence. Hashing forbidden plaintext does not automatically make it safe.

## Monotonic Collection privacy

```text
PUBLIC < INTERNAL < RESTRICTED
```

A Collection may be equally or more restrictive than its member Files; it may never make a File less restricted.

```text
COLLECTION_MEMBERSHIP != DECLASSIFICATION
```

Replay binding to a historical Collection snapshot does not bypass the underlying File/Collection privacy classification. Phase 7 is not an archival-access backdoor.

## Search-index confidentiality

Lexical indexes and semantic vectors are derived but may leak source content. They inherit the access/export restrictions of the Collection snapshot from which they were built.

```text
DERIVED != PUBLIC
VECTOR != SAFE_TO_DISCLOSE
SEARCHABLE != AUTHORITATIVE
```

Phase 7 must not infer that an index was used merely because an index exists. If exact index use was not recorded, replay metadata remains `not_recorded`.

## DNA/lattice projection confidentiality

The `A/C/G/T` projection is reversible. Encoding data into DNA symbols does not redact, anonymize, encrypt, or declassify it.

```text
ENCODED != ENCRYPTED
ENCODED != REDACTED
DNA_PROJECTION_INHERITS_SOURCE_PRIVACY
```

## Redaction policy

Redaction happens before durable storage, content hashing, lattice placement, embedding generation, replay metadata capture, DNA export, screenshots, or ordinary logs whenever the sensitive value is not required for reproducibility.

At minimum, redact or omit credentials, tokens, cookies, secret environment variables, incidental account/billing identifiers, unnecessary host/user/path/IP identifiers, credential-bearing command arguments, account-linkable provider request IDs unless explicitly required, and unreviewed arbitrary provider-response metadata.

Redaction must be explicit and inspectable. Do not silently replace sensitive material with invented values that could later be mistaken for source data.

## Access-control policy

CONTROL implements local operator interfaces but does **not** claim a deployed remote multi-user authentication/authorization system.

The Phase 5 WebUI binds to loopback. The Phase 6/7 agent API uses local stdin/stdout and does not open a network listener.

Any remote or multi-user deployment must separately define authentication, authorization by operation/record class, least privilege for INTERNAL/RESTRICTED material, Collection-aware search/replay authorization, privileged audit records, session expiry, and credential rotation.

AI callers do not become administrators merely because they are machine clients.

## Retention policy

Records carry one of:

```text
TRANSIENT
SESSION
ARCHIVE
```

Automatic expiry/garbage collection is not yet implemented. Replay records and deterministic reports are durable research artifacts once created; their existence must not silently upgrade the retention class or public-export eligibility of referenced source material.

## Model-state privacy

Model-state capture must be minimized to reproducibility/recovery metadata. Do not record credentials, private provider account details, hidden prompts not intended for preservation, or hidden chain-of-thought.

Phase 7 compares model-state metadata but never treats a model-state comparison as a mind/personality comparison.

```text
MODEL_STATE != MODEL_MIND
MODEL_STATE_COMPARISON != MIND_COMPARISON
```

## Browser/WebUI boundary

The implemented WebUI uses:

- loopback only;
- unpredictable per-process session token;
- no CORS;
- non-loopback Host rejection;
- same-origin checks for state-changing requests when Origin is supplied;
- Content Security Policy;
- output rendering through DOM `textContent` rather than untrusted `innerHTML`;
- framing restrictions;
- `no-store` caching.

Phase 7 replay execution uses POST and inherits the same mutation boundary. Replay classification, replay lookup, and research timelines are read-only routes after token authentication.

Remote/multi-user deployment remains outside the implemented threat model.

## AI/agent API boundary

The structured machine interface remains bounded local JSONL/stdin-stdout. Machine callers are not trusted administrators merely because they can speak JSON.

The API enforces request/response/File/cardinality limits, caller quotas plus non-spoofable process-wide ceilings, duplicate-member rejection, strict JSON constants, operation-specific parameter whitelists, and typed errors.

```text
QUOTA != AUTHORITY
HUMAN_CALLER_AUTHORITY == AI_CALLER_AUTHORITY
API_ACCESS != EPISTEMIC_PRIVILEGE
```

Replay execution is a mutation and consumes the same mutation quota. The Phase 7 operations do not add ORACLE writes, generic NEXUS passthrough, WorldStore mutation, vote controls, threshold controls, hidden reasoning, credential access, or synthetic truth scoring.

## NEXUS boundary

CONTROL discovers supported NEXUS operations and uses reviewed public interfaces. The only governance-bearing path remains the adapter's `council.run` operation.

Replay does not recover or reapply old ballots. It asks the current configured Council to run under the current live NEXUS contract, after classification. If the configured roster identity differs from the original committed roster, explicit changed-configuration authorization is required.

```text
CONTROL_INVOKES_COUNCIL != CONTROL_OWNS_COUNCIL
CONSENSUS != TRUTH
VOTE != EVIDENCE
```

## ORACLE boundary

The ORACLE adapter remains read-only. Replay current-evidence queries use the same read-only adapter and preserve `unknown`/unavailable states.

```text
CURRENT_EVIDENCE != ORIGINAL_EVIDENCE
FRESH != TRUE
STALE != FALSE
```

Replay must never append, rewrite, relabel, or manufacture ORACLE history.

## Persistent storage boundary

The storage core validates canonical IDs, object hashes/sizes, record schemas, path confinement, immutable Collection identities, snapshot continuity, privacy monotonicity, duplicate identities, atomic writes, provenance, size limits, and classification/redaction requirements.

Phase 7 adds content-addressed replay records/reports under separate paths. Reads require canonical JSON bytes and content-derived identities.

## Replay boundary

A replay label is a technical reproducibility claim and must be earned.

### Threat: rewriting the original

Mitigation: replay creates a new run. CONTROL hashes the original run, event chain, and bound model-state records before and after execution. Any change fails the operation.

```text
ORIGINAL_RUN != REPLAY_RUN
ORIGINAL_RESULT_IMMUTABLE = true
```

### Threat: silently using current Collection membership

Mitigation: replay passes the original exact Collection snapshot back into the normal ask path. Current HEAD is read only for comparison.

```text
REPLAY_COLLECTION_SNAPSHOT = ORIGINAL_COLLECTION_SNAPSHOT
CURRENT_COLLECTION_HEAD != ORIGINAL_COLLECTION_SNAPSHOT
```

### Threat: inventing historical index state

Mitigation: current `control.ask` records index status `not_used`. Pre-Phase-7 runs without replay-basis metadata use `not_recorded`. The runtime does not infer historical index use from present indexes.

```text
NOT_USED != NOT_RECORDED
LEGACY_MISSING_INDEX != INVENTED_INDEX
```

### Threat: silently accepting Council drift

Mitigation: original committed roster identity is compared with the current configured roster. A changed roster requires explicit `allow_changed_configuration` authorization before replay.

### Threat: claiming stochastic rerun as exact

Mitigation: replay classification inspects recorded replayability/model state/NEXUS replayability and never sets `exact_replay_claimed=true` in the Phase 7 protocol.

### Threat: treating current evidence as historical evidence

Mitigation: deterministic reports keep original and replay evidence sets separate and explicitly state `current_evidence_is_original_evidence=false`.

### Threat: replay difference becomes truth score

Mitigation: comparison lanes stay separate. Reports and timelines pin `comparison_is_truth=false` / `timeline_is_truth=false` and produce no aggregate truth/fidelity percentage.

## Longitudinal timeline boundary

Research timelines group exact question identities by `question_sha256`. They describe recorded changes; they do not establish causality, improvement, or truth.

```text
TIMELINE != TRUTH
CHANGE != IMPROVEMENT
CONSENSUS_CHANGE != EVIDENCE_CHANGE
```

The timeline scan is bounded to the local CONTROL store and a maximum returned run count.

## Secret scanning and fixtures

Examples/tests must use synthetic placeholders, never copied production credentials or private provider payloads. CI must remain safe on public runners.

Before release/public export, scan tracked content and generated bundles for credential patterns and review high-entropy/account-linked values.

## Security invariants

```text
MODEL_OUTPUT = UNTRUSTED_INPUT
CREDENTIALS != COGNITIVE_STATE
STORED != TRUSTED
HASH_MATCH != TRUTH
UI_ACTION != AUTHORITY_ESCALATION
AI_CALLER != ADMIN_BY_DEFAULT
HUMAN_CALLER_AUTHORITY == AI_CALLER_AUTHORITY
API_ACCESS != EPISTEMIC_PRIVILEGE
CONTROL_CALL != ORACLE_AUTHORITY
CONTROL_CALL != NEXUS_GOVERNANCE
QUOTA != AUTHORITY
ORIGINAL_RUN != REPLAY_RUN
CURRENT_EVIDENCE != ORIGINAL_EVIDENCE
CURRENT_COLLECTION_HEAD != ORIGINAL_COLLECTION_SNAPSHOT
LEGACY_MISSING_INDEX != INVENTED_INDEX
REPLAY_CLASSIFICATION != TRUTH
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
