# Phase 9 — INT composition batteries

QSOL-CONTROL Phase 9 adds deterministic **CONTROL-local conformance receipts** using the composition discipline established by QSOL-INT.

It does **not** move QSOL-INT composition authority into CONTROL.

```text
QSOL-INT COMPOSES
QSOL-CONTROL OPERATES

COMPATIBILITY_RECEIPT != PARENT_AUTHORITY
BATTERY_PASS != TRUTH
COMPATIBLE != TRUE
```

## Pinned parent evidence

Phase 9 binds exact parent evidence in `composition/parent-pins.json`:

| Parent | Pinned commit | Machine artifact |
| --- | --- | --- |
| QSOL-INT methodology | `e8c509b93ae39ad784b4f739bf21b27aa41201bf` | `compatibility/reports/pinned-bootstrap.json` |
| QSOL-ORACLE | `3c8a0b39893bd3a7eeb0db6530aa5ed8ad0e664e` | `manifest.json` |
| QSOL-NEXUS | `839303ea512631e527073682343341742cead975` | `README4AI.md` |
| QSOL-THOTH | `03f6bdf063b7fb36fb13cd3d12e6d89dc8407b47` | `ai/concap-compatibility.json` |

Every artifact also records its exact Git blob SHA-1. CONTROL's local ORACLE, NEXUS and portable-CONCAP contract files are independently blob-pinned.

The receipt scope is always:

```text
pinned_parent_evidence_only
```

A pinned receipt never implies that a later parent commit is compatible.

## Run the batteries

```bash
python3 tools/int_composition.py validate
python3 tools/int_composition.py run
python3 tools/int_composition.py run --json
```

The report is canonical JSON, content-addressed, deterministic, and contains exactly eleven declared cases.

## Battery surface

1. CONTROL ↔ ORACLE pinned compatibility.
2. CONTROL ↔ NEXUS pinned compatibility.
3. CONTROL ↔ THOTH portable-CONCAP pinned compatibility.
4. Authority non-escalation.
5. Stale-parent handling.
6. Vote/evidence separation.
7. Lattice-memory/content-canonical separation.
8. Model-state/model-identity separation.
9. Collection/search-index authority separation.
10. DNA/lattice projection/raw-byte canonical separation.
11. Schema/protocol-version drift.

The first three emit exact parent/local contract receipts. The remaining cases test CONTROL's composition boundaries across already-implemented phases.

## Current-parent observations

The deterministic baseline does not access the network and therefore reports:

```text
current_parent_compatibility = not_claimed
```

A caller may separately supply an observed identity file:

```json
{
  "protocol": "qsol-control-int-observed-parents/1",
  "parents": {
    "oracle": {
      "available": true,
      "commit": "<40 hex>",
      "git_blob_sha1": "<40 hex>",
      "protocol": "QSOL-ORACLE/1",
      "schema_version": "1.2.0"
    }
  }
}
```

Then run:

```bash
python3 tools/int_composition.py check-drift \
  --observed-parents observed.json \
  --json
```

Classification is fail-closed:

- exact commit + blob: `NO_DRIFT`, compatible for that observation;
- missing source: `SOURCE_UNAVAILABLE`, compatibility unknown, review required;
- changed commit/blob with same major: `CONTENT_DRIFT`, compatibility untested, review required;
- schema-major change: `SCHEMA_DRIFT`, compatibility untested, review required;
- protocol-major change: `BREAKING_DRIFT`, incompatible, review required.

No command silently rewrites `composition/parent-pins.json`.

```text
DRIFT_IS_NEVER_SILENTLY_ACCEPTED
UNAVAILABLE != CONTRADICTED
PINNED_PARENT_COMPATIBILITY != CURRENT_PARENT_COMPATIBILITY
```

## Separation batteries

### Authority

Composition must not promote adapter compatibility, storage integrity, retrieval similarity, votes, or successful reconstruction into semantic authority.

### Vote and evidence

NEXUS Council consensus remains independent of ORACLE evidence state.

```text
VOTE != EVIDENCE
CONSENSUS != EVIDENCE
CONSENSUS != TRUTH
```

### Memory and canonical state

The lattice remains deterministic storage/navigation metadata. It does not replace content identity, provenance, or canonical record lineage.

### Model state and identity

Model-state records are reproducibility metadata. A model hash is an identity claim about supplied bytes or descriptors, not those bytes themselves and not a model mind.

```text
MODEL_STATE != MODEL_MIND
HASH_IDENTITY != ARTIFACT_BYTES
```

### Collections and indexes

Collection snapshots are canonical membership history. Search indexes are derived, rebuildable, and authority-free.

```text
INDEX != CANONICAL_MEMORY
SEARCH_SCORE != TRUTH
```

### DNA projection and raw bytes

Raw File object bytes remain canonical. DNA/lattice forms remain reversible derived projections.

```text
RAW_OBJECT_BYTES = CANONICAL
DNA_PROJECTION != CANONICAL_SOURCE
```

## Relationship to QSOL-INT

The methodology reference is QSOL-INT's pinned compatibility report and its governing rule:

```text
INTEGRATION_MUST_NOT_INCREASE_SEMANTIC_AUTHORITY
```

CONTROL may prove that its own adapter and storage contracts conform to the pinned composition expectations. It may not declare itself the owner of QSOL-INT's broader composition semantics.
