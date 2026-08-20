# Phase 10 Reproducible Release Workflow

QSOL-CONTROL releases are deterministic source bundles with explicit integrity
receipts. A reproducible release proves byte identity for the declared source tree. It
does not prove scientific truth, live-model replayability, or publication authority.

```text
RELEASE_HASH != SEMANTIC_TRUTH
REPRODUCIBLE_BYTES != REPRODUCIBLE_LIVE_INFERENCE
RELEASE_BUNDLE != PUBLICATION_AUTHORITY
```

## Release bundle

The machine contract is `ai/release-contract.json`; inventory policy is
`release/release-inventory.json`.

Build from a clean checkout of the exact release commit:

```bash
python3 tools/release_bundle.py check
python3 tools/release_bundle.py build \
  --release-version 1.0.0 \
  --source-commit <40-lowercase-hex-release-commit> \
  --output ../QSOL-CONTROL-1.0.0.zip
python3 tools/release_bundle.py verify ../QSOL-CONTROL-1.0.0.zip
```

For reproducibility, run the build twice from byte-identical clean checkouts using the
same `release-version` and `source-commit`; the resulting ZIP SHA-256 values must match.

## Deterministic archive rules

- ZIP format with `ZIP_STORED` members only;
- no compression/decompression path;
- fixed member timestamp `1980-01-01 00:00:00`;
- fixed regular-file mode `0644`;
- empty ZIP/member comments and extras;
- UTF-8 byte-lexicographic member ordering;
- exact SHA-256 per source file;
- content-addressed `RELEASE.json`;
- source-tree SHA-256 over the ordered file inventory;
- unexpected/missing/duplicate/symlink/traversal members rejected;
- verification does not extract the archive.

## Why ZIP_STORED

CONTROL already uses deterministic ZIP output for portable CONCAP delivery, but no
compressed ZIP import is part of the canonical runtime. Phase 10 keeps release
verification equally conservative: compressed untrusted members are rejected, so a
release verifier cannot become a decompression-bomb surface merely because ZIP is a
convenient distribution container.

## Release inventory

The inventory includes canonical contracts, runtime code, schemas, tests, examples,
documentation, WebUI assets, composition pins, and the validation workflow. Generated
artifacts, Python caches, and host-specific files are excluded.

A clean checkout is part of the release procedure. If an unexpected file is placed
inside an inventoried root, it becomes visible in the source-tree fingerprint rather
than being silently ignored as part of canonical release content.

## Release readiness

`python3 tools/release_bundle.py check` requires:

- repository contract `2.6.0`;
- Phase 10 marked complete;
- AI bootstrap synchronized;
- migration/release contracts on the same target version;
- current changelog discipline;
- release checklist present.

This check complements, rather than replaces, the full CI suite and the human review
steps in `RELEASE-CHECKLIST.md`.
