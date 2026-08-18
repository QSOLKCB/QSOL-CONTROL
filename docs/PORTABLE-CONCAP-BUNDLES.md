# Portable CONCAP Bundles

QSOL-CONTROL can construct deterministic portable CONCAP bundles from explicit private export specifications. Portable bundles let an authorized consumer load approved context objects without receiving access to the private repository that authored them.

## Existing object format, new delivery layer

Portable CONCAP objects remain ordinary deterministic `QSOL-RESTORE-DAT/1` objects.

```text
private source bytes
      |
      | explicit qsol-control-concap-export-spec/1
      v
QSOL-CONTROL
      |
      | pack QSOL-RESTORE-DAT/1
      | omit private source_ref metadata
      v
portable bundle
  BOOTSTRAP.json
  OBJECTS.json
  objects/sha256/<prefix>/<digest>.dat
```

No second payload container is introduced.

## Export specification

A private export spec explicitly binds versioned CONCAP role ids to existing CONTROL restore pack specifications.

```json
{
  "protocol": "qsol-control-concap-export-spec/1",
  "schema_version": "1.0.0",
  "bundle_id": "example_context",
  "export_class": "RESTRICTED",
  "sensitive_export_acknowledged": true,
  "bindings": [
    {
      "role_id": "concap.identity.core/1",
      "pack_spec": "restore/specs/identity.pack.json"
    }
  ],
  "boundaries": [
    "PRIVATE_SOURCE != PORTABLE_BUNDLE",
    "PORTABLE_BUNDLE != PUBLICATION",
    "RESTRICTED_BUNDLE != ENCRYPTED_BUNDLE",
    "SOURCE_REF_STRIPPED != SOURCE_BYTES_ANONYMIZED",
    "MODEL_CAN_LOAD_OBJECT != MODEL_CAN_ACCESS_SOURCE_REPOSITORY",
    "QSOL-RESTORE-DAT/1 != ENCRYPTION"
  ]
}
```

Bindings must be strictly sorted by UTF-8 role id. Unknown fields fail closed. The export class must be at least as restrictive as every included source entry. A RESTRICTED export requires explicit acknowledgement.

## Private metadata stripping

Existing private restore pack specs may contain `source_ref` values naming a private repository or source path. The portable exporter intentionally does not copy `source_ref` into the new object's embedded restore manifest.

Payload bytes selected by the explicit pack spec are preserved exactly.

```text
SOURCE_REF_STRIPPED != SOURCE_BYTES_ANONYMIZED
```

If the payload itself contains private names, paths, identities, or secrets, those bytes remain present. The export specification is therefore a deliberate disclosure boundary, not an anonymizer.

## Object index

`OBJECTS.json` uses the public `QSOL-CONCAP/OBJECT-INDEX/1` contract also consumed by QSOL-THOTH.

Each object has:

- `object_id = sha256(exact QSOL-RESTORE-DAT/1 bytes)`;
- byte size;
- media type;
- container id;
- a relative content-derived path.

```text
objects/sha256/<first-two-hex>/<64-hex>.dat
```

One object can satisfy several semantic roles. Reusing one pack spec for several roles therefore produces one object plus several role bindings.

`projection_sha256` binds the exact `objects` and `role_bindings` projection. `index_id` binds the full canonical index body.

## Bootstrap

`BOOTSTRAP.json` is intentionally small. It binds the exact bytes of `OBJECTS.json`, its canonical index id, bundle class, and declared object/role counts.

A model can be handed a directory or archive containing only:

```text
BOOTSTRAP.json
OBJECTS.json
objects/
```

It does not need a Git checkout.

## Build

```bash
python3 tools/concap_bundle.py build \
  --source-root /private/source/checkout \
  --export-spec /private/source/checkout/restore/CONCAP-EXPORT.spec.json \
  --output-dir /tmp/qsol-portable
```

Optional deterministic ZIP:

```bash
python3 tools/concap_bundle.py build \
  --source-root /private/source/checkout \
  --export-spec /private/source/checkout/restore/CONCAP-EXPORT.spec.json \
  --output-dir /tmp/qsol-portable \
  --zip-output /tmp/qsol-portable.zip
```

The ZIP uses sorted entries, stored bytes, fixed timestamps, fixed permissions, and no comments. Byte-identical bundle inputs therefore produce byte-identical ZIP bytes.

## Verify

```bash
python3 tools/concap_bundle.py verify --bundle /tmp/qsol-portable
```

Verification checks:

- exact bootstrap/index shape;
- exact index byte hash;
- acyclic index identity;
- projection hash;
- content-derived object paths;
- object byte size and SHA-256;
- `QSOL-RESTORE-DAT/1` fixed-point verification;
- absence of `source_ref` in portable object manifests;
- bundle privacy class versus contained entry privacy;
- absence of unexpected files and symlinks.

## Transport neutrality

Bundle files can be copied byte-for-byte through:

- local directories;
- removable storage;
- deterministic ZIP archives;
- LAN file shares;
- static HTTP object stores;
- authenticated capability relays.

Transport URLs, bearer tokens, signed-URL expiries and network state are not canonical bundle fields.

```text
OBJECT_IDENTITY != TRANSPORT_LOCATION
PORTABLE_BUNDLE != PUBLICATION
```

A RESTRICTED bundle requires a restricted transport or an appropriate encrypted outer channel. The `.dat` format itself is not encryption.

## Trust boundary

```text
PRIVATE SOURCE REPOSITORY
        |
        | explicit export
        v
PORTABLE VERIFIED OBJECTS
        |
---------------- trust boundary ----------------
        |
        v
MODEL / CONSUMER
```

Core invariant:

```text
MODEL_CAN_RECONSTRUCT_CONTEXT
!=
MODEL_CAN_ACCESS_PRIVATE_SOURCE
```
