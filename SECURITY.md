# QSOL-CONTROL Security

QSOL-CONTROL is a control plane. Its most important security property is **authority containment**.

A compromised display must not become a compromised ORACLE ledger. A malicious model response must not become a NEXUS command. A stored File, Collection membership, search hit, replay difference, vector similarity, DNA projection, migration receipt, compatibility receipt, or release hash must not become trusted evidence merely because it survived disk I/O.

The detailed Phase 10 network/browser analysis is in [`docs/THREAT-MODEL.md`](docs/THREAT-MODEL.md).

## Trust boundaries

Treat as untrusted by default:

- browser input;
- AI/agent API requests;
- replay execution requests and changed-configuration acknowledgements;
- model output;
- File uploads/imports and persisted File/Collection metadata;
- semantic vectors supplied by external adapters;
- imported interaction/recovery bundles;
- external source payloads;
- ORACLE/NEXUS transport payloads until validated against their contracts;
- filenames, archive paths, archive members, content types, source locators and user-supplied metadata;
- current-parent observations supplied to composition drift checks;
- migration/release inputs and generated manifests until validated.

## Credentials

Credentials are operational secrets, not lattice memory, Files, Collections, replay state, model state, migration state, or release metadata.

Credentials must never intentionally enter questions, Council prompts, persistent archival content/metadata, search descriptors, replay basis/reports, DNA projections, model-state records, interaction records, ORACLE evidence, screenshots/browser exports, release bundles, migration receipts, or ordinary logs.

Prefer references to external secret stores rather than copying secret values into CONTROL state.

Phase 10 preserves write-time secret-marker rejection and adds `tools/file_metadata_audit.py` for read/import-side auditing. The audit rejects credential-labelled keys, high-confidence credential markers, credential-bearing locators, duplicate JSON members, malformed File identities, and rehashed hostile records. It fails closed rather than silently redacting canonical history.

## Data classification

```text
PUBLIC      safe for deliberate public export
INTERNAL    operator-owned local state; not public by default
RESTRICTED  sensitive metadata/content requiring explicit access/export approval
FORBIDDEN   credentials, hidden chain-of-thought, or material CONTROL must not retain
```

`FORBIDDEN` material must be rejected before persistence. Hashing forbidden plaintext does not make it safe.

```text
PUBLIC < INTERNAL < RESTRICTED
COLLECTION_MEMBERSHIP != DECLASSIFICATION
```

A Collection may be equally or more restrictive than its member Files; it may never make a File less restricted. Replay/recovery do not bypass privacy classification.

## Derived-data confidentiality

Lexical indexes, semantic vectors, DNA/lattice projections, compatibility reports, and release inventories are derived artifacts and may leak source information. Derived does not mean public.

```text
DERIVED != PUBLIC
VECTOR != SAFE_TO_DISCLOSE
SEARCHABLE != AUTHORITATIVE
ENCODED != ENCRYPTED
ENCODED != REDACTED
DNA_PROJECTION_INHERITS_SOURCE_PRIVACY
```

## Browser/WebUI boundary

The implemented WebUI uses:

- loopback-only binds;
- unpredictable per-process session token;
- no CORS;
- non-loopback `Host` rejection;
- same-origin checks for state-changing requests when `Origin` is supplied;
- Content Security Policy and framing restrictions;
- DOM `textContent` rather than untrusted `innerHTML`;
- `no-store` caching.

Phase 7 replay execution is a POST mutation and inherits the same boundary.

Phase 10 explicitly threat-models this **local** surface. It does not claim that loopback/session-token mechanics become internet-facing authentication if an operator adds a reverse proxy, tunnel, port-forward, or remote bind.

```text
LOOPBACK != REMOTE_AUTH
SESSION_TOKEN != MULTI_USER_AUTHORIZATION
REMOTE_MULTI_USER_DEPLOYMENT = false
```

Remote/multi-user deployment remains deferred and would require separate authentication, authorization, TLS/transport, session lifecycle, record-class ACL, audit, and credential-rotation policy.

## AI/agent API boundary

The machine interface remains bounded local JSONL/stdin-stdout and opens no network listener. It enforces request/response/File/cardinality limits, caller quotas plus process-wide ceilings, duplicate-member rejection, strict JSON constants, operation-specific parameter whitelists, and typed errors.

```text
QUOTA != AUTHORITY
HUMAN_CALLER_AUTHORITY == AI_CALLER_AUTHORITY
API_ACCESS != EPISTEMIC_PRIVILEGE
```

## ORACLE and NEXUS boundaries

The ORACLE adapter remains read-only. CONTROL must never append, rewrite, relabel, or manufacture ORACLE history.

The NEXUS adapter exposes reviewed Council invocation rather than generic governance passthrough. CONTROL cannot override ballots, vote weights, roster authority, thresholds, or WorldStore history.

```text
CONTROL_CALL != ORACLE_AUTHORITY
CONTROL_CALL != NEXUS_GOVERNANCE
CONTROL_INVOKES_COUNCIL != CONTROL_OWNS_COUNCIL
CONSENSUS != TRUTH
VOTE != EVIDENCE
```

## Persistent storage and replay boundary

The storage core validates content identities, object hashes/sizes, schemas, path confinement, immutable Collection identities, snapshot continuity, privacy monotonicity, duplicate identities, atomic writes, provenance, and size limits.

Replay creates a new run and never rewrites the original. It binds to the original Collection snapshot, compares current evidence separately, and never invents unrecorded historical index state.

```text
ORIGINAL_RUN != REPLAY_RUN
ORIGINAL_RESULT_IMMUTABLE = true
CURRENT_EVIDENCE != ORIGINAL_EVIDENCE
CURRENT_COLLECTION_HEAD != ORIGINAL_COLLECTION_SNAPSHOT
LEGACY_MISSING_INDEX != INVENTED_INDEX
REPLAY_CLASSIFICATION != TRUTH
```

Research timelines describe recorded changes; they do not establish causality, improvement, or truth.

## Archive and decompression boundary

Compressed untrusted archive input is **default-deny**.

The Phase 10 release verifier uses `storage/archive_safety.py` and accepts only bounded `ZIP_STORED` members. Before member payload reads it bounds the archive file, member count, per-member bytes, and aggregate bytes. It rejects traversal, duplicate members, symlink members, directories, and any compression method other than `ZIP_STORED`.

Release verification performs no extraction and no decompression. Existing portable-CONCAP ZIP support remains an export format; CONTROL does not silently acquire a generic ZIP import path.

```text
COMPRESSED_UNTRUSTED_INPUT != ACCEPTED_BY_DEFAULT
ARCHIVE_VERIFY != ARCHIVE_EXECUTE
```

A future compressed import path requires a separately reviewed bounded decoder.

## Migration boundary

`qsol-control-migration/1` is procedural compatibility machinery, not a semantic rewrite engine.

- source versions and steps are explicitly declared;
- downgrades fail closed;
- unknown majors fail closed;
- undeclared same-major versions are not guessed compatible;
- source state is preserved;
- in-place canonical rewrites are forbidden by the current policy;
- receipts are content-addressed and authority-free beyond procedure/integrity.

```text
MIGRATION != REINTERPRETATION
MIGRATION_RECEIPT != SEMANTIC_AUTHORITY
SOURCE_STATE != MUTATED_IN_PLACE
UNKNOWN_MAJOR != ASSUMED_COMPATIBLE
```

## Release boundary

`qsol-control-release-bundle/1` builds deterministic source archives from an explicit inventory. Every included source file has SHA-256 identity; `RELEASE.json` also binds the deterministic source-tree SHA-256, declared source commit, and release version.

A release bundle proves the integrity/reproducibility of the declared bytes only.

```text
RELEASE_BUNDLE != PUBLICATION_AUTHORITY
RELEASE_HASH != SEMANTIC_TRUTH
REPRODUCIBLE_BYTES != REPRODUCIBLE_LIVE_INFERENCE
MERGED_MAIN != PUBLISHED_RELEASE
GREEN_CI != RELEASED
```

The release checklist requires two byte-identical builds from byte-identical clean checkouts before publication.

## Adversarial validation

`tools/adversarial_storage.py` is a deterministic fixed-seed CI battery covering malformed identities, path traversal, secret metadata and object corruption. It supplements targeted unit/security tests; it is not a proof that no bug exists.

```text
FUZZ_PASS != SECURITY_PROOF
```

## Secret scanning and fixtures

Examples/tests must use synthetic placeholders, never production credentials or private provider payloads. CI must remain safe on public runners.

Before public release/export, run the metadata audit where relevant, scan tracked/generated artifacts for credential patterns, and review high-entropy/account-linked values.

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
COLLECTION_MEMBERSHIP != DECLASSIFICATION
DERIVED_INDEX != PUBLIC_DATA
ENCODED != ENCRYPTED
DNA_PROJECTION_INHERITS_SOURCE_PRIVACY
LOOPBACK != REMOTE_AUTH
COMPRESSED_UNTRUSTED_INPUT != ACCEPTED_BY_DEFAULT
MIGRATION != REINTERPRETATION
RELEASE_HASH != SEMANTIC_TRUTH
MERGED_MAIN != PUBLISHED_RELEASE
GREEN_CI != RELEASED
```

## Reporting

For security-sensitive changes, include the affected boundary, threat, mitigation, residual risk, and regression coverage in the pull request description.
