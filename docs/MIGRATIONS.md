# Phase 10 Versioned Migration Policy

QSOL-CONTROL migrations are procedural compatibility operations, not semantic rewrites.

```text
MIGRATION != REINTERPRETATION
MIGRATION_RECEIPT != SEMANTIC_AUTHORITY
SOURCE_STATE != MUTATED_IN_PLACE
UNKNOWN_MAJOR != ASSUMED_COMPATIBLE
```

The machine policy is `ai/migration-policy.json`. The reference tool is:

```bash
python3 tools/migration.py validate
python3 tools/migration.py plan --from-version 2.5.0 --to-version 2.6.0 --json
```

## Rules

- The current repository contract is `2.6.0`.
- Supported automatic source versions are explicitly enumerated.
- A migration proceeds only through declared forward steps.
- Downgrades are rejected.
- Unknown contract majors are rejected and require manual review.
- Unknown same-major source versions are not guessed compatible.
- The source is preserved.
- In-place canonical-state rewrite is forbidden.
- Every plan emits a deterministic content-addressed receipt.
- A migration receipt proves only the declared procedure and identities. It does not
  confer semantic, evidentiary, or truth authority.

## Current declared steps

The `2.0.0` through `2.6.0` repository-contract line is additive at the canonical store
level. Current declared steps register new interfaces/contracts and do not require
rewriting existing canonical File, Collection, run, model-state, replay, or recovery
records.

That does **not** mean every future `2.x` change is automatically safe. Future steps
must be explicitly added to the policy and reviewed before the tool will plan them.

## Store migration

Phase 10 intentionally does not ship an in-place mutator. If a future storage migration
is necessary, the required shape is:

1. verify the source store under its source contract;
2. create a separate target workspace;
3. copy/transform only through a versioned migration implementation;
4. verify target identities and lineage;
5. emit a migration receipt binding source and target fingerprints;
6. retain the original source until the operator explicitly retires it.

```text
COPY_THEN_VERIFY != DELETE_SOURCE
HASH_MATCH != TRUTH
MIGRATED_RECORD != NEW_AUTHORITY
```
