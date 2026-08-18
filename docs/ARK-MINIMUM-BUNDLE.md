# QSOL-CONTROL Minimum ARK Recovery Bundle

## Purpose

Phase 1B closes its offline persistence gate with `qsol-control-ark-minimum-bundle/1`: the smallest deterministic CONTROL storage package intended to reconstruct and verify one interaction run without the original CONTROL store, WebUI, search engine, ORACLE, NEXUS, or network access.

The bundle reuses the existing `QSOL-RESTORE-DAT/1` container. It is a recovery transport, not a new authority-bearing source.

```text
RECOVERY_BUNDLE != SEMANTIC_AUTHORITY
HASH_INTEGRITY != EVIDENCE_AUTHORITY
RESTORED_CONTEXT != ORIGINAL_ASSISTANT_INSTANCE
```

## Minimum contents

For one `run_id`, the bundle includes:

- `CONTROL-RECOVERY.json`, the deterministic reconstruction bootstrap;
- `lattice/profile.json`, the exact top-level lattice-address contract;
- the immutable `qsol-control-interaction/2` run record;
- the complete append-only `qsol-control-run-event/1` chain;
- every File record and raw content-addressed object referenced by the run or its events;
- when a Collection is bound, its immutable descriptor and the snapshot chain from the exact run-bound snapshot back to revision 0;
- the File records and raw objects required by those exported Collection snapshots.

Derived lexical indexes, semantic-vector indexes, DNA projections, WebUI state, and live service connections are deliberately excluded from the minimum set.

## Exact historical snapshot semantics

A run binds to an exact Collection snapshot, not to whatever `HEAD` happens to contain years later.

If the source Collection has advanced after the run:

```text
source HEAD today          -> snapshot N
run-bound historical state -> snapshot K
recovered HEAD             -> snapshot K
```

The reconstruction deliberately sets its local recovery `HEAD` to snapshot K so the recovered store reproduces the historical state the run actually consumed.

```text
RECOVERY_HEAD != SOURCE_CURRENT_HEAD
```

This does not rewrite the source Collection. The recovery store is a new local reconstruction.

## Verification gate

`verify_ark_bundle()` performs two independent classes of checks:

1. `QSOL-RESTORE-DAT/1` container integrity and canonical fixed-point reconstruction;
2. semantic storage reconstruction into a fresh temporary CONTROL store, followed by run/event/File/raw-object/Collection-lineage verification and comparison with the original run fingerprint.

The Collection lineage must reach revision 0. Referenced object bytes must hash to the identities declared by their File records.

A container that is internally well-formed but omits a required raw object therefore fails the CONTROL recovery verification.

## Privacy

The minimum bundle is at least `INTERNAL`. The strictest privacy class among required Files/Collections propagates to the bundle.

For `RESTRICTED` output, the CLI requires all of:

```text
--allow-restricted
--acknowledge-recovery-export
--actor <identity>
```

Local export is written mode `0600`. This is filesystem access control, not encryption.

## CLI

```bash
python3 tools/ark_bundle.py export \
  --root .store \
  <run_id> \
  --output control-run.dat

python3 tools/ark_bundle.py verify control-run.dat

python3 tools/ark_bundle.py restore \
  control-run.dat \
  --target recovered-store
```

Restore refuses an existing target path rather than merging recovered history into unknown local state.

## Relationship to Phase 8

This closes the **Phase 1B minimum-storage export gate** and defines the minimum recoverable CONTROL bundle used by the broader Phase 8 bridge.

Phase 8 may later add richer recovery material such as optional DNA projections, search-index descriptors, broader model-state registry exports, plain-text maps, and constrained-environment packaging. Those additions are not required to prove the Phase 1B offline round trip.
