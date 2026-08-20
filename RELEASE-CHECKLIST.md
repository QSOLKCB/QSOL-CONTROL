# QSOL-CONTROL Release Checklist

Use this checklist for every public release. A release is not complete merely because a
tag exists or CI is green.

## Source identity

- [ ] Start from a clean checkout of the exact release commit.
- [ ] Record the exact 40-hex source commit used by the release bundle.
- [ ] Confirm `manifest.json`, `README4AI.md`, `ROADMAP.md`, and `CHANGELOG.md` agree on the repository contract and phase status.
- [ ] Confirm deferred/non-goal items remain explicitly deferred rather than silently claimed implemented.

## Validation

- [ ] `python3 tools/validate_control.py`
- [ ] `python3 tools/validate_restore_contracts.py`
- [ ] `python3 tools/agent_api.py --help`
- [ ] `python3 tools/int_composition.py validate`
- [ ] `python3 tools/migration.py validate`
- [ ] `python3 tools/adversarial_storage.py --iterations 256`
- [ ] `python3 -W default -m unittest discover -s tests -v`

## Security and secret review

- [ ] Review the Phase 10 network/browser threat model and confirm the release still defaults to loopback/local stdio.
- [ ] Confirm remote multi-user deployment is not accidentally enabled.
- [ ] Run the File metadata secret audit against any CONTROL store used to generate examples or recovery artifacts.
- [ ] Confirm no credentials, private keys, cookies, bearer tokens, hidden chain-of-thought, or private corpus bytes are present in tracked release content.
- [ ] Confirm compressed untrusted archive input remains default-deny; release verification must not decompress members.

## Migration

- [ ] Confirm `ai/migration-policy.json` targets the released repository contract version.
- [ ] Confirm every supported migration step is explicit, forward-only, source-preserving, and non-in-place.
- [ ] Confirm no new automatic compatibility claim was added for an unknown major or undeclared source version.

## Reproducible release bundle

- [ ] `python3 tools/release_bundle.py check`
- [ ] Build the release bundle twice from byte-identical clean checkouts using the same release version and source commit.
- [ ] Confirm both release ZIP SHA-256 values are byte-identical.
- [ ] `python3 tools/release_bundle.py verify <bundle.zip>` succeeds for both outputs.
- [ ] Confirm `RELEASE.json` source-tree SHA-256 and per-file SHA-256 identities match the bundled bytes.
- [ ] Confirm release ZIP members are `ZIP_STORED` only and verification performs no extraction/decompression.

## Changelog and publication discipline

- [ ] Move completed Unreleased notes into the intended release version/date only when the release is actually being cut.
- [ ] Keep CHANGELOG entries factual: merged, released, executed, synthetic, and deferred states must remain distinct.
- [ ] Prepare release notes from the exact merged/release state, not from an earlier PR description.
- [ ] Create the tag/release only after all required checks and review gates are green.
- [ ] Verify the published release/tag points at the intended commit.

```text
MERGED_MAIN != PUBLISHED_RELEASE
GREEN_CI != RELEASED
RELEASE_BUNDLE != PUBLICATION_AUTHORITY
RELEASE_HASH != SEMANTIC_TRUTH
```
