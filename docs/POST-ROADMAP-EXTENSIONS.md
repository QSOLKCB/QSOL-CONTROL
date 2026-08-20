# Post-roadmap extensions and permanent non-goals

QSOL-CONTROL's numbered roadmap is complete through Phase 10. PR #15 resolves the old deferred list without reopening the completed core contract.

The extension machine entrypoint is `extensions/manifest.json` (`qsol-control-post-roadmap-extensions/1`). It is explicitly bound to core contract `2.6.0`.

```text
CORE_2_6_0 != EXTENSION_SURFACE
OPTIONAL_EXTENSION != CORE_AUTHORITY
```

## Deferred-item disposition

| Old deferred item | PR #15 disposition |
| --- | --- |
| Remote multi-user deployment | Authenticated remote **Agent API gateway** implemented as an optional extension. The local WebUI is not remotely exposed. |
| Mobile native applications | Native iOS/SwiftUI and Android/Kotlin reference clients implemented as thin HTTPS clients. App-store packaging is not claimed. |
| Distributed consensus for CONTROL storage | External consensus coordination adapter implemented. CONTROL does not embed a consensus algorithm or let a quorum receipt rewrite storage by itself. |
| Automatic truth scoring | Permanent non-goal. Forbidden. |
| Hidden chain-of-thought capture | Permanent non-goal. Forbidden. |
| Literal geometric-cognition claims from the lattice | Permanent non-goal. Forbidden. |
| Biological claims from the DNA-symbol codec | Permanent non-goal. Forbidden. |
| Claims that φ traversal is physically optimal storage | Permanent non-goal. Forbidden. |

## Remote multi-user Agent API gateway

`api/remote_http.py` adds a deliberately narrow network transport over the existing `AgentAPIDispatcher`.

The public endpoint is:

```text
POST /v1/agent
Content-Type: application/json
Authorization: Bearer <token>
```

The remote request protocol contains no caller object:

```json
{
  "protocol": "qsol-control-remote-request/1",
  "request_id": "mobile-123",
  "operation": "control.health",
  "params": {}
}
```

A gateway principal maps the token digest to a fixed local Agent API caller identity plus an explicit operation allowlist. The client cannot self-award `caller.kind`, `caller.id`, ORACLE authority, NEXUS governance, or any extra epistemic privilege.

Gateway config stores `sha256(token_utf8)`, never the raw bearer token. On POSIX the config is required to be private (`0600`-style permissions). Non-loopback binds require both explicit `allow_non_loopback=true` and TLS with a minimum of TLS 1.2. Host allowlisting is mandatory. CORS is not enabled.

```text
REMOTE_ACCESS != EPISTEMIC_PRIVILEGE
AUTHENTICATED != AUTHORITATIVE
CLIENT_IDENTITY != SELF_ASSERTED_CALLER_IDENTITY
REMOTE_GATEWAY != REMOTE_WEBUI
```

Launch:

```bash
python3 tools/remote_gateway.py \
  --gateway-config /secure/control-gateway.json \
  --root .qsol-control-store
```

The committed `examples/remote-gateway.loopback.json` is a synthetic shape reference only. Real token material and TLS private keys must not enter the repository.

## Native mobile reference clients

The mobile clients are intentionally thin:

- `mobile/ios/QSOLControl/` uses SwiftUI + `URLSession`;
- `mobile/android/app/src/main/` uses Android platform APIs + `HttpsURLConnection`.

Both speak `qsol-control-remote-request/1` to `/v1/agent`, require HTTPS in the reference client, hold the bearer token only in memory for the current UI session, and render the protocol response without inventing local truth scoring or hidden-reasoning views.

They are source-level reference clients, not signed App Store / Play Store releases.

```text
MOBILE_CLIENT != CONTROL_AUTHORITY
MOBILE_UI != TRUTH_ENGINE
VISIBLE_RESPONSE != HIDDEN_CHAIN_OF_THOUGHT
```

## External distributed-consensus coordination

`adapters/consensus.py` resolves the distributed-consensus deferred item through an external coordination boundary instead of embedding Raft/Paxos into CONTROL.

CONTROL first creates a content-addressed intent:

```text
intent_id = sha256(canonical intent payload)
```

The intent binds:

- CONTROL operation;
- exact parameters;
- expected current CONTROL store fingerprint;
- coordination-only authority.

An external provider forms quorum and returns `qsol-control-consensus-receipt/1`. CONTROL validates exact intent binding, member-set/state fingerprints, epoch/index shape, quorum satisfaction, provider verification, and the no-authority-escalation contract.

The adapter itself does **not** apply the mutation to CONTROL storage. A quorum receipt is an admission/coordination artifact for a higher-level deployment workflow, not a magic distributed write primitive.

```text
CONSENSUS_RECEIPT != SEMANTIC_AUTHORITY
QUORUM != TRUTH
COORDINATION != EVIDENCE
EXTERNAL_CONSENSUS != CONTROL_STORAGE_REWRITE
```

CLI:

```bash
python3 tools/consensus_adapter.py --command-json '["consensus-provider"]' health
python3 tools/consensus_adapter.py --command-json '["consensus-provider"]' \
  propose --root .qsol-control-store \
  --operation control.collection.create \
  --params-json intent-params.json
```

The external provider is responsible for the actual consensus algorithm, cryptographic/member authentication, liveness, leader election, durability, and fault model.

## Permanent non-goals

`ai/permanent-nongoals.json` makes the five epistemic/ontological items permanent rather than leaving them as tempting empty checkboxes.

```text
AUTOMATIC_TRUTH_SCORING = FORBIDDEN
HIDDEN_CHAIN_OF_THOUGHT_CAPTURE = FORBIDDEN
LATTICE_GEOMETRY != COGNITION_CLAIM
DNA_CODEC != BIOLOGICAL_CLAIM
PHI_TRAVERSAL != PHYSICAL_OPTIMALITY
```

A later PR may strengthen these prohibitions, but must not silently reinterpret them as unfinished features.
