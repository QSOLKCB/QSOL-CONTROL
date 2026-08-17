# QSOL-CONTROL Persistent Storage

## Purpose

QSOL-CONTROL distinguishes **Files** from **Collections**.

```text
FILE
= one immutable document/content object plus metadata
= may be attached to one run for immediate context
= does not need to live in a Collection

COLLECTION
= persistent named group of File references
= membership changes create immutable snapshots
= may have one or more rebuildable search indexes
= intended for retrieval across many documents and many runs
```

The design borrows the useful product distinction without importing a vendor-specific storage dependency.

## Core rule

```text
CANONICAL BYTES != SEARCH INDEX
COLLECTION MEMBERSHIP != ENDORSEMENT
SEARCH SCORE != TRUTH
SEMANTIC SIMILARITY != EVIDENCE STRENGTH
INDEX != CANONICAL MEMORY
DNA PROJECTION != CANONICAL BYTES
```

A search index helps retrieve likely-relevant records. It does not establish whether those records are true, authoritative, current, or admissible evidence.

## Storage stack

```text
                           QSOL-CONTROL
                                |
                    +-----------+-----------+
                    |                       |
                 run refs              persistent corpus
                    |                       |
                    v                       v
               +---------+          +----------------+
               |  FILES  |<---------|  COLLECTIONS   |
               +----+----+  members +--------+-------+
                    |                       |
          immutable metadata          immutable snapshots
                    |                       |
                    +-----------+-----------+
                                |
                                v
                    +-----------------------+
                    | CONTENT-ADDRESSED     |
                    | OBJECT STORE          |
                    | sha256(bytes)         |
                    +-----+-----------+-----+
                          |           |
                          |           +--------------------+
                          v                                v
              +-----------------------+        +-----------------------+
              | DERIVED SEARCH INDEX  |        | DNA/LATTICE PROJECTION|
              | lexical / embeddings  |        | A/C/G/T + codon64     |
              | rebuildable           |        | rebuildable           |
              +-----------------------+        +-----------------------+
```

The 3×3×3 lattice remains an interaction-memory classification layer. Collections are a persistent document grouping/retrieval layer. The DNA/lattice projection is a reversible recovery representation over raw File bytes. These layers complement one another rather than replacing one another.

## File identity

Raw bytes are stored by SHA-256 object identity:

```text
object_id = sha256(raw_bytes)
```

A File record is a separate immutable metadata object that references those bytes. Its identity includes metadata such as filename, media type, timestamp, privacy class, retention class, source and metadata:

```text
file_id = sha256(canonical_file_record_without_file_id)
```

Therefore:

- identical bytes can be deduplicated;
- the same bytes may have multiple legitimate File records with different provenance/metadata;
- renaming a File record does not silently rewrite old metadata;
- content identity and metadata identity remain distinguishable.

## Collections

A Collection has a stable `collection_id` derived from its creation descriptor.

Membership is not edited in-place. Each change creates a new immutable Collection Snapshot:

```text
revision 0 -> snapshot:A
                 |
                 v
revision 1 -> snapshot:B
                 |
                 v
revision 2 -> snapshot:C   <- HEAD
```

Each snapshot contains:

```text
collection_id
revision
previous_snapshot_id
created_at
sorted member file_ids
snapshot_id
```

Only the small local `HEAD` pointer moves atomically.

This means a future replay can state exactly which Collection membership existed when a search or Council run occurred.

## Lexicographic ordering

Lexicographic ordering is part of the deterministic storage discipline.

CONTROL uses it for:

- canonical JSON object-key ordering;
- Collection member ordering by `file_id`;
- deterministic search tie-breaking by `file_id`;
- canonical 27-cell lattice enumeration;
- stable exported record ordering where semantic order is otherwise absent.

The intent is the same discipline used elsewhere in QSOL: when multiple equivalent orderings are possible, choose one public deterministic rule rather than letting platform/runtime iteration order leak into identity.

## Search indexes are derived state

A Collection snapshot may have multiple indexes.

The bootstrap runtime implements two forms:

### Deterministic lexical baseline

`qsol.term-frequency-cosine/1`

This is a dependency-free, inspectable baseline for offline retrieval and regression tests. It tokenizes UTF-8 text, stores term counts and ranks by cosine similarity.

It is **not described as a modern embedding semantic model**.

### Semantic vector index

`qsol.cosine-vector-search/1`

CONTROL can persist externally generated embedding vectors and perform cosine search over them. The embedding generator is deliberately outside the Phase-1 storage core.

Every semantic index must identify at least:

```text
provider
model_id
revision
dimensions
```

Future adapters may add tokenizer/chunking/model hashes and other reproducibility metadata.

CONTROL therefore supports real vector retrieval without making a particular embedding vendor a dependency of canonical storage.

## Snapshot binding

Every index binds to one exact Collection Snapshot:

```text
index.collection_id
index.snapshot_id
```

If Collection membership changes, the previous semantic index becomes stale and semantic search fails closed until a new index is registered.

The deterministic lexical baseline may be rebuilt automatically because its algorithm is part of the public CONTROL contract.

## Why not make embeddings canonical?

Embedding models drift. Tokenizers change. Providers disappear. Vector dimensions change. Retrieval methods improve.

The durable archive should therefore preserve:

```text
canonical bytes
File metadata
Collection identity
Collection snapshots
index descriptors / receipts when useful
```

while treating vectors and indexes as reconstructable projections.

This follows the same QSOL principle used elsewhere:

> Canonical source survives; projections remain reproducible derivatives.

## Search result semantics

Search results return a score plus an explicit score meaning:

```text
retrieval_similarity_not_truth_or_evidence_strength
semantic_similarity_not_truth_or_evidence_strength
```

The WebUI must not relabel these scores as:

```text
truth probability
scientific confidence
evidence quality
Council support
source authority
```

Retrieval determines what should be inspected next, not what reality is required to believe.

## DNA / codon lattice projection

`storage/dna_lattice.py` implements a reversible digital projection:

```text
protocol: qsol-control-dna-lattice/1
codec:    qsol.dna-2bit-codon64/1
```

The four-symbol alphabet is assigned two-bit values:

```text
A = 00
C = 01
G = 10
T = 11
```

Therefore:

```text
4 bases = 8 bits = 1 byte
3 bases = 6 bits = 64 possible codon slots
```

A byte stream is encoded high bits first, grouped into three-base codons, padded with `A` only when the final codon requires it, and distributed across the lattice. The original byte length is retained so padding is never ambiguous.

### Why codons fit cleanly

The three-base digital codon provides an exact 0–63 integer slot:

```text
codon_index = first * 16 + second * 4 + third
```

where each base value is `0..3`.

This provides a direct six-bit mapping without claiming biological equivalence.

### 3×3×3 outer structure

The outer storage address remains the 27-cell lattice:

```text
L[0,0,0]
...
L[2,2,2]
```

Two traversal profiles are implemented.

#### Canonical lexicographic traversal

```text
qsol.lexicographic-27/1
```

Cells are enumerated as `(x, y, z)` tuples in ordinary lexicographic order.

#### Optional φ-gated traversal

```text
qsol.phi-stride-27/1
```

This is a single deterministic path through the same 27 cells using the fixed modular stride:

```text
stride = 17
index(n) = (17 * n) mod 27
```

`17` is the versioned protocol constant corresponding to `round(27 / φ)`. Since `gcd(17,27)=1`, all 27 cells are visited exactly once before the cycle repeats.

The implementation intentionally stores the integer constant. Runtime reconstruction does not depend on floating-point evaluation of φ.

### Round-robin placement

Codon `n` is assigned to traversal cell:

```text
cell = traversal[n mod 27]
```

Each cell stores its local codons in arrival order. Reconstruction walks global codon sequence numbers and deterministically selects the corresponding cell/local offset.

This avoids storing redundant sequence numbers for every codon while preserving an exact inverse mapping.

### Verification

Every projection includes:

```text
projection_id
content_sha256
byte_length
base_length
padding_bases
codon_count
27 cell strings
codon histogram
traversal_id
```

Decoding verifies:

- projection identity;
- exact 27-cell membership;
- valid A/C/G/T symbols;
- whole-codon cell lengths;
- traversal-assignment counts;
- base/byte lengths;
- codon histogram;
- final decoded SHA-256.

A projection is accepted only if it reconstructs the original bytes exactly.

### Storage efficiency boundary

The DNA string is **not a compression scheme**. Writing four ASCII letters for every byte would increase representation size.

CONTROL therefore keeps raw bytes as canonical storage and generates the DNA/codon form as an optional derived recovery/export projection.

```text
RAW_BYTES = CANONICAL
DNA_PROJECTION = DERIVED
DNA_ENCODING != COMPRESSION
DNA_ENCODING != BIOLOGICAL_CLAIM
PHI_TRAVERSAL != PHYSICAL_OPTIMALITY
```

This gives future systems a simple symbolic reconstruction path without making the normal object store deliberately worse.

See [`STORAGE-LINEAGE.md`](STORAGE-LINEAGE.md) for the conceptual lineage from QSOLAI, QAI-UFT, `supreme-engine`, and THESIS.

## Persistence layout

The reference store uses a simple filesystem layout:

```text
store/
├── objects/
│   └── sha256/
│       └── <prefix>/<digest>
└── records/
    ├── files/
    │   └── <file-digest>.json
    ├── collections/
    │   └── <collection-digest>/
    │       ├── collection.json
    │       ├── HEAD.json
    │       ├── snapshots/
    │       └── index-heads/
    └── indexes/
        └── <index-digest>.json
```

DNA/lattice projections are generated on demand rather than inserted into this canonical tree by default.

Writes use temporary files plus `os.replace()` so a partial write does not become the new canonical pointer.

## Privacy and retention

Durable File/Collection records accept:

```text
privacy:
  PUBLIC
  INTERNAL
  RESTRICTED

retention:
  TRANSIENT
  SESSION
  ARCHIVE
```

`FORBIDDEN` is intentionally rejected by the storage API.

This does **not** mean CONTROL can automatically recognize every credential or private datum. Classification and redaction must happen before persistence where required by `SECURITY.md`.

A Collection inherits no magical right to publish its members. Export/presentation must continue to respect each File's privacy and provenance.

A DNA/lattice projection inherits the source File's disclosure constraints. Encoding restricted bytes as `A/C/G/T` does not declassify them.

## Files attached to runs

A human or AI may attach a File to a run without placing it in a Collection:

```text
interaction record
   |
   +--> file_id
```

This is the immediate-context case.

If the same document should remain discoverable across future runs, add the File reference to a Collection:

```text
interaction -> file_id
                 |
                 v
             Collection
                 |
                 v
             searchable
```

The bytes are not duplicated; the Collection stores membership references.

## Lattice relationship

The lattice answers questions such as:

- Is this a question, response or evidence record?
- Is it observed, derived or unresolved?
- Is it current, historical or recovery-oriented?

A Collection answers a different question:

- Which durable Files belong to this searchable corpus at this snapshot?

The DNA projection answers another:

- Can these exact bytes be represented and reconstructed through the versioned digital codon/lattice codec?

Therefore:

```text
LATTICE ADDRESS != COLLECTION MEMBERSHIP
COLLECTION MEMBERSHIP != EPISTEMIC CLASSIFICATION
DNA PROJECTION != EVIDENCE STATUS
```

A File may be referenced from one or more lattice records and Collections without changing its File identity.

## Integrity and verification

`ControlStore.verify()` checks:

- File record identities;
- object size/hash agreement;
- Collection descriptor identities;
- snapshot identity and lineage;
- membership references;
- revision continuity;
- lineage loops.

`ControlStore.fingerprint()` produces a deterministic inventory fingerprint over canonical object/File identities and Collection HEAD snapshots.

Derived indexes and DNA/lattice projections are deliberately excluded from the canonical fingerprint because they are rebuildable projections.

## ARK recovery direction

A minimum recoverable persistent-storage bundle should eventually include:

```text
raw content objects
File records
Collection descriptors
Collection snapshots
schemas
canonical-JSON rules
hashing rules
storage fingerprint
optional index descriptors
optional DNA/lattice projections
```

A future system should be able to reconstruct Collection membership without reproducing the original search engine, and reconstruct File bytes without requiring the DNA projection. Search indexes and DNA forms can then be rebuilt or independently verified.

## Security boundaries

Persistent storage must never become an excuse to persist everything.

```text
PERSISTENT != PERMITTED
COLLECTION != PUBLICATION
INDEXED != SAFE_TO_DISCLOSE
SEARCHABLE != AUTHORITATIVE
ENCODED != DECLASSIFIED
```

See `SECURITY.md` for redaction, classification, retention and export rules.
