# QSOL-CONTROL WebUI

## Status

Phase 5 is implemented as a **local loopback human operator surface**. Phase 7 extends the existing Replay / Compare view with classified replay execution and recurring-question longitudinal research without creating a second browser authority layer.

```text
runtime: webui/server.py
launcher: tools/webui.py
browser: webui/static/index.html
contract: ai/webui-contract.json
```

It is deliberately standard-library-only on the server and framework-free in the browser. This keeps the operator layer small enough to inspect and avoids creating a second application stack that quietly duplicates CONTROL's authority-bearing boundaries.

Remote multi-user deployment is not implemented.

## Start it

Storage-only:

```bash
python3 tools/webui.py \
  --root .qsol-control-store
```

With the read-only ORACLE adapter:

```bash
python3 tools/webui.py \
  --root .qsol-control-store \
  --oracle-root /path/to/QSOL-ORACLE
```

With ORACLE and the local NEXUS JSONL runtime:

```bash
python3 tools/webui.py \
  --root .qsol-control-store \
  --oracle-root /path/to/QSOL-ORACLE \
  --nexus-command-json '["python3","-m","nexus_runtime","--world","/secure/nexus-world"]' \
  --nexus-members council-members.json
```

Default address:

```text
http://127.0.0.1:8765
```

The Phase 5 server accepts loopback binds only:

```text
127.0.0.1
::1
localhost
```

## Browser boundary

The WebUI is a browser surface over existing CONTROL runtimes. It is not a new source of evidence, truth, Council governance, or model cognition.

```text
CONTROL_DISPLAY != AUTHORITY
CONTROL_OPERATION != TRUTH
VOTE != EVIDENCE
CONSENSUS != TRUTH
SEARCH_SCORE != TRUTH
SEMANTIC_SIMILARITY != EVIDENCE_STRENGTH
MODEL_STATE != MODEL_MIND
VISIBLE_OUTPUT != HIDDEN_CHAIN_OF_THOUGHT
RUNTIME_METADATA != CONSCIOUSNESS
PROVIDER_REPORTED != LOCALLY_VERIFIED
MODEL_STATE_COMPARISON != MIND_COMPARISON
LATTICE_ADDRESS != TRUTH
CODON_FREQUENCY != EVIDENCE
REPLAY_CLASSIFICATION != TRUTH
ORIGINAL_RUN != REPLAY_RUN
```

The frontend never derives a synthetic truth percentage from votes, model confidence, entropy, model count, Council consensus, retrieval scores, embedding similarity, codon frequency, lattice position, or replay classification.

## Session protection

On startup the server creates an unpredictable local session token.

The browser obtains it from the same-origin `/api/session` bootstrap and supplies it as:

```text
X-QSOL-Control-Token
```

All later API reads and every state-changing request require the token. The server does not enable CORS.

The server also rejects non-loopback `Host` headers and requires any browser `Origin` supplied on a state-changing request to be the same loopback server and port. This blocks the straightforward DNS-rebinding path where an attacker-controlled hostname resolves to `127.0.0.1` and attempts to retrieve/reuse the local session token.

```text
LOOPBACK_BIND != ARBITRARY_HOST_ACCEPTANCE
LOCAL_SESSION_TOKEN != DNS_REBINDING_PERMISSION
```

Responses also use:

```text
Content-Security-Policy
X-Content-Type-Options: nosniff
Referrer-Policy: no-referrer
Cross-Origin-Resource-Policy: same-origin
Cache-Control: no-store
```

Retrieved record content is inserted with DOM `textContent`; the application does not use `innerHTML` for untrusted records.

This does not replace the broader Phase 10 browser/network threat model. It gives the local Phase 5 surface a sane fail-closed baseline rather than postponing every browser boundary until later.

## Question composer

The composer exposes exactly two operator modes:

```text
Evidence only
Ask Council
```

Replay-basis fields are validated before a durable run is created. Invalid suggested searches, ORACLE age limits, Council member descriptors, NEXUS evidence refs, NEXUS mode, or replay-relevant privacy settings therefore fail before partial interaction history can be persisted.

### Evidence only

When ORACLE is configured:

1. CONTROL queries the read-only ORACLE adapter.
2. `known`, `conflict`, or `unknown` remains explicit.
3. ORACLE event/provenance refs are preserved.
4. missing evidence and suggested searches remain visible.
5. suggested searches are labelled **NOT EVIDENCE**.
6. a canonical CONTROL interaction is persisted.

If ORACLE is unconfigured/unavailable, the run records `unknown`; the UI does not invent evidence.

### Ask Council

The same evidence path is preserved first. CONTROL then calls the already-implemented NEXUS adapter.

The browser may provide:

```text
NEXUS mode
Council member descriptors
admitted object:<sha256> evidence refs
```

or use a server-configured member file.

The browser has no generic parent-operation passthrough. It does not expose `world.create`, Stenographer operations, ballot mutation, threshold overrides, or vote-weight controls.

## File attachments

The browser reads selected local files and submits bounded base64 content to the loopback server.

Before a run is created, each attachment becomes a normal content-addressed CONTROL File.

Phase 5 bounds each browser upload to 4 MiB.

Immediate File context is therefore ordinary persistent CONTROL state, not a special browser-only memory channel.

## Persistent Collections

The Collections view can:

- create a Collection;
- browse its current immutable membership snapshot;
- add/remove content-addressed File IDs through the CONTROL store;
- show the exact `HEAD` snapshot ID and revision;
- run deterministic lexical search.

Search results retain the existing meaning:

```text
retrieval_similarity_not_truth_or_evidence_strength
```

A search score is never promoted into evidence strength.

## Exact run snapshot

When a question uses a Collection, the current snapshot identity is frozen into the immutable run.

The run inspector resolves that historical snapshot by ID. If the Collection's current `HEAD` later advances, the old run continues to show the exact snapshot it actually used.

```text
RUN_COLLECTION_SNAPSHOT != CURRENT_COLLECTION_HEAD
```

## Evidence panel

The Evidence view renders:

- ORACLE availability;
- `known` / `conflict` / `unknown`;
- evidence references;
- source timestamps;
- freshness separately from truth;
- provenance kinds;
- missing evidence;
- suggested searches marked non-evidence.

`unknown` is a normal epistemic result, not a UI crash condition.

## Council panel

The Council view renders the verified `qsol-control-nexus-council-response/1` output.

It preserves:

- canonical roster order;
- model/adapter IDs;
- ordinary vote weight and epistemic privilege;
- parent phase order;
- visible phase submissions;
- the separate `SEALED_BALLOT` stage;
- revealed ballots;
- commitment-verification status;
- the exact consensus numerator/denominator;
- threshold-met state;
- canonical disposition;
- `NO_CONSENSUS` when applicable.

The panel states:

```text
VOTE != EVIDENCE
CONSENSUS != TRUTH
```

It does not render agreement as verification.

## Minority reports

NEXUS minority reports are shown as their own top-level view.

They are not buried beneath the winning disposition or averaged away.

## Sources / provenance

The Sources view combines inspectable references from:

- attached CONTROL Files;
- exact Collection snapshot Files;
- ORACLE observations preserved in evidence events.

Each row keeps its source/provenance/authority labels.

CONTROL storage does not transform those labels into stronger authority.

## ORACLE timeline and receipts

The Timeline combines:

- ORACLE observation timestamps from preserved evidence references;
- CONTROL immutable event timestamps.

The Receipts view shows CONTROL receipt events plus the verified NEXUS receipt reference/verification material when available.

The Health view also exposes the existing QSOL-CONTEXT 2056 timelock status through ORACLE.

```text
ELIGIBLE != EXECUTED
```

## Model-state inspector

Phase 5 consumes the Phase 4 label contract without renaming it.

Required labels:

```text
Panel title:        Model-state reproducibility metadata
Boundary badge:     Not model mind
Provenance heading: Metadata provenance
Unknown:            Unknown / not established
Locally verified:   Locally verified
Provider reported:  Provider reported
Inferred:           Inferred — not verified
Observed:           Observed
```

Every field is displayed with its Phase 4 provenance classification.

The inspector never silently promotes:

```text
provider_reported -> locally_verified
inferred          -> observed
unknown           -> false
```

and never presents model-state metadata as hidden reasoning, model mind, consciousness level, or subjective state.

Raw canonical JSON remains inspectable for technical auditing.

## Lattice-memory browser

The Memory view renders all 27 top-level logical addresses.

Each cell resolves to ordinary run/event records and can be inspected with the keyboard.

The visualization is navigation only:

```text
GEOMETRY != TRUTH
LATTICE_ADDRESS != COGNITION
```

## DNA/lattice recovery projection

The DNA view can inspect a CONTROL File's reversible projection using:

```text
qsol.lexicographic-27/1
qsol.phi-stride-27/1
```

Inspection displays:

- projection ID;
- input content hash;
- byte/codon counts;
- traversal identity;
- per-cell codon counts;
- codon histogram.

It also states:

```text
RAW_BYTES = CANONICAL
DNA_PROJECTION = DERIVED
CODON_FREQUENCY != EVIDENCE
```

Export returns the full deterministic projection JSON.

For a RESTRICTED File the operator must explicitly acknowledge that the export is reversible sensitive data. The export is audited through the existing CONTROL audit store.

## Replay / compare

Phase 5 supplies the browser surface; Phase 7 implements the replay engine behind the same reviewed local boundary.

The panel can:

- compare any two immutable runs without executing anything;
- classify whether a stored run can be rerun and what kind of rerun is actually supportable;
- execute a classified replay as a **new immutable run**;
- compare original evidence with current evidence;
- preserve the exact original Collection snapshot while comparing current Collection `HEAD` separately;
- explain Council/runtime/model/configuration changes;
- display recurring-question longitudinal timelines.

Generic run comparison remains explicitly non-executing even though replay execution now exists elsewhere:

```text
comparison_is_replay_execution = false
phase7_replay_execution_implemented = true
```

Replay also preserves:

```text
ORIGINAL_RUN != REPLAY_RUN
ORIGINAL_RESULT_IMMUTABLE = true
CURRENT_EVIDENCE != ORIGINAL_EVIDENCE
CURRENT_COLLECTION_HEAD != ORIGINAL_COLLECTION_SNAPSHOT
REPLAY_CLASSIFICATION != TRUTH
MODEL_STATE_COMPARISON != MIND_COMPARISON
```

For new Council runs the replay basis records the complete validated Council member descriptors, not merely member/model/adapter IDs. A change in an accepted execution field such as a member profile is therefore configuration drift. Historical Phase 7 runs that did not preserve the complete descriptor are marked incomplete and require explicit changed-configuration authorization rather than assuming equivalence.

Standalone File references are verified before a replay is advertised as executable. Missing or corrupt File records/objects classify the run as unavailable original context.

Replay model summaries are bounded to 100 states in rendered responses with explicit total/truncation metadata. Research timelines scan the model-state registry once, order runs by parsed UTC instants rather than raw timestamp strings, and compare normalized model/runtime metadata without per-run `state_id` values.

Persisted replay records and reports are content-addressed **and** semantically validated on every read. Hash-valid but authority-escalating, exact-replay-claiming, cross-record-inconsistent, or run-unbound replay metadata is rejected.

## Health / status

The Health view reports separately on:

```text
CONTROL storage
ORACLE
NEXUS
QSOL-CONTEXT timelock
```

Unavailable parents remain unavailable; the UI does not synthesize a healthy status from cached data.

## Accessibility

Phase 5 uses:

- semantic HTML landmarks;
- tab roles with arrow/Home/End keyboard navigation;
- a skip link;
- visible focus rings;
- explicit form labels;
- `aria-live` status messaging;
- text labels in addition to symbols;
- provenance words in addition to decoration;
- mobile single-column fallback;
- reduced-motion support;
- readable raw JSON dialogs.

The `Not model mind` boundary is visible text and available to assistive technology.

## Mobile fallback

Below the small-screen breakpoint:

- two-column content collapses to one column;
- mode controls stack;
- action rows stack;
- the tab strip remains horizontally scrollable;
- the run picker becomes full width;
- lattice cells collapse from nine columns to three.

The fallback is intended for inspection and ordinary operator actions, not to mimic a native mobile application.

## Limits

The local WebUI does **not** claim:

- remote multi-user deployment;
- a public network service;
- a separate browser authority model;
- exact replay of stochastic inference merely because inputs look similar;
- browser-side model inference;
- direct ORACLE writes;
- direct NEXUS WorldStore mutation;
- hidden chain-of-thought capture;
- model-mind capture;
- synthetic truth scoring.

Those boundaries are features, not missing decorative gauges.
