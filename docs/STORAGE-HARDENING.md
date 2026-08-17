# QSOL-CONTROL Storage Hardening Contract

This document makes the Phase 1A determinism, concurrency, privacy and repository-boundary assumptions explicit.

## 1. Lexical tokenization is versioned

The deterministic lexical baseline uses:

```text
engine       qsol.term-frequency-cosine/2
tokenizer    qsol.unicode-nfkc-casefold-alnum/1
normalization NFKC
case mapping  Unicode casefold
token chars   Unicode categories L* and N*, plus underscore
stopwords     none
stemming      none
```

All other Unicode code points are delimiters.

The index record stores the Python `unicodedata.unidata_version` used to tokenize the corpus. Rebuilding an index under a different Unicode database may therefore produce a different derived index identity. That is acceptable only when recorded explicitly; it must not be silently presented as the same derived artifact.

```text
TOKENIZER_VERSION != TRUTH_AUTHORITY
REBUILT_INDEX != ORIGINAL_INDEX
```

## 2. Lexicographic ordering is locale-independent

Content references are ASCII `sha256:<hex>` strings and are ordered bytewise.

General normalized lexical strings use UTF-8 byte order after NFKC + casefold normalization.

CONTROL does not use locale collation, filesystem directory order, GUI sort order, or host-language locale settings as part of canonical ordering.

Canonical collation identifier:

```text
qsol.utf8-byte-lexicographic/1
```

## 3. Search index integrity

Lexical indexes contain:

- exact Collection `snapshot_id`;
- tokenizer descriptor;
- collation identifier;
- inherited Collection privacy class;
- `documents_sha256` over canonical JSON term maps.

Semantic indexes contain:

- exact Collection `snapshot_id`;
- embedding provider;
- model ID;
- revision;
- dimensions;
- inherited Collection privacy class;
- `embedding_sha256` over the canonical embedding descriptor;
- `vectors_sha256` over canonical vector data.

Every index also has a content-derived `index_id`. `get_index()` re-verifies identity and payload fingerprints before use.

A semantic index whose bound snapshot is not the current Collection snapshot fails closed. There is no Phase-1A `allow-stale` mode.

```text
SNAPSHOT_MISMATCH => REFUSE_SEARCH
VECTOR_HASH_MATCH != EMBEDDING_AUTHENTICITY
SEARCH_SCORE != EVIDENCE_STRENGTH
```

## 4. Concurrency model

Phase 1A is deliberately **single-node and local-filesystem oriented**.

It does not claim distributed transactions, network-filesystem locking, multi-host consensus, or database-grade crash recovery.

Collection and index-head writes use an exclusive lock file. A second writer encountering the same lock fails closed instead of racing the first writer.

Collection updates also support compare-and-swap with an expected HEAD snapshot:

```bash
python3 tools/storage_cli.py --root .store update-collection <collection_id> \
  --add <file_id> \
  --expect-head <snapshot_id>
```

If HEAD changed after the caller inspected it, the update is rejected.

This protects against stale local writers. It is not a distributed lease protocol.

Stale lock recovery is intentionally not automatic in Phase 1A. An operator must investigate a leftover lock rather than CONTROL guessing that a writer is dead.

## 5. Snapshot lifecycle

Collection descriptors and snapshots are immutable content-addressed records.

Only the small `HEAD.json` pointer advances.

Phase 1A implements no snapshot garbage collection or compaction. Historical snapshots remain available for verification and replay lineage.

```text
HEAD_MOVES
SNAPSHOTS_DO_NOT_MUTATE
```

## 6. Restricted DNA export

DNA/codon projection is fully reversible and inherits source privacy.

A `RESTRICTED` File requires both:

```text
--allow-restricted
--acknowledge-reversible-sensitive-export
```

and an explicit:

```text
--actor <identifier>
```

A successful export emits a local immutable audit event containing the File ID, privacy class, projection ID, traversal ID, content hash, output target and acknowledgement state.

`--dry-run` performs validation and computes the projection identity without writing the projection and without creating an audit event.

The CLI refuses symlink inputs/outputs on the sensitive file/projection paths it controls. This reduces accidental path substitution; it is not a sandbox boundary.

## 7. Operator audit

Current audited operations:

- committed Collection membership updates;
- DNA exports;
- storage fingerprints requested through the CLI.

Audit records are content-addressed local CONTROL records and can be listed with:

```bash
python3 tools/storage_cli.py --root .store audit
```

Audit events are excluded from the canonical storage fingerprint so requesting a fingerprint does not change the fingerprint being reported.

```text
AUDIT_EVENT != EPISTEMIC_EVENT
AUDIT_LOG != ORACLE_LEDGER
```

## 8. Metadata and vector privacy

Embedding descriptors, File/Collection metadata and audit details are scanned for a small denylist of obvious credential markers before persistence. This is a guardrail, not a complete secret scanner.

Do not store:

- API keys;
- bearer tokens;
- private keys;
- session cookies;
- provider secrets;
- arbitrary provider-response blobs containing unknown sensitive fields.

Semantic vectors inherit the privacy class of the Collection snapshot that produced them.

```text
DERIVED != SAFE_TO_PUBLISH
```

## 9. Dry-run semantics

`update-collection --dry-run` validates the proposed membership, privacy monotonicity and referenced File IDs without creating a snapshot or moving HEAD.

`dna-export --dry-run` validates privacy acknowledgement and computes the exact projection identity without writing output or an audit event.

A dry-run result is advisory operational output, not a persisted commitment.

## 10. Operational limits

Phase 1A intentionally does not promise a fixed maximum File size or Collection size. The implementation reads File payloads and JSON index structures into memory, so practical limits are bounded by local RAM, filesystem capacity and Python process limits.

Therefore Phase 1A should be treated as an auditable research substrate, not a petabyte document service.

Large-corpus work should prefer external/rebuildable indexing adapters rather than enlarging canonical CONTROL records without review.

## 11. Repository separation

The intended repository boundary is now explicit:

```text
QSOL-CONTROL  OPERATES
  public machinery, schemas, codecs, CLI, tests

QSOL-CORPUS   PRESERVES INTERACTION CORPUS
  private persistent user/model conversation corpus and curated Collections

LATTICE       REMEMBERS
  public reusable lattice-memory implementation/profile

QSOL-ARK      SURVIVES
  recovery/preservation boundary
```

QSOL-CONTROL must not become the canonical home of private user conversation datasets merely because it contains the storage engine.

Likewise, LATTICE geometry does not gain evidence or truth authority by moving into its own repository.

```text
ENGINE != CORPUS
CORPUS != EVIDENCE_AUTHORITY
LATTICE != TRUTH
```
