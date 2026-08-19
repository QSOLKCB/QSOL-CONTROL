# QSOL-CONTROL NEXUS Council adapter

## Purpose

`qsol-control-nexus-adapter/1` is CONTROL's local invocation and rendering boundary for QSOL-NEXUS Council runs.

CONTROL is an operator. NEXUS remains the governance owner.

```text
CONTROL_INVOKES_COUNCIL != CONTROL_OWNS_COUNCIL
CONTROL_RECEIPT_COPY != NEXUS_WORLDSTORE_WRITE
CONSENSUS != EVIDENCE
CONSENSUS != TRUTH
```

## Runtime discovery

CONTROL does not assume the current full NEXUS operation catalog. Every adapter session discovers the live runtime through:

```text
system.health
system.operations
```

The current adapter requires the parent to advertise:

```text
system.health
system.operations
council.run
world.inspect
receipt.verify
```

`council.epoch.verify` is optional and used only when advertised and when the Council response contains an epoch-admission receipt.

The discovered `system.health` response must identify the local control transport as:

```text
jsonl_stdio
```

The adapter currently accepts NEXUS protocol major `0` and fails closed on an unknown major. Runtime versions use full Semantic Versioning 2.0.0 syntax, including prerelease and build metadata such as `2.0.0-rc.1+build.7`.

## Local JSONL / stdio transport

The reference transport starts one local process with `shell=False` and maintains a persistent stdin/stdout session.

One canonical JSON object is written per line. One bounded JSON object is read per line. Owned stdin/stdout pipe handles are explicitly closed after the child is reaped so repeated adapter sessions do not leak descriptors.

The CLI receives the executable argv as JSON so shell parsing never becomes part of the adapter contract:

```bash
python3 tools/nexus_adapter.py \
  --nexus-command-json '["python3","-m","nexus_runtime","--world","/secure/nexus-world"]' \
  discover
```

For a repository checkout where `src/` is placed on `PYTHONPATH`, the same NEXUS `python3 -m nexus_runtime` entrypoint can be used without changing the CONTROL protocol.

## Council submission

A Council request contains:

```text
question
members
evidence_refs
evidence_state
mode
```

`evidence_refs` are ordered unique NEXUS WorldStore `object:<sha256>` references. CONTROL preserves their supplied order and verifies that the committed NEXUS evidence snapshot contains exactly those references in exactly that order.

Example members file:

```json
[
  {"member_id":"A","model_id":"mock-a","adapter_id":"mock","profile":"balanced"},
  {"member_id":"B","model_id":"mock-b","adapter_id":"mock","profile":"skeptical"},
  {"member_id":"C","model_id":"mock-c","adapter_id":"mock","profile":"exploratory"}
]
```

Run:

```bash
python3 tools/nexus_adapter.py \
  --nexus-command-json '["python3","-m","nexus_runtime","--world","/secure/nexus-world"]' \
  run \
  --question 'What follows from the admitted evidence?' \
  --members council-members.json \
  --evidence-ref object:<sha256> \
  --evidence-state known \
  --mode analytical
```

## Governance fields are not CONTROL knobs

CONTROL deliberately rejects governance-bearing fields in requested member/configuration data, including:

```text
vote_weight
epistemic_privilege
ballot / ballots
ballot_commitment / ballot_commitments
consensus_threshold
consensus_numerator
consensus_denominator
roster_authority
worldstore / world_store / world_state
```

Hidden/private reasoning keys are also rejected recursively **before** `council.run` is submitted. This includes chain-of-thought, hidden/private reasoning, scratchpads and reasoning traces.

Credential-labelled fields are rejected recursively before submission and before persistence, even when the value does not happen to contain a familiar token prefix. Examples include `api_key`, `access_token`, `refresh_token`, `client_secret`, `private_key`, `authorization`, `password`, and direct credential fields. Operational references such as a configured `credential_env` name are not themselves treated as secret values.

NEXUS may expose provider, deployment, capability, authentication-profile, timeout, local-endpoint, or model-selection fields according to its own runtime contract. Those fields select execution resources; they do not grant CONTROL authority to alter Council governance.

## Post-commit verification

CONTROL does not render the initial `council.run` response without resolving the committed artifacts.

After a successful run it:

1. resolves `session_ref` with `world.inspect` and verifies its content address;
2. resolves the committed `question_ref` and requires the exact submitted question text;
3. requires the committed session `world_mode`, returned `mode_id`, and committed `world_presence` mode to equal the submitted mode;
4. verifies that the committed World Presence binds the same question and roster;
5. reads the canonical roster and policy from the committed `council_session`;
6. requires non-empty `member_id`, `model_id`, and `adapter_id` fields plus ordinary vote weight `1` and epistemic privilege `none`;
7. requires every phase's joined member order to equal that roster order;
8. preserves the phase order exactly from the committed policy;
9. verifies every revealed ballot against its NEXUS `ballot:<sha256>` commitment;
10. recomputes the tally and the NEXUS disposition from revealed ballots;
11. recomputes whether the winning disposition meets the committed numerator/denominator;
12. validates the NEXUS consensus label against the revealed ballots and committed threshold;
13. requires the result threshold to equal the committed policy's exact numerator/denominator;
14. verifies the evidence snapshot binds the same committed question, requested evidence refs and requested evidence state;
15. preserves and verifies committed minority reports against the revealed ballots;
16. resolves `receipt_ref`, verifies its WorldStore identity, and calls `receipt.verify`;
17. requires the receipt's leading input refs to bind the committed question, evidence snapshot and world presence;
18. checks receipt result/replayability linkage to the committed session;
19. validates the optional Council Chair / Compute Epoch admission evidence when returned;
20. rejects credential-labelled or hidden-reasoning fields in accepted parent artifacts.

A self-consistent content hash is therefore not enough by itself. The committed session must also bind to the request CONTROL actually submitted.

## Phases and sealed ballot

The committed NEXUS policy currently represents deliberation phases separately from the ballot:

```text
WHITE
RED
BLACK
YELLOW
GREEN
BLUE
```

CONTROL preserves that `phase_order` exactly as returned by NEXUS.

The subsequent ballot is rendered separately as:

```text
SEALED_BALLOT
```

with both commitment records and the post-run revealed ballots. CONTROL verifies the commitments and never creates or edits ballot choices or rationales.

## Consensus threshold

CONTROL preserves NEXUS's canonical `disposition`, but it separately recomputes whether that disposition actually reaches the committed threshold.

The verified render therefore includes:

```json
{
  "disposition": "ACCEPT",
  "threshold_met": false,
  "consensus_outcome": "NO_CONSENSUS",
  "consensus_threshold": {
    "numerator": 2,
    "denominator": 3
  }
}
```

This distinction matters because NEXUS may record the single plurality disposition even when that plurality does not meet the consensus threshold. CONTROL must not turn a plurality into consensus merely because the disposition field is non-empty.

```text
PLURALITY_DISPOSITION != CONSENSUS_THRESHOLD_MET
```

CONTROL also recomputes the expected NEXUS consensus label (`UNANIMOUS`, `STRONG_CONSENSUS`, `CONSENSUS`, `MAJORITY_NO_CONSENSUS`, or `NO_CONSENSUS`) from the revealed ballots and committed threshold and fails closed if the committed label disagrees.

## Minority reports

Minority reports are preserved as committed by NEXUS. CONTROL checks that they agree with the revealed ballot record and does not suppress them when consensus is reached.

## Storage in CONTROL

When `--control-root` is supplied, CONTROL stores canonical JSON copies of externally visible artifacts:

```text
council.run public response
council_session WorldStore object
receipt WorldStore object
receipt.verify response
CONTROL verified render
optional epoch-admission receipt + verification
```

Each File is labelled `reference-only` and explicitly records:

```text
copied_governance_authority = false
hidden_chain_of_thought_captured = false
```

If an existing `qsol-control-interaction/2` run is supplied with `--control-run-id`, CONTROL first verifies **before writing any NEXUS artifact Files** that the target run:

- is a `council` run;
- has the exact same question text; and
- has the exact same evidence state as the Council invocation.

Only then are the verified NEXUS artifacts written and receipt/response events appended. This prevents a response for question A from being attached to unrelated run B.

## Hidden chain-of-thought boundary

CONTROL does not call NEXUS Stenographer operations and does not request hidden model reasoning.

Visible Council phase submissions and visible ballot rationales are treated as public/runtime outputs, not hidden chain-of-thought.

If a caller request or future parent response exposes a field named like hidden/private reasoning, scratchpad, reasoning trace, or chain-of-thought, this adapter fails closed rather than submitting or persisting it.

```text
VISIBLE_NEXUS_OUTPUT != HIDDEN_CHAIN_OF_THOUGHT
HIDDEN_CHAIN_OF_THOUGHT_CAPTURED = false
```

## Governance gate

The adapter public mutation surface contains exactly one operation:

```text
council.run
```

It does not expose:

```text
world.create
arbitrary operation passthrough
ballot mutation
roster-authority mutation
vote-weight mutation
threshold mutation
WorldStore rewrite
```

`council.run` necessarily causes NEXUS itself to append its own immutable WorldStore objects. That is NEXUS executing its governance protocol, not CONTROL directly rewriting WorldStore history.
