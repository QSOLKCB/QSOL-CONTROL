# Changelog

All notable changes to QSOL-CONTROL are recorded here.

The changelog distinguishes implementation, merge, release, execution, and synthetic
conformance states. A merged PR is not a published release, and a green CI run is not a
release event.

```text
MERGED_MAIN != PUBLISHED_RELEASE
GREEN_CI != RELEASED
SYNTHETIC_CONFORMANCE != EXECUTED
```

## Contract versioning

Public repository contracts use `MAJOR.MINOR.PATCH` semantics declared in
`manifest.json`:

- **major**: breaking schema or authority-contract change;
- **minor**: backward-compatible capability or contract extension;
- **patch**: correction/clarification that does not change accepted contract meaning.

JSON Schemas use Draft 2020-12. Lattice profiles and parent-system protocols remain
independently versioned and are never silently substituted.

## Unreleased

### Added — PR #15 post-roadmap deferred resolution

- Separately versioned `qsol-control-post-roadmap-extensions/1` machine manifest bound to
  the completed core contract `2.6.0`.
- Optional authenticated remote Agent API gateway with digest-only bearer credentials,
  fixed principal-to-caller identity mapping, per-principal operation allowlists, Host
  allowlisting, no CORS, and mandatory TLS for non-loopback binds.
- Native iOS/SwiftUI and Android/Kotlin reference clients that remain thin HTTPS
  transports over `qsol-control-remote-request/1` rather than reimplementing CONTROL.
- External consensus coordination adapter with content-addressed mutation intents and
  exact quorum-receipt validation; CONTROL does not embed a consensus algorithm and the
  adapter does not directly mutate CONTROL storage.
- `ai/permanent-nongoals.json` making automatic truth scoring, hidden chain-of-thought
  capture, literal lattice-cognition claims, biological DNA-codec claims, and physical
  optimality claims for φ traversal permanent prohibitions rather than open backlog.
- Reproducible source-release inventory now includes the extension and native-client
  source roots while retaining core repository contract `2.6.0`.

### Boundaries — post-roadmap extensions

```text
CORE_2_6_0 != EXTENSION_SURFACE
REMOTE_ACCESS != EPISTEMIC_PRIVILEGE
AUTHENTICATED != AUTHORITATIVE
MOBILE_CLIENT != CONTROL_AUTHORITY
CONSENSUS_RECEIPT != SEMANTIC_AUTHORITY
QUORUM != TRUTH
AUTOMATIC_TRUTH_SCORING = FORBIDDEN
HIDDEN_CHAIN_OF_THOUGHT_CAPTURE = FORBIDDEN
```

### Added — Phase 10 hardening and release discipline

- Explicit network/browser threat model for the implemented loopback WebUI and local
  JSONL/stdio agent API, including residual-risk and remote-deployment nonclaims.
- Read/import-side File and Collection metadata secret audit with credential-labelled
  key, token-marker, credential-bearing locator, duplicate-JSON, identity, and size
  checks.
- Default-deny compressed-untrusted-archive policy; Phase 10 release verification
  accepts bounded `ZIP_STORED` members only and performs no extraction/decompression.
- Deterministic adversarial/fuzz-style storage battery with a fixed seed and CI gate.
- Versioned `qsol-control-migration/1` policy with forward-only declared steps,
  source preservation, no in-place rewrite, and content-addressed migration receipts.
- Reproducible `qsol-control-release-bundle/1` source ZIP with fixed metadata,
  per-file SHA-256, source-tree SHA-256, content-addressed `RELEASE.json`, deterministic
  inventory, and bounded verification.
- `RELEASE-CHECKLIST.md` and explicit release/changelog discipline.
- Repository contract advances additively to `2.6.0` and roadmap completion through
  Phase 10.

### Security

- Compressed untrusted imports remain unsupported by default rather than being
  implicitly accepted through ZIP convenience tooling.
- Release archive verification rejects compression, traversal, symlinks, duplicates,
  oversized archives/members, and unexpected member sets.
- Imported/rehashed File metadata containing credential-labelled material is detectable
  without silently rewriting canonical history.

### Validation

The current validation gate is:

```bash
python3 tools/validate_control.py
python3 tools/validate_restore_contracts.py
python3 tools/agent_api.py --help
python3 tools/int_composition.py validate
python3 tools/migration.py validate
python3 tools/adversarial_storage.py --iterations 256
python3 tools/release_bundle.py check
python3 tools/validate_extensions.py
python3 -W default -m unittest discover -s tests -v
```

## Roadmap implementation history

- **Phase 0** — architecture, authority contracts, human/AI bootstrap.
- **Phase 1A** — content-addressed Files, immutable Collections/snapshots, deterministic
  lexical/vector retrieval, DNA/lattice projection, portable CONCAP delivery.
- **Phase 1B** — immutable runs/events, deterministic lattice lineage, fingerprints,
  minimum ARK recovery bundle.
- **Phase 2** — read-only ORACLE adapter and timelock view.
- **Phase 3** — governance-preserving NEXUS Council adapter.
- **Phase 4** — model-state reproducibility registry and archaeology export.
- **Phase 5** — local loopback Human WebUI.
- **Phase 6** — structured JSONL/stdio AI/agent API.
- **Phase 7** — classified replay and longitudinal research timelines.
- **Phase 8** — repository-level ARK recovery bridge.
- **Phase 9** — exact-pinned INT-style cross-repository composition batteries.
- **Phase 10** — hardening, migration policy, deterministic release machinery, and
  release discipline.
- **Post-roadmap PR #15** — optional remote/mobile/consensus extension surfaces plus
  permanent non-goal resolution.

Release-specific version headings are added **only when a release is actually cut**;
completed Unreleased entries are then moved under that exact version/date according to
`RELEASE-CHECKLIST.md`.