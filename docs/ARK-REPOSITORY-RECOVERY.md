# QSOL-CONTROL Phase 8 Repository Recovery

## Purpose

Phase 8 extends the existing one-run ARK minimum bundle into a repository-level recovery bridge.

The narrow `qsol-control-ark-minimum-bundle/1` remains unchanged and useful when only one interaction lineage must survive. The broader `qsol-control-ark-repository-recovery/1` package preserves the canonical CONTROL storage state needed to reconstruct the research system itself.

```text
RECOVERY_PACKAGE != SEMANTIC_AUTHORITY
RAW_OBJECT_BYTES = CANONICAL
SEARCH_INDEX_DESCRIPTOR != CANONICAL_MEMORY
DNA_PROJECTION != CANONICAL_SOURCE
LATTICE_ADDRESS != TRUTH
HASH_INTEGRITY != EVIDENCE_AUTHORITY
RESTORED_CONTEXT != ORIGINAL_ASSISTANT_INSTANCE
```

QSOL-ARK remains the recovery-semantics authority. CONTROL owns only its packaging, validation, and reconstruction mechanics.

## Package shape

A repository recovery export is a deterministic directory:

```text
CONTROL-recovery-package/
├── CONTROL-REPOSITORY-RECOVERY.json
├── RECOVERY-MAP.txt
└── capsules/
    ├── 000000.dat
    ├── 000001.dat
    └── ...
```

Each `.dat` file remains an ordinary bounded `QSOL-RESTORE-DAT/1` capsule. Phase 8 does not create a new container format merely because the repository can exceed one capsule's entry/payload budgets.

Capsules are ordered deterministically. The top-level bootstrap binds their paths, SHA-256 hashes, sizes, entry counts, the canonical source inventory fingerprint, package privacy class, and the hash of the human-readable recovery map.

## Canonical recovered state

The source fingerprint covers exact recoverable CONTROL state:

- raw File object bytes;
- immutable File records;
- Collection descriptors;
- all Collection membership snapshots;
- current Collection `HEAD` pointers;
- immutable interaction run records;
- append-only run events;
- run `HEAD` pointers;
- model-state records;
- Phase 7 replay records;
- Phase 7 deterministic replay reports.

Public JSON Schemas and the lattice descriptor are included as supporting recovery contracts. They are verified and restored alongside the package but are not reinterpreted as evidence.

Audit-event history remains outside the Phase 8 canonical source fingerprint. That is an explicit current policy, not evidence that audit records are unimportant or public.

## Derived recovery aids

Two classes of derived material may be included explicitly:

### Search-index descriptors

`--include-index-descriptors` includes descriptors that preserve index identity, engine, exact Collection snapshot binding, tokenizer/embedding identity and fingerprints where applicable.

The lexical document-frequency payload and semantic vectors are deliberately omitted.

Descriptors are restored under:

```text
optional/index-descriptors/
```

They are never written into `store/records/indexes/` by the Phase 8 reconstructor.

```text
INDEX_DESCRIPTOR != INDEX_PAYLOAD
INDEX != CANONICAL_MEMORY
SEARCH_SCORE != TRUTH
```

### DNA/lattice projections

`--include-dna` optionally adds reversible deterministic projections for Files within the configured size ceiling.

They are restored under:

```text
optional/dna/
```

Raw object bytes remain canonical. A DNA projection cannot substitute for missing canonical bytes during normal reconstruction.

```text
DNA_PROJECTION = DERIVED
ENCODED != ENCRYPTED
CODON_FREQUENCY != EVIDENCE
```

## Large raw objects

One `QSOL-RESTORE-DAT/1` entry is intentionally bounded. A repository may contain a raw object larger than the Phase 8 per-capsule transport budget.

Large raw objects are therefore split into deterministic transport chunks. A transport manifest records:

- target canonical object path;
- original object SHA-256;
- original size;
- ordered chunk paths;
- per-chunk SHA-256 and size.

The reconstructor streams those chunks into the canonical object path and verifies the complete original SHA-256 and size before CONTROL storage verification occurs.

Transport chunking never changes the canonical object identity.

## Export

```bash
python3 tools/repository_recovery.py export \
  --root .qsol-control-store \
  --output control-recovery
```

Add optional derived aids:

```bash
python3 tools/repository_recovery.py export \
  --root .qsol-control-store \
  --output control-recovery \
  --include-index-descriptors \
  --include-dna
```

For `RESTRICTED` source state, export requires all three:

```text
--allow-restricted
--acknowledge-recovery-export
--actor <operator identity>
```

The strictest canonical source classification determines the package class, with a minimum package class of `INTERNAL`.

## Verify

```bash
python3 tools/repository_recovery.py verify control-recovery
```

Verification is not a shallow archive checksum. It:

1. verifies the bootstrap identity and recovery-map hash;
2. verifies the exact top-level package inventory;
3. verifies every capsule hash, size, entry count and `QSOL-RESTORE-DAT/1` fixed point;
4. rejects duplicate logical paths across capsules;
5. reconstructs into a fresh temporary directory;
6. reassembles and verifies large raw objects;
7. verifies File/object identities and Collection privacy/lineage;
8. verifies every run/event lineage;
9. verifies model-state identity and run linkage;
10. semantically verifies replay records/reports and referenced runs;
11. verifies that derived search indexes did not enter the canonical store;
12. recomputes the canonical source inventory fingerprint and requires exact equality.

A successful report therefore establishes deterministic integrity/reconstruction of the declared CONTROL state. It does not establish the truth of any stored research claim.

## Restore

```bash
python3 tools/repository_recovery.py restore control-recovery \
  --target recovered-control
```

The target must not already exist. Recovery stages into a temporary sibling directory, verifies the reconstruction, then atomically moves the finished directory into place.

The result contains:

```text
recovered-control/
├── store/                 canonical reconstructed CONTROL store
├── schemas/               supporting JSON Schemas
├── lattice/               supporting lattice profile
├── optional/              optional derived aids, if exported
├── CONTROL-REPOSITORY-RECOVERY.json
└── RECOVERY-MAP.txt
```

## Constrained recovery

Phase 8 includes a constrained fixture under:

```text
examples/recovery/constrained-store.fixture.json
```

The test reconstructs with:

```text
network_available = false
webui_available = false
search_engine_available = false
python_standard_library_only = true
```

The WebUI and original search engine are not reconstruction dependencies. Search indexes are rebuildable projections, not canonical memory.

## Relationship to earlier recovery machinery

```text
qsol-control-ark-minimum-bundle/1
    one run + dependencies
    exact run snapshot recovery
    remains stable

qsol-control-ark-repository-recovery/1
    whole recoverable CONTROL storage state
    multiple bounded QSOL-RESTORE-DAT/1 capsules
    model-state + replay continuity
    current Collection HEADs + full snapshot history
    optional derived recovery aids
```

Both formats preserve the same authority rule:

```text
CONTROL_PACKAGES_RECOVERY != CONTROL_OWNS_RECOVERY_AUTHORITY
```
