# QSOL-CONTROL Model-State Registry

## Purpose

Phase 4 implements persistent `qsol-control-model-state/1` records for **computational archaeology and reproducibility**.

The registry preserves externally inspectable facts about a model execution. It does not preserve or infer a model mind.

```text
MODEL_STATE != MODEL_MIND
VISIBLE_OUTPUT != HIDDEN_CHAIN_OF_THOUGHT
RUNTIME_METADATA != CONSCIOUSNESS
```

These are runtime and schema invariants, not disclaimers pasted onto the UI later.

## Persistent identity

Canonical records live under the CONTROL storage root:

```text
records/model-states/<sha256>.json
```

`state_id` is the SHA-256 content reference of the canonical record payload excluding `state_id` itself.

```text
STATE_ID = sha256(canonical model-state payload)
```

Records are immutable. A path/content identity mismatch fails verification.

Each record is bound to an existing `qsol-control-interaction/2` run through:

```text
system.control_run_id
```

The registry validates that run before capture. Late model-state capture does **not** mutate the already immutable interaction run record merely to add a new array member.

### Run-event lineage

Phase 1B already defined a compact `model_state` event payload. Phase 4 deliberately does not redefine that old event shape in place.

Instead:

```text
full Phase-4 registry record = canonical model state
Phase-1B model_state event   = backward-compatible lineage projection
record_refs                  = [canonical state_id]
```

The projection preserves the model/runtime identifiers, selected execution fields, system run binding, and the canonical `state_id`. The full field-level provenance remains in the registry record.

The older event format has only one coarse `metadata_provenance` field. Phase 4 sets that projection field to `unknown` rather than collapsing many field-level provenance classes into a stronger claim.

```text
EVENT_PROJECTION != CANONICAL_MODEL_STATE
COARSE_PROVENANCE != FIELD_LEVEL_PROVENANCE
```

Capture is idempotent: re-capturing the same canonical state does not append a duplicate run-event link.

## Canonical record

The record captures four dimensions.

### Model identity

```text
provider
runtime
runtime_version
model_id
revision
quantization
model_hash
weight_hash
tokenizer_identity
tokenizer_hash
```

The first five identify what the execution environment says the model was. Hashes provide artifact identity only when available.

### Local artifact verification

The CLI/runtime may be given local paths for:

```text
model
weights
tokenizer
```

Those paths are used only for hashing.

For a regular file:

```text
sha256(exact file bytes)
```

For a directory/sharded artifact:

```text
sha256(canonical manifest(relative path, exact file SHA-256, size))
```

The latter is explicitly labelled `directory-manifest`; it is not misrepresented as a hash of one imaginary directory byte stream.

The canonical model-state record stores:

```text
hash
hash scope/kind
size
file count
manifest protocol when applicable
```

It does **not** store:

```text
local artifact path
model bytes
weight bytes
tokenizer bytes
```

```text
HASH_IDENTITY != ARTIFACT_BYTES
```

### Execution configuration

The registry preserves, where available:

```text
Council seat
NEXUS mode
deterministic/stochastic indicator
seed
context limit
sampling parameters
tool permissions
tool permission envelope
```

The canonical tool envelope separates:

```text
filesystem: none | read-only | workspace-write | unrestricted | unknown
network:    none | loopback | restricted | unrestricted | unknown
tools
mcp_plugins
external_execution
```

Tool access is recorded as execution context. It does not confer epistemic authority.

### System snapshot identities

A model-state may bind:

```text
CONTROL run identity
CONTROL manifest identity
NEXUS identity
ORACLE refs
SUBSTRATE identity
ARK identity
INT identity
exact Collection snapshot identity
NEXUS evidence snapshot ref
relevant hardware/runtime metadata
```

If a containing CONTROL run already binds a Collection snapshot, the registry refuses a contradictory model-state snapshot identity.

## Field-level provenance

Every canonical capture field has one explicit provenance class:

```text
observed
provider_reported
locally_verified
inferred
unknown
```

Unclassified fields default to:

```text
unknown
```

They never silently become `observed`.

Locally computed model/weight/tokenizer hashes are automatically labelled:

```text
locally_verified
```

The containing CONTROL run identity is also locally verified. `captured_at` is classified as observed.

Important distinction:

```text
PROVIDER_REPORTED != LOCALLY_VERIFIED
INFERRED != OBSERVED
UNKNOWN != FALSE
```

A provider-reported model ID is preserved as provider-reported unless another mechanism independently establishes it.

## Privacy and forbidden material

Persistent records use:

```text
PUBLIC
INTERNAL
RESTRICTED
```

`FORBIDDEN` is not a persistable class. It is a rejection outcome.

The runtime recursively rejects credential-labelled fields such as API keys, access/refresh tokens, client secrets, passwords, authorization headers, cookies and private keys. Known credential-value markers are rejected as defence in depth.

The runtime also rejects fields labelled as:

```text
chain_of_thought
hidden_chain_of_thought
hidden_reasoning
private_reasoning
internal_reasoning
reasoning_trace
scratchpad
model_mind
internal_activations
```

Do not hash a credential and call the result archival metadata.

## Cross-state and cross-run comparison

Two model states can be compared deterministically with:

```text
qsol-control-model-state-comparison/1
```

The comparison records:

```text
field path
left value
right value
left provenance
right provenance
field category
```

Run-level comparison uses:

```text
qsol-control-model-state-run-comparison/1
```

States are aligned by Council seat when a seat exists, otherwise by provider/model identity. Ambiguous duplicate alignment keys fail closed rather than guessing which model instance corresponds to which.

Comparisons explicitly carry:

```json
"model_mind_inference": false
```

```text
MODEL_STATE_COMPARISON != MIND_COMPARISON
```

## Future-AI archaeology export

`qsol-control-model-state-archaeology/1` is a deterministic, self-describing JSON export of selected states.

It includes:

```text
canonical model-state records
state IDs
run -> state index
provenance vocabulary
privacy class
artifact identity semantics
epistemic/UI boundary labels
```

It explicitly states:

```json
"hidden_chain_of_thought_captured": false,
"model_mind_captured": false,
"contains_model_artifact_bytes": false,
"local_artifact_paths_persisted": false
```

RESTRICTED exports require explicit acknowledgement and are written owner-only (`0600`) on POSIX systems.

The archaeology export is meant to answer questions such as:

- Which model/runtime was recorded for this visible output?
- Which identity fields were observed, provider-reported, locally verified, inferred or unknown?
- Were exact weights or tokenizer artifacts locally hashable?
- What sampling/context/tool envelope was active?
- Which NEXUS/ORACLE/SUBSTRATE/Collection identities were bound?
- What changed between two runs?

It cannot answer:

- What was the model secretly thinking?
- Was the model conscious?
- Was the answer true because a particular model produced it?
- Can a future runtime reproduce identical stochastic output merely from metadata?

## UI label contract

Until Phase 5 builds the WebUI, the required model-state labels are already machine-readable in `ai/model-state-contract.json`.

The UI must present:

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

The WebUI must not shorten the panel to `Mind`, `AI mind`, `internal state`, or equivalent language.

## CLI

Capture from a JSON descriptor:

```bash
python3 tools/model_state.py --root .store capture \
  --descriptor model-state-input.json \
  --weight-artifact /local/path/model.gguf \
  --tokenizer-artifact /local/path/tokenizer.json
```

Inspect and verify:

```bash
python3 tools/model_state.py --root .store show <state_id>
python3 tools/model_state.py --root .store verify <state_id>
python3 tools/model_state.py --root .store list --run-id <run_id>
```

Compare:

```bash
python3 tools/model_state.py --root .store compare-states <left_state_id> <right_state_id>
python3 tools/model_state.py --root .store compare-runs <left_run_id> <right_run_id>
```

Export:

```bash
python3 tools/model_state.py --root .store export \
  --run-id <run_id> \
  --output model-state-archaeology.json
```

For RESTRICTED material, add `--allow-restricted` only after reviewing the export boundary.

## Schemas and contracts

- `schema/model-state.schema.json`
- `schema/model-state-comparison.schema.json`
- `schema/model-state-run-comparison.schema.json`
- `schema/model-state-archaeology.schema.json`
- `ai/model-state-contract.json`

The public protocol remains:

```text
qsol-control-model-state/1
```
