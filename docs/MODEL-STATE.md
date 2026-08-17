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

## Example conceptual record

```json
{
  "type": "qsol-control-model-state",
  "protocol": "qsol-control-model-state/1",
  "state_id": "sha256:...",
  "model": {
    "provider": "local",
    "runtime": "ollama",
    "model_id": "example-model",
    "revision": "unknown",
    "quantization": "Q4_K_M"
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

## Export to ARK

ARK-oriented exports should prefer compact, self-describing model-state records with schemas and hashes so future reconstruction does not depend on the original CONTROL database or UI.
