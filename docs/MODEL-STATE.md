# QSOL-CONTROL Model-State Preservation

## Purpose

CONTROL preserves externally inspectable model/runtime metadata so future humans and AIs can understand the computational circumstances surrounding a recorded interaction.

The goal is **computational archaeology and reproducibility**, not mind capture.

## Core boundary

```text
MODEL_STATE != MODEL_MIND
VISIBLE_OUTPUT != HIDDEN_CHAIN_OF_THOUGHT
RUNTIME_METADATA != CONSCIOUSNESS
```

CONTROL must never claim it preserved hidden reasoning that a model/provider did not expose.

## State classes

Every field should be classifiable as one of:

```text
observed
provider_reported
locally_verified
inferred
unknown
```

`inferred` metadata must remain explicitly inferred. Unknown fields remain unknown.

## Candidate fields

When available and appropriate, preserve:

### Identity

```text
provider
runtime
runtime_version
model_id
model_revision
model_family
open_or_closed_weight_status
```

### Artifact identity

```text
weight/model hash
model file identity
tokenizer identity/hash
adapter identity/hash
quantization identity
```

### Inference configuration

```text
context limit
sampling parameters
temperature
top_p/top_k where applicable
seed where meaningful
deterministic/stochastic classification
```

### QSOL execution context

```text
CONTROL protocol/version/run_id
NEXUS protocol/runtime
Council seat
Council mode
ORACLE snapshot/receipt refs
SUBSTRATE snapshot identity
ARK/INT compatibility refs where relevant
tool permission envelope
```

### Environment

Only when materially relevant to reproducibility:

```text
OS/runtime class
accelerator/GPU class
precision
relevant library/runtime versions
execution timestamp
```

Avoid collecting irrelevant host/user details merely because they are available.

## Recommended field policy

Prefer **allowlisted structured fields** over dumping provider/runtime response objects into a generic metadata map.

Good:

```text
runtime = ollama
runtime_version = 0.x
quantization = Q4_K_M
accelerator_class = RTX-50-series
```

Usually unnecessary and potentially sensitive:

```text
local username
home directory
machine hostname
serial number
private LAN address
provider account ID
billing workspace ID
raw HTTP headers
full environment dump
```

If a sensitive identifier is genuinely necessary for reproducibility, classify it as restricted metadata and document why.

## Privacy classification

Before model-state persistence/export, classify fields conceptually as:

```text
PUBLIC      deliberately safe for public export
INTERNAL    useful local reproducibility metadata; not public by default
RESTRICTED  sensitive identifier or environment metadata requiring explicit approval
FORBIDDEN   credential or hidden reasoning that CONTROL must not retain
```

A model-state record may contain fields from more than one class internally, but export tooling must not flatten those classes into an unrestricted public blob.

## Redaction / aggregation

Redact or aggregate before durable storage when precision is not required.

Examples:

```text
/home/alice/models/foo.gguf       -> local model path omitted; artifact hash retained
trent-workstation-03              -> hostname omitted
192.168.1.27                      -> network address omitted
GPU serial ABC123                 -> accelerator class retained, serial omitted
provider workspace 784923...      -> workspace ID omitted
Authorization: Bearer ...         -> entire credential removed
```

Do not hash a credential and then call the hash safe archival metadata. Secret-derived hashes may still be sensitive and can support guessing attacks.

## Retention

Model-state metadata exists to support replay/reconstruction, but retention is still a deliberate decision.

Recommended policy:

- credentials/hidden reasoning: **never persist**;
- incidental transport/debug metadata: **transient**;
- unreviewed model-state captures: **session/workspace scope** by default;
- curated reproducibility records: **archive** only after classification and redaction;
- ARK/public exports: only explicitly cleared fields.

Archival intent does not override privacy or rights boundaries.

## Example canonical record

The canonical valid fixture is:

```text
examples/schema/model-state.valid.json
```

Its paired negative fixture intentionally claims hidden chain-of-thought capture and **must fail**:

```text
examples/schema/model-state.invalid.json
```

Conceptually, a valid record looks like:

```json
{
  "protocol": "qsol-control-model-state/1",
  "state_id": "sha256:...",
  "captured_at": "...",
  "model": {
    "provider": "local",
    "runtime": "ollama",
    "model_id": "example-model",
    "revision": null,
    "quantization": "Q4_K_M",
    "metadata_provenance": "observed"
  },
  "execution": {
    "council_seat": "WHITE",
    "mode": "analytical",
    "stochastic": true
  },
  "system": {
    "control_run_id": "sha256:...",
    "nexus_identity": "...",
    "oracle_refs": [],
    "substrate_identity": "..."
  },
  "hidden_chain_of_thought_captured": false
}
```

## Future-AI questions this should enable

A future system should be able to ask:

- Which model/runtime produced this visible output?
- Was the exact model artifact locally hashable?
- Which NEXUS version and Council seat were active?
- What evidence snapshot was available?
- Was generation deterministic or stochastic?
- What changed between two runs?
- Is enough metadata present to reproduce, approximate, or merely contextualize the run?

## What this record cannot prove

A model-state record does not prove:

- that the model's answer was true;
- that the provider-reported model identity was authentic unless independently verified;
- consciousness or subjective state;
- the model's complete internal activations;
- hidden chain-of-thought;
- that a future implementation can recreate identical stochastic output.

## Privacy / secret boundary

Never store:

- API keys/tokens;
- account cookies;
- private provider billing/account metadata;
- secret environment variables;
- unredacted credentials in command lines;
- hidden reasoning not intentionally exposed for persistence.

Review before storage/export:

- provider request IDs;
- workspace/project IDs;
- model endpoints;
- usernames/local paths;
- hostnames/IP addresses;
- device identifiers;
- free-form provider metadata.

See `SECURITY.md` for the repository-wide classification, redaction, access-control and retention rules.

## Export to ARK

ARK-oriented exports should prefer compact, self-describing model-state records with schemas and hashes so future reconstruction does not depend on the original CONTROL database or UI.

An ARK export is a new boundary review: it must not automatically inherit every field that CONTROL retained locally.
