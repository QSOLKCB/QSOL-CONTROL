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

The adapter currently accepts NEXUS protocol major `0` and fails closed on an unknown major. Minor protocol changes are discovered at runtime and must still expose the required operations.

## Local JSONL / stdio transport

The reference transport starts one local process with `shell=False` and maintains a persistent stdin/stdout session.

One canonical JSON object is written per line. One bounded JSON object is read per line.

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

NEXUS may expose provider, deployment, capability, authentication-profile, timeout, local-endpoint, or model-selection fields according to its own runtime contract. Those fields select execution resources; they do not grant CONTROL authority to alter Council governance.

## Post-commit verification

CONTROL does not render the initial `council.run` response without resolving the committed artifacts.

After a successful run it:

1. resolves `session_ref` with `world.inspect`;
2. verifies the WorldStore object's content address;
3. reads the canonical roster and policy from the committed `council_session`;
4. requires every phase's joined member order to equal that roster order;
5. preserves the phase order exactly from the committed policy;
6. verifies every revealed ballot against its NEXUS `ballot:<sha256>` commitment;
7. recomputes the tally from revealed ballots;
8. requires the result threshold to equal the committed policy's exact numerator/denominator;
9. preserves the committed minority reports exactly;
10. resolves `receipt_ref`, verifies its WorldStore identity, and calls `receipt.verify`;
11. checks receipt result/replayability linkage to the committed session;
12. validates the optional Council Chair / Compute Epoch admission evidence when returned.

A hash verifies integrity and linkage. It does not turn Council consensus into epistemic truth.

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

CONTROL renders the exact threshold from the committed NEXUS session:

```json
{
  "numerator": 2,
  "denominator": 3
}
```

The values above describe the current reference policy. CONTROL does not hard-code them as its own governance rule. It verifies that the result's threshold matches the session policy returned by NEXUS.

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

If an existing `qsol-control-interaction/2` run is supplied with `--control-run-id`, CONTROL also appends a receipt event and a derived response event referencing the verified NEXUS artifacts.

## Hidden chain-of-thought boundary

CONTROL does not call NEXUS Stenographer operations and does not request hidden model reasoning.

Visible Council phase submissions and visible ballot rationales are treated as public/runtime outputs, not hidden chain-of-thought.

If a future parent response exposes a field named like hidden/private reasoning, scratchpad, reasoning trace, or chain-of-thought, this adapter fails closed rather than persisting it.

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
