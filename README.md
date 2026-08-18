# QSOL-CONTROL

**A human + AI control plane for the QSOL ecosystem, orchestrating NEXUS Council reasoning, ORACLE evidence, deterministic votes, replayable queries, persistent Collections, portable CONCAP delivery, and 3×3×3 lattice memory.**

> **CONTROL controls the machinery, not reality.**
>
> A button becoming green does not make a claim true. Six models agreeing does not make a claim true either. A semantic-search score of `0.97` does not make it true. We are trying very hard to disappoint the dashboard industry.

QSOL-CONTROL exposes the same governed system through two planned surfaces:

- **Human control plane** — WebUI for questions, evidence, Council votes, minority reports, Files, Collections, search, model states, lattice memory and replay.
- **AI control plane** — structured machine interface for equivalent operations without hidden epistemic privilege.

CONTROL owns orchestration and storage mechanics. It does **not** own scientific truth, public epistemic authority, NEXUS governance, ORACLE history, or ARK recovery authority.

## Full architecture

```text
                                      HUMAN OPERATOR
                                           |
                                   browser / WebUI
                                           |
                                           v
                             +-----------------------------+
                             |        QSOL-CONTROL         |
                             |           OPERATES          |
                             |-----------------------------|
                             | Human WebUI                 |
                             | AI / agent API              |
                             | query orchestration         |
                             | File / Collection control   |
                             | replay / comparison         |
                             +--------------+--------------+
                                            |
                         +------------------+------------------+
                         |                                     |
                 evidence-only                         Council reasoning
                         |                                     |
                         v                                     v
              +----------------------+              +----------------------+
              |     QSOL-ORACLE      |              |      QSOL-NEXUS      |
              |      WITNESSES       |              |       REASONS        |
              |----------------------|              |----------------------|
              | provenance           |              | AI Council           |
              | observations         |              | WHITE -> RED         |
              | conflicts / unknowns |              | -> BLACK -> YELLOW   |
              | witness ledger       |              | -> GREEN -> BLUE     |
              | temporal contracts   |              | -> SEALED BALLOT     |
              +----------+-----------+              +-----------+----------+
                         |                                          |
                         |         witnessed / reasoned refs        |
                         |                                          |
                         +------------------+-----------------------+
                                            |
                                            v
                             +-----------------------------+
                             |  3 x 3 x 3 LATTICE MEMORY   |
                             |        REMEMBERS            |
                             |-----------------------------|
                             | question / response /       |
                             | evidence classification     |
                             | provenance / lineage        |
                             | AI model-state refs         |
                             | historical / recovery refs  |
                             +--------------+--------------+
                                            |
                                            | references
                                            v
                    +---------------------------------------------+
                    |       PERSISTENT FILES + COLLECTIONS        |
                    |---------------------------------------------|
                    | raw objects: sha256(bytes)                  |
                    | immutable File metadata                     |
                    | named persistent Collections                |
                    | immutable membership snapshots              |
                    | deterministic lexical retrieval             |
                    | semantic vector indexes (derived)           |
                    | DNA/codon lattice projection (derived)      |
                    +----------------------+----------------------+
                                           |
                         approved recovery/context projection
                                           |
                                           v
                    +---------------------------------------------+
                    |        PORTABLE CONCAP DELIVERY             |
                    |---------------------------------------------|
                    | QSOL-RESTORE-DAT/1 objects                  |
                    | content-addressed immutable paths           |
                    | role -> object index                        |
                    | deterministic transport bundle              |
                    +----------------------+----------------------+
                                           |
                                transport-neutral bytes
                                           |
                                           v
                                      QSOL-THOTH
                               routing / resolution boundary
                                           |
                               preservation / reconstruction
                                           v
                                   +----------------+
                                   |    QSOL-ARK    |
                                   |    SURVIVES    |
                                   +----------------+

        +----------------------+     +----------------------+     +----------------------+
        |   QSOL-SUBSTRATE     |     |       QSOL-ARK       |     |       QSOL-INT       |
        |        KNOWS         |     |       SURVIVES       |     |       COMPOSES        |
        | public epistemic     |     | recovery contracts   |     | cross-repo integrity |
        | state + provenance   |     | reconstruction       |     | drift + handoff      |
        +-----------+----------+     +-----------+----------+     +-----------+----------+
                    \___________________________|___________________________/
                                                |
                                      THREE-PILLAR FOUNDATION

       QSOL-CONTEXT (private working context)
             |
             | explicit/publication-safe projections only
             v
       QSOL-SUBSTRATE

       QSOL-ORACLE publication contract:
       QSOL-CONTEXT -> eligible for public release on 18 Aug 2056
       ELIGIBLE != EXECUTED
```

## The verbs

```text
QSOL-SUBSTRATE  KNOWS
QSOL-ARK        SURVIVES
QSOL-INT        COMPOSES
QSOL-ORACLE     WITNESSES
QSOL-NEXUS      REASONS
QSOL-CONTROL    OPERATES
LATTICE MEMORY  REMEMBERS
```

## Files vs Collections

The Phase-1 storage model makes a deliberate distinction:

```text
FILE
= one immutable content object + metadata
= may be attached to a single run for immediate context

COLLECTION
= persistent named group of File references
= survives across runs
= membership is snapshot-versioned
= may have searchable derived indexes
```

A File does not need to be copied when it joins a Collection. Collections store content-addressed references.

```text
raw bytes
   |
   +--> File record
           |
           +--> run attachment
           |
           +--> Collection A
           |
           +--> Collection B
```

Collection membership is stored as immutable snapshots. Only a small atomic `HEAD` pointer moves forward.

See [`docs/PERSISTENT-STORAGE.md`](docs/PERSISTENT-STORAGE.md).

## Search without pretending similarity is truth

Phase 1 provides two retrieval paths:

### Deterministic lexical baseline

```text
qsol.term-frequency-cosine/1
```

Dependency-free UTF-8 token counts + cosine similarity provide a reproducible offline baseline.

### Semantic vector retrieval

```text
qsol.cosine-vector-search/1
```

CONTROL accepts externally generated embedding vectors together with an explicit provider/model/revision/dimension descriptor. This keeps one embedding vendor out of canonical storage.

Every search index binds to an exact Collection snapshot. If Collection membership changes, an old semantic index becomes stale and search fails closed until it is rebuilt/re-registered.

```text
SEARCH_SCORE != TRUTH
SEMANTIC_SIMILARITY != EVIDENCE_STRENGTH
INDEX != CANONICAL_MEMORY
COLLECTION_MEMBERSHIP != ENDORSEMENT
```

## 3×3×3 lattice memory

CONTROL defines a **3×3×3 Sierpinski-derived logical lattice** with 27 top-level cells.

```text
X = information role   question | response | evidence
Y = epistemic role     observed | derived | unresolved
Z = temporal role      current | historical | recovery
```

```text
L[x,y,z]
```

The geometry is a deterministic addressing/recovery discipline, not a literal claim about cognition or physics.

```text
GEOMETRY != TRUTH
LATTICE_ADDRESS != COLLECTION_MEMBERSHIP
```

See [`docs/LATTICE-MEMORY.md`](docs/LATTICE-MEMORY.md).

## DNA / codon recovery projection

Phase 1 adds a reversible digital projection over the same 27-cell lattice:

```text
outer address structure:
  3 x 3 x 3
  = ternary coordinate structure
  = 27 cells

payload alphabet:
  A = 00
  C = 01
  G = 10
  T = 11

4 bases = 1 byte
3 bases = 6 bits = 64 possible codon slots
```

Bytes are encoded into `A/C/G/T`, grouped into three-base codons, and distributed round-robin across one deterministic 27-cell traversal.

Two versioned traversals exist:

```text
qsol.lexicographic-27/1
qsol.phi-stride-27/1
```

The optional φ-gated path uses a fixed stride of `17` over the 27 lexicographic cells:

```text
cell_index(n) = (17 * n) mod 27
```

Because `gcd(17, 27) = 1`, every cell is visited exactly once before the path repeats.

The projection stores original byte length and SHA-256 and must decode byte-for-byte before it is accepted.

**Raw bytes remain canonical.** The DNA/lattice form is a derived recovery representation, not a compression claim and not a biological claim.

```text
DNA_ENCODING != BIOLOGICAL_CLAIM
PHI_TRAVERSAL != PHYSICAL_TRUTH
CODON_FREQUENCY != EVIDENCE
```

Conceptual lineage is documented in [`docs/STORAGE-LINEAGE.md`](docs/STORAGE-LINEAGE.md), including QSOLAI, QAI-UFT, `supreme-engine`, and THESIS.

## Human / AI question flow

```text
Human or AI caller
  -> CONTROL receives question
  -> optional File attachments / Collection snapshot selected
  -> retrieval finds candidate context
  -> ORACLE supplies bounded evidence state
  -> NEXUS runs Council reasoning against admitted evidence
  -> votes and minority reports remain separate from evidence
  -> ORACLE witnesses externally visible receipts
  -> CONTROL preserves references, visible outputs and model states
  -> lattice classifies interaction memory
```

AI callers receive **no more epistemic authority than human callers**.

## AI model-state preservation

CONTROL's model-state contract preserves externally inspectable runtime metadata for future computational archaeology where available:

```text
provider / runtime / model identifier / revision
weight or tokenizer identity where verifiable
quantization
sampling configuration
seed where meaningful
Council seat / mode
NEXUS / ORACLE / SUBSTRATE identities
CONTROL run identity
relevant runtime hardware metadata
```

It does not claim to preserve a model's mind or hidden chain-of-thought.

```text
MODEL_STATE != MODEL_MIND
VISIBLE_OUTPUT != HIDDEN_CHAIN_OF_THOUGHT
RUNTIME_METADATA != CONSCIOUSNESS
```

See [`docs/MODEL-STATE.md`](docs/MODEL-STATE.md).

## Phase 1B interaction persistence

Phase 1B now implements the offline interaction-memory core. Persistent run records use the versioned `qsol-control-interaction/2` contract; the earlier `qsol-control-interaction/1` schema remains available as the legacy contract rather than being silently redefined.

Each run is content-addressed, binds to exact File IDs and an exact Collection snapshot when supplied, and has an append-only event history with an atomic `HEAD`. Questions, responses and evidence receive deterministic top-level lattice addresses from the recorded information/epistemic/temporal roles.

```text
RUN_ID = sha256(canonical run payload)
LATTICE_ADDRESS != TRUTH
HASH_INTEGRITY != EVIDENCE_AUTHORITY
RUN_RECORD != MODEL_MIND
```

Non-`unknown` evidence states require an explicit ORACLE reference. Derived events require explicit input lineage. Runtime validation rejects obvious credential material and model-state payloads that claim hidden chain-of-thought capture.

Run verification checks immutable record identities, event lineage, exact Collection snapshot membership and the bytes behind referenced File records. Record-set imports are bounded to 16 MiB and 100,000 events. RESTRICTED record-set exports require explicit acknowledgement and are written owner-only (`0600`).

The minimum ARK recovery bundle is still deliberately open; the Phase 1B record-set is an interaction round-trip format, not a claim that the complete CONTROL recovery package already exists.

## Storage and interaction CLIs

The current Phase-1 reference runtimes are standard-library-only.

```bash
python3 tools/storage_cli.py --root .store put-file notes.txt
python3 tools/storage_cli.py --root .store create-collection "Research"
python3 tools/storage_cli.py --root .store update-collection <collection_id> --add <file_id>
python3 tools/storage_cli.py --root .store build-lexical <collection_id>
python3 tools/storage_cli.py --root .store search <collection_id> "quantum evidence"
python3 tools/storage_cli.py --root .store dna-export <file_id> --output file.dna.json
python3 tools/storage_cli.py dna-decode file.dna.json --output recovered.bin
python3 tools/storage_cli.py --root .store verify
python3 tools/storage_cli.py --root .store fingerprint

python3 tools/interaction_cli.py --root .store create \
  --question "What survives?" \
  --mode evidence_only \
  --requester-kind human \
  --created-at 2026-08-19T08:00:00+09:30 \
  --replayability R3
python3 tools/interaction_cli.py --root .store verify <run_id>
python3 tools/interaction_cli.py --root .store fingerprint <run_id>
```

Replayability classification is explicit at the CLI boundary; omission never silently becomes an exact-replay claim.

Semantic vectors can be registered with `register-semantic` and searched with `search-semantic`; embedding generation itself is intentionally outside the canonical storage core.

## Portable CONCAP delivery

CONTROL contains the packing and verification side of the portable-context bridge used with QSOL-THOTH.

```text
QSOL-CONTEXT / approved source
          |
          v
      QSOL-CONTROL
          |
          | qsol-control-concap-export-spec/1
          v
  QSOL-RESTORE-DAT/1 objects
          |
          +--> BOOTSTRAP.json
          +--> OBJECTS.json
          +--> objects/sha256/<prefix>/<digest>.dat
          |
          v
  local disk / USB / archive / LAN / HTTPS
          |
          v
      QSOL-THOTH
```

The immutable object identity is `sha256(exact object bytes)`. Transport location is not part of object identity, and CONTROL does not acquire THOTH's semantic-routing authority.

```text
PRIVATE_SOURCE != PORTABLE_BUNDLE
PORTABLE_BUNDLE != PUBLICATION
RESTRICTED_BUNDLE != ENCRYPTED_BUNDLE
SOURCE_REF_STRIPPED != SOURCE_BYTES_ANONYMIZED
OBJECT_IDENTITY != TRANSPORT_LOCATION
ROUTING != RESOLUTION
RESOLUTION != TRANSPORT
TRANSPORT != AUTHORITY
```

RESTRICTED export requires explicit acknowledgement. Locally built RESTRICTED bundle directories are owner-only (`0700`), files are owner-only (`0600`), and deterministic ZIP output is `0600`. This is local file protection, **not encryption**.

Imported bundle metadata is bounded before JSON parsing: `BOOTSTRAP.json` is capped at 1 MiB, `OBJECTS.json` at 16 MiB, with 10,000 objects and 100,000 role bindings maximum. Deterministic ZIP output must be outside the verified bundle tree.

```bash
python3 tools/concap_bundle.py build \
  --source-root /path/to/source \
  --export-spec restore/CONCAP-EXPORT.spec.json \
  --output-dir /secure/path/qsol-portable \
  --zip-output /secure/path/qsol-portable.zip

python3 tools/concap_bundle.py verify --bundle /secure/path/qsol-portable
```

See [`docs/PORTABLE-CONCAP-BUNDLES.md`](docs/PORTABLE-CONCAP-BUNDLES.md) and [`ai/concap-bundle-contract.json`](ai/concap-bundle-contract.json).

## Constitutional invariants

```text
CONTROL_DISPLAY != AUTHORITY
CONTROL_OPERATION != TRUTH
VOTE != EVIDENCE
CONSENSUS != TRUTH
CONFIDENCE != PROBABILITY
STORED != TRUE
PERSISTED != CANONICAL
MEMORY != AUTHORITY
HASH_INTEGRITY != EVIDENCE_AUTHORITY
RUN_RECORD != MODEL_MIND
SEARCH_SCORE != TRUTH
SEMANTIC_SIMILARITY != EVIDENCE_STRENGTH
INDEX != CANONICAL_MEMORY
COLLECTION_MEMBERSHIP != ENDORSEMENT
MODEL_STATE != MODEL_MIND
DNA_ENCODING != BIOLOGICAL_CLAIM
PHI_TRAVERSAL != PHYSICAL_TRUTH
HUMAN_CALLER == AI_CALLER_FOR_EPISTEMIC_AUTHORITY
CONTROL_MUST_NOT_REWRITE_ORACLE_HISTORY
CONTROL_MUST_NOT_CHANGE_NEXUS_VOTES
```

## Replay instead of chat amnesia

Phase 1B now preserves an immutable offline run history bound to exact File refs, an exact Collection snapshot, explicit evidence/model references and deterministic lattice addresses. This does not yet execute a live replay through ORACLE or NEXUS; it establishes the deterministic storage substrate that later replay uses.

That supports future operations without rewriting the original history:

```text
REPLAY ORIGINAL RUN
RE-RUN WITH CURRENT COLLECTION
COMPARE RESULTS
EXPLAIN WHAT CHANGED
```

## Validation

Validation remains dependency-free and requires **Python 3.11 or newer**. CI currently uses Python 3.12.

```bash
python3 tools/validate_control.py
python3 -W default -m unittest discover -s tests -v
```

The manifest registers the Phase 1B interaction runtime/CLI, legacy and persistent interaction schemas, run-event and run-record-set schemas, plus the existing storage/portable-CONCAP contracts. Runtime adversarial coverage is in `tests/test_interaction_store.py`; portable bundle behavior remains covered by `tests/test_concap_bundle.py`.

All public schemas use **JSON Schema draft 2020-12**.

## Documentation map

- [`README4AI.md`](README4AI.md) — compact machine bootstrap.
- [`AGENTS.md`](AGENTS.md) — contributor/agent operating rules.
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — authority boundaries and system design.
- [`ROADMAP.md`](ROADMAP.md) — implementation sequence.
- [`SECURITY.md`](SECURITY.md) — privacy, redaction and control/storage threat boundaries.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — contribution/validation contract.
- [`CHANGELOG.md`](CHANGELOG.md) — contract evolution.
- [`docs/PERSISTENT-STORAGE.md`](docs/PERSISTENT-STORAGE.md) — Files, Collections, snapshots and search.
- [`docs/STORAGE-LINEAGE.md`](docs/STORAGE-LINEAGE.md) — conceptual lineage for lexicographic, codon and φ-gated design.
- [`docs/LATTICE-MEMORY.md`](docs/LATTICE-MEMORY.md) — 27-cell interaction-memory model.
- [`docs/MODEL-STATE.md`](docs/MODEL-STATE.md) — future-AI model-state preservation.
- [`docs/NEXUS-ORACLE.md`](docs/NEXUS-ORACLE.md) — orchestration boundary.
- [`docs/PORTABLE-CONCAP-BUNDLES.md`](docs/PORTABLE-CONCAP-BUNDLES.md) — deterministic portable bundle format and transport boundary.
- [`ai/concap-bundle-contract.json`](ai/concap-bundle-contract.json) — machine-readable portable bundle contract.
- [`docs/WEBUI.md`](docs/WEBUI.md) — planned human surface.
- [`docs/AI-API.md`](docs/AI-API.md) — planned machine caller surface.
- [`manifest.json`](manifest.json) — canonical machine map.

## License

QSOL-CONTROL is licensed under the **Mozilla Public License 2.0 (MPL-2.0)**. See [`LICENSE`](LICENSE).

## Status

- **PR #1:** Phase-0 architecture/contracts bootstrap — merged.
- **PR #2:** Phase-1A persistent Files/Collections, retrieval indexes, and DNA/lattice recovery projection — merged/integrated baseline.
- **PR #4:** portable CONCAP delivery — merged.
- **PR #5:** Phase-1B interaction/lattice persistence — implemented in this branch; minimum ARK CONTROL bundle remains open.

Live ORACLE/NEXUS adapters, the minimum ARK CONTROL recovery bundle, WebUI and network AI API remain sequenced in the ROADMAP.

---

**QSOL-CONTROL controls the machinery, not reality. If the Council unanimously votes that the Moon is made of cheese and the semantic index returns it at 0.999 similarity, CONTROL's job is to preserve both facts about the system — not update astronomy.**
