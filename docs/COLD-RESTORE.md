# Cold restore capsules

QSOL-CONTROL implements the deterministic byte/container machinery used to move a reviewed recovery substrate between repositories and a cold-start consumer.

It does **not** define what memories are true, which records are important, or whether a restored model is the same model instance.

```text
QSOL-ARK      defines recovery/MRS semantics
QSOL-CONTEXT  supplies curated personal/working continuity records
QSOL-CORPUS   supplies optional archival interaction history
LATTICE       supplies structural profile/traversal conformance
QSOL-CONTROL  packs, verifies, unpacks and projects bytes
```

## QSOL-RESTORE-DAT/1

The `.dat` extension is application-defined. CONTROL therefore defines an explicit container instead of relying on an unspecified generic DAT interpretation.

Binary layout:

```text
MAGIC:        ASCII `QSOL-RESTORE-DAT/1` + NUL
MANIFEST_LEN: unsigned 64-bit big-endian integer
MANIFEST:     canonical UTF-8 JSON
PAYLOAD:      concatenated entry bytes
```

Entries are sorted by UTF-8 bytes of `logical_path` before packing. Each entry records:

- canonical relative logical path;
- kind;
- privacy class;
- recovery class;
- fixed integer φ-shell value;
- byte length;
- SHA-256;
- optional source reference.

The container itself carries a content-derived `manifest_id`, payload SHA-256, exact restore schedule and epistemic boundaries. Repacking verified entries must reproduce byte-identical capsule bytes.

## Recovery classes

The recovery scheduler uses the names from the QEC invariant lineage as a deterministic ordering profile:

```text
NEAR_SHELL       1000
MID_SHELL        1618
OUTER_SHELL      2618
RESONANCE_NODE   4236
WIGGLE_ZONE      6854
```

Values are stored as integer thousandths, not binary floating point.

The golden recurrence is pinned as:

```text
1000 + 1618 = 2618
1618 + 2618 = 4236
2618 + 4236 = 6854
```

This ordering is a software recovery convention. It is **not** evidence that φ is physically optimal storage.

`QSOL-E8-INV-005` contributes the fixed five-class naming contract. The three primary classes are NEAR/MID/OUTER; RESONANCE_NODE and WIGGLE_ZONE are boundary/optional classes.

`QSOL-OURO-INV-006` contributes the fixed-point recovery idea: parse -> verify -> repack must return exactly the original bytes for a canonical capsule. No hidden state participates.

## DNA/lattice projection

A verified `.dat` capsule may be encoded using CONTROL's existing:

```text
qsol.dna-2bit-codon64/1
qsol-3x3x3-sierpinski-derived-memory/1
qsol.phi-stride-27/1
```

The DNA form is redundant and reversible:

```text
DAT BYTES = canonical recovery object
DNA       = derived recovery projection
LATTICE   = structural distribution/traversal
```

Do not call the DNA representation compression, encryption, biological storage, cognition, or truth.

## Multiple capsules + bootstrap index

Personal continuity should normally be split into small purpose-specific capsules rather than one giant file, for example:

```text
restore/capsules/identity.dat
restore/capsules/working-style.dat
restore/capsules/projects.dat
restore/capsules/research.dat
restore/capsules/continuity.dat
```

A small `RESTORE-BOOTSTRAP.json` in the source repository points to each capsule by repository, exact commit, path and SHA-256. This makes the model-ingestion surface inspectable while keeping the capsule bytes independently verifiable.

For a private repository, a no-login model session cannot fetch those URLs itself. A cold-start test therefore uploads the bootstrap plus declared `.dat` files explicitly. That is desirable: the test cannot accidentally inherit private repository access.

## CLI

Create a pack specification next to the source files:

```json
{
  "protocol": "qsol-control-restore-pack-spec/1",
  "entries": [
    {
      "logical_path": "identity/context.json",
      "source_path": "identity/context.json",
      "kind": "json",
      "privacy_class": "RESTRICTED",
      "recovery_class": "NEAR_SHELL",
      "source_ref": "QSOL-CONTEXT:identity/context.json"
    }
  ]
}
```

Then:

```bash
python3 tools/restore_cli.py pack --spec restore-pack.json --output identity.dat
python3 tools/restore_cli.py verify identity.dat
python3 tools/restore_cli.py inspect identity.dat
python3 tools/restore_cli.py unpack identity.dat --output-dir restored/
```

A RESTRICTED capsule may only be exported into reversible DNA form after two explicit acknowledgements **and** actor attribution. A successful export appends a non-canonical local JSONL audit event:

```bash
python3 tools/restore_cli.py dna-export identity.dat \
  --output identity.dna.json \
  --allow-restricted \
  --acknowledge-reversible-sensitive-export \
  --actor trent \
  --audit-log .qsol-control-restore-audit.jsonl

python3 tools/restore_cli.py dna-decode identity.dna.json --output identity-restored.dat
```

Preview validation without writing projection bytes or an audit record:

```bash
python3 tools/restore_cli.py dna-export identity.dat \
  --output identity.dna.json \
  --allow-restricted \
  --acknowledge-reversible-sensitive-export \
  --actor trent \
  --dry-run
```

Audit records are operational receipts, not canonical restore data and not evidence that the exported content is true.

## Cold-start acceptance test

Do **not** delete a live account to test disaster recovery.

Use a clean browser/profile or no-login model session with no pre-existing user memory. Provide only the bootstrap and its declared capsules. Score reconstruction against the canonical source snapshot.

The acceptance target is **personal context reconstruction**, not model-instance reconstruction.

```text
RESTORE_CAPSULE != MODEL_MEMORY
RESTORED_CONTEXT != ORIGINAL_ASSISTANT_INSTANCE
RESTORE_SUCCESS != FACTUAL_TRUTH
DNA_PROJECTION != CANONICAL_SOURCE
```
