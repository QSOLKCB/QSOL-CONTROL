# QSOL-CONTROL

**A human + AI control plane for the QSOL ecosystem, orchestrating NEXUS Council reasoning, ORACLE evidence, deterministic votes, replayable queries, persistent Collections, portable CONCAP delivery, model-state archaeology, and 3×3×3 lattice memory.**

> **CONTROL controls the machinery, not reality.**
>
> A button becoming green does not make a claim true. Six models agreeing does not make a claim true either. A semantic-search score of `0.97` does not make it true. We are trying very hard to disappoint the dashboard industry.

QSOL-CONTROL exposes the same governed system through two planned surfaces:

- **Human control plane** — WebUI for questions, evidence, Council votes, minority reports, Files, Collections, search, model states, lattice memory and replay.
- **AI control plane** — structured machine interface for equivalent operations without hidden epistemic privilege.

CONTROL owns orchestration and storage mechanics. It does **not** own scientific truth, public epistemic authority, NEXUS governance, ORACLE history, ARK recovery authority, or anyone's secret model thoughts.

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
                    | model-state registry + comparisons          |
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

## Phase 4 model-state registry

CONTROL now implements persistent, immutable `qsol-control-model-state/1` records for **reproducibility and future computational archaeology**.

A model-state record can preserve, where available:

```text
provider / runtime / runtime version / model identifier / revision
model / weights / tokenizer hashes when locally verifiable
quantization
sampling configuration
context limit
seed where meaningful
Council seat / NEXUS mode
tool permissions + filesystem/network/plugin envelope
CONTROL / NEXUS / ORACLE / SUBSTRATE / ARK / INT identities
exact Collection snapshot identity
relevant runtime hardware metadata
```

Every canonical field also carries one explicit provenance class:

```text
observed
provider_reported
locally_verified
inferred
unknown
```

Unclassified fields become `unknown`, not mysteriously upgraded to `observed` during the night shift.

Local model/weight/tokenizer paths may be supplied solely for hashing. Regular files are identified by `sha256(exact bytes)`; sharded directories use an explicitly labelled canonical file-manifest identity. **Local paths and artifact bytes are never persisted in model-state records or archaeology exports.**

The full registry record is canonical. Phase 1B's older compact `model_state` run-event format remains a backward-compatible lineage projection that points to the same canonical `state_id`.

```text
MODEL_STATE != MODEL_MIND
VISIBLE_OUTPUT != HIDDEN_CHAIN_OF_THOUGHT
RUNTIME_METADATA != CONSCIOUSNESS
PROVIDER_REPORTED != LOCALLY_VERIFIED
HASH_IDENTITY != ARTIFACT_BYTES
MODEL_STATE_COMPARISON != MIND_COMPARISON
```

Cross-state and cross-run comparisons preserve both values and provenance. Future-AI archaeology exports are deterministic and self-describing, explicitly state that they contain neither hidden chain-of-thought nor model-mind data, and require explicit acknowledgement before exporting RESTRICTED records.

The future Phase 5 model-state inspector is already contract-bound to labels such as **“Model-state reproducibility metadata”** and **“Not model mind”**. The WebUI itself remains unimplemented.

See [`docs/MODEL-STATE.md`](docs/MODEL-STATE.md) and [`ai/model-state-contract.json`](ai/model-state-contract.json).

## Phase 1B interaction persistence

Persistent run records use the versioned `qsol-control-interaction/2` contract; the earlier `qsol-control-interaction/1` schema remains available as the legacy contract rather than being silently redefined.

Each run is content-addressed, binds to exact File IDs and an exact Collection snapshot when supplied, and has an append-only event history with an atomic `HEAD`. Questions, responses and evidence receive deterministic top-level lattice addresses from the recorded information/epistemic/temporal roles.

```text
RUN_ID = sha256(canonical run payload)
LATTICE_ADDRESS != TRUTH
HASH_INTEGRITY != EVIDENCE_AUTHORITY
RUN_RECORD != MODEL_MIND
```

Non-`unknown` evidence states require an explicit ORACLE reference. Derived events require explicit input lineage. Runtime validation rejects obvious credential material and model-state projections that claim hidden chain-of-thought capture.

Run verification checks immutable record identities, event lineage, exact Collection snapshot membership and the bytes behind referenced File records. Record-set imports are bounded to 16 MiB and 100,000 events. RESTRICTED record-set exports require explicit acknowledgement and are written owner-only (`0600`).

## Minimum ARK recovery bundle

Phase 1B's offline gate is closed by `qsol-control-ark-minimum-bundle/1`, carried inside the existing deterministic `QSOL-RESTORE-DAT/1` container.

For one interaction run it packages the run record, complete event chain, referenced File records/raw objects, the exact bound Collection descriptor and snapshot lineage to revision 0 when applicable, and the lattice profile required to interpret addresses. Derived search indexes, WebUI state, and live service connections are excluded from the minimum set.

Verification reconstructs a fresh temporary CONTROL store and requires the original run fingerprint to match after reconstruction.

If the source Collection has moved on since the run, the recovered store deliberately points its local `HEAD` to the **historical snapshot used by the run**, not today's source `HEAD`.

```text
RECOVERY_BUNDLE != SEMANTIC_AUTHORITY
RECOVERY_HEAD != SOURCE_CURRENT_HEAD
RESTORED_CONTEXT != ORIGINAL_ASSISTANT_INSTANCE
```

See [`docs/ARK-MINIMUM-BUNDLE.md`](docs/ARK-MINIMUM-BUNDLE.md) and [`ai/ark-recovery-contract.json`](ai/ark-recovery-contract.json).

## Phase 2 read-only ORACLE adapter

CONTROL implements `qsol-control-oracle-adapter/1` against the stable parent protocol `QSOL-ORACLE/1`.

The adapter discovers the parent manifest at runtime, verifies the append-only ledger before evidence queries, returns exact `known` / `conflict` / `unknown` states, preserves event/provenance references, reports freshness separately from truth semantics, stores verified receipt payloads only as reference-only CONTROL Files, and exposes the QSOL-CONTEXT 2056 timelock state.

The adapter has **no ORACLE write operation**. CONTROL receipt storage is forbidden from overlapping the ORACLE repository tree.

```text
ORACLE_REFERENCE != CONTROL_AUTHORITY
ORACLE_RECEIPT_COPY != ORACLE_LEDGER_APPEND
FRESH != TRUE
STALE != FALSE
SUGGESTED_SEARCH != EVIDENCE
ELIGIBLE != EXECUTED
```

See [`docs/ORACLE-ADAPTER.md`](docs/ORACLE-ADAPTER.md) and [`ai/oracle-adapter-contract.json`](ai/oracle-adapter-contract.json).

## Phase 3 NEXUS Council adapter

CONTROL implements `qsol-control-nexus-adapter/1` over NEXUS's local JSONL/stdio control plane.

Every adapter session discovers `system.health` and `system.operations`; CONTROL does not freeze the entire NEXUS operation catalog into its own code. The adapter requires the live parent to advertise `council.run`, `world.inspect` and `receipt.verify`, with `council.epoch.verify` used only when advertised and returned by NEXUS.

After Council execution, CONTROL resolves the committed `council_session` and receipt from NEXUS WorldStore, verifies their content-addressed identities, preserves the canonical roster and phase order, verifies each revealed ballot against its sealed commitment, renders the exact consensus threshold from the committed session policy, and preserves minority reports.

The six deliberation phases are preserved from the NEXUS session policy. The subsequent commitment/reveal stage is rendered separately as `SEALED_BALLOT`; CONTROL does not rewrite the parent phase array to make a diagram look tidier.

```text
CONTROL_INVOKES_COUNCIL != CONTROL_OWNS_COUNCIL
NEXUS_SESSION != CONTROL_REINTERPRETATION
CONTROL_CAN_WORLD_CREATE = false
CONTROL_CAN_OVERRIDE_VOTE_WEIGHT = false
CONTROL_CAN_OVERRIDE_BALLOTS = false
CONTROL_CAN_OVERRIDE_CONSENSUS_THRESHOLD = false
NEXUS_OWNS_WORLDSTORE_HISTORY = true
VISIBLE_NEXUS_OUTPUT != HIDDEN_CHAIN_OF_THOUGHT
```

CONTROL never calls NEXUS Stenographer operations through this adapter and fails closed if parent output exposes fields labelled as hidden/private reasoning, chain-of-thought, scratchpad, or reasoning trace. Visible phase submissions and visible ballot rationales remain externally visible NEXUS outputs, not hidden chain-of-thought.

Verified NEXUS session/receipt/output artifacts may be copied into CONTROL only as `reference-only` Files. When linked to an existing CONTROL interaction, the adapter appends receipt and derived response events without copying NEXUS governance authority.

See [`docs/NEXUS-ADAPTER.md`](docs/NEXUS-ADAPTER.md) and [`ai/nexus-adapter-contract.json`](ai/nexus-adapter-contract.json).

## Storage, recovery, adapter, and model-state CLIs

The reference runtimes are standard-library-only.

```bash
python3 tools/storage_cli.py --root .store put-file notes.txt
python3 tools/storage_cli.py --root .store create-collection "Research"
python3 tools/storage_cli.py --root .store update-collection <collection_id> --add <file_id>
python3 tools/storage_cli.py --root .store build-lexical <collection_id>
python3 tools/storage_cli.py --root .store search <collection_id> "quantum evidence"
python3 tools/storage_cli.py --root .store verify
python3 tools/storage_cli.py --root .store fingerprint

python3 tools/interaction_cli.py --root .store verify <run_id>
python3 tools/interaction_cli.py --root .store fingerprint <run_id>

python3 tools/model_state.py --root .store capture --descriptor model-state-input.json
python3 tools/model_state.py --root .store verify <state_id>
python3 tools/model_state.py --root .store compare-states <left_state_id> <right_state_id>
python3 tools/model_state.py --root .store compare-runs <left_run_id> <right_run_id>
python3 tools/model_state.py --root .store export --run-id <run_id> --output model-state-archaeology.json

python3 tools/ark_bundle.py export --root .store <run_id> --output control-run.dat
python3 tools/ark_bundle.py verify control-run.dat
python3 tools/ark_bundle.py restore control-run.dat --target recovered-store

python3 tools/oracle_adapter.py --oracle-root /path/to/QSOL-ORACLE discover
python3 tools/oracle_adapter.py --oracle-root /path/to/QSOL-ORACLE query "QSOLKCB/QSOL-CONTEXT"
python3 tools/oracle_adapter.py --oracle-root /path/to/QSOL-ORACLE timelock

python3 tools/nexus_adapter.py \
  --nexus-command-json '["python3","-m","nexus_runtime","--world","/secure/nexus-world"]' \
  discover
python3 tools/nexus_adapter.py \
  --nexus-command-json '["python3","-m","nexus_runtime","--world","/secure/nexus-world"]' \
  run --question "What follows?" --members council-members.json --evidence-ref object:<sha256>
```

## Portable CONCAP delivery

CONTROL contains the packing and verification side of the portable-context bridge used with QSOL-THOTH. Immutable object identity is `sha256(exact object bytes)` and transport location is not part of object identity.

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

See [`docs/PORTABLE-CONCAP-BUNDLES.md`](docs/PORTABLE-CONCAP-BUNDLES.md) and [`ai/concap-bundle-contract.json`](ai/concap-bundle-contract.json).

## Constitutional invariants

```text
CONTROL_DISPLAY != AUTHORITY
CONTROL_OPERATION != TRUTH
VOTE != EVIDENCE
CONSENSUS != TRUTH
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
MODEL_STATE_COMPARISON != MIND_COMPARISON
RUNTIME_METADATA != CONSCIOUSNESS
PROVIDER_REPORTED != LOCALLY_VERIFIED
HASH_IDENTITY != ARTIFACT_BYTES
DNA_ENCODING != BIOLOGICAL_CLAIM
PHI_TRAVERSAL != PHYSICAL_TRUTH
RECOVERY_BUNDLE != SEMANTIC_AUTHORITY
RECOVERY_HEAD != SOURCE_CURRENT_HEAD
ORACLE_REFERENCE != CONTROL_AUTHORITY
ORACLE_RECEIPT_COPY != ORACLE_LEDGER_APPEND
FRESH != TRUE
STALE != FALSE
SUGGESTED_SEARCH != EVIDENCE
ELIGIBLE != EXECUTED
CONTROL_INVOKES_COUNCIL != CONTROL_OWNS_COUNCIL
CONTROL_RECEIPT_COPY != NEXUS_WORLDSTORE_WRITE
VISIBLE_NEXUS_OUTPUT != HIDDEN_CHAIN_OF_THOUGHT
VISIBLE_OUTPUT != HIDDEN_CHAIN_OF_THOUGHT
HUMAN_CALLER == AI_CALLER_FOR_EPISTEMIC_AUTHORITY
CONTROL_MUST_NOT_REWRITE_ORACLE_HISTORY
CONTROL_MUST_NOT_CHANGE_NEXUS_VOTES
```

## Replay instead of chat amnesia

Phase 1B preserves an immutable offline run history bound to exact File refs, an exact Collection snapshot, explicit evidence/model references and deterministic lattice addresses. The minimum ARK bundle proves canonical storage reconstruction offline. Phase 3 adds verified references to committed NEXUS Council sessions and receipts. Phase 4 adds immutable, provenance-classified model-state records and deterministic cross-run configuration comparison without claiming deterministic replay of live stochastic inference or reconstruction of hidden cognition.

## Validation

Validation remains dependency-free and requires **Python 3.11 or newer**. CI currently uses Python 3.12.

```bash
python3 tools/validate_control.py
python3 -W default -m unittest discover -s tests -v
```

The manifest registers the Phase 1B storage/recovery layer, Phase 2 ORACLE adapter, Phase 3 NEXUS Council adapter, and Phase 4 model-state registry with their machine contracts, schemas, CLIs, and adversarial tests.

Phase 4 finalizes a previously provisional model-state schema with required persistent-registry, provenance, privacy, and epistemic-boundary fields; accordingly, the repository contract `schema_version` advances from `1.6.0` to `2.0.0` under the existing semantic-versioning policy.

All public schemas use **JSON Schema draft 2020-12**.

## Documentation map

- [`README4AI.md`](README4AI.md) — compact machine bootstrap.
- [`AGENTS.md`](AGENTS.md) — contributor/agent operating rules.
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — authority boundaries and system design.
- [`ROADMAP.md`](ROADMAP.md) — implementation sequence.
- [`SECURITY.md`](SECURITY.md) — privacy, redaction and control/storage threat boundaries.
- [`docs/PERSISTENT-STORAGE.md`](docs/PERSISTENT-STORAGE.md) — Files, Collections, snapshots and search.
- [`docs/LATTICE-MEMORY.md`](docs/LATTICE-MEMORY.md) — 27-cell interaction-memory model.
- [`docs/MODEL-STATE.md`](docs/MODEL-STATE.md) — implemented model-state registry, provenance, comparisons and archaeology export.
- [`docs/WEBUI.md`](docs/WEBUI.md) — planned WebUI including the pinned Phase 4 model-state label contract.
- [`docs/NEXUS-ORACLE.md`](docs/NEXUS-ORACLE.md) — orchestration boundary.
- [`docs/ARK-MINIMUM-BUNDLE.md`](docs/ARK-MINIMUM-BUNDLE.md) — one-run offline recovery gate.
- [`docs/ORACLE-ADAPTER.md`](docs/ORACLE-ADAPTER.md) — read-only evidence adapter.
- [`docs/NEXUS-ADAPTER.md`](docs/NEXUS-ADAPTER.md) — verified local Council adapter and governance gate.
- [`docs/PORTABLE-CONCAP-BUNDLES.md`](docs/PORTABLE-CONCAP-BUNDLES.md) — deterministic portable context bundles.
- [`ai/model-state-contract.json`](ai/model-state-contract.json) — machine-readable Phase 4 registry and UI-label contract.
- [`ai/nexus-adapter-contract.json`](ai/nexus-adapter-contract.json) — machine-readable NEXUS governance boundary.
- [`manifest.json`](manifest.json) — canonical machine map.

## License

QSOL-CONTROL is licensed under the **Mozilla Public License 2.0 (MPL-2.0)**. See [`LICENSE`](LICENSE).

## Status

- **PR #1:** Phase-0 architecture/contracts bootstrap — merged.
- **PR #2:** Phase-1A persistent Files/Collections, retrieval indexes, and DNA/lattice recovery projection — merged/integrated baseline.
- **PR #4:** portable CONCAP delivery — merged.
- **PR #5:** Phase-1B interaction/lattice persistence — merged.
- **PR #6:** minimum ARK recovery gate + Phase 2 read-only ORACLE adapter — merged.
- **PR #7:** Phase 3 NEXUS Council adapter — merged.
- **PR #8:** Phase 4 AI model-state registry — current implementation.

Phase 5 WebUI, the broader Phase 8 repository-level ARK package, and the network AI API remain sequenced in the ROADMAP.

---

**QSOL-CONTROL controls the machinery, not reality. If the Council unanimously votes that the Moon is made of cheese and the semantic index returns it at 0.999 similarity, CONTROL's job is to preserve both facts about the system — not update astronomy. A model-state hash is paperwork, not a séance.**
