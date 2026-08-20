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
| Remote multi-user deployment | Authenticated and record-authorized remote **Agent API gateway** implemented as an optional extension. The local WebUI is not remotely exposed. |
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

### Authentication is not authorization

Each principal also carries a privacy ceiling and record ACLs for File, Collection, run, model-state, and replay identities. PUBLIC Files/Collections may be shared within the privacy ceiling. INTERNAL/RESTRICTED Files/Collections require explicit ACL or ownership established by a prior successful authenticated gateway action. Runs/replays/model-state records are not globally readable merely because an ID is known.

Successful gateway-created resources are associated with the authenticated principal through content-addressed `qsol-control-remote-audit/1` records under `records/remote-audit/`. The audit preserves principal ID, caller mapping, request ID, operation, outcome, requested refs, and created refs while explicitly recording `credential_material_captured=false`. Bearer headers/tokens are never persisted.

```text
AUTHENTICATION != RECORD_AUTHORIZATION
AUTHENTICATED != AUTHORITATIVE
CLIENT_IDENTITY != SELF_ASSERTED_CALLER_IDENTITY
```

### Network and availability boundary

Gateway config stores `sha256(token_utf8)`, never the raw bearer token. Presented bearer tokens must be 32..4096 characters. On POSIX the config and TLS private key are required to be private. Non-loopback binds require both explicit `allow_non_loopback=true` and TLS with a minimum of TLS 1.2. Host allowlisting is mandatory. CORS is not enabled.

The public `build_server()` factory revalidates those rules even for programmatically constructed configurations. The server bounds accepted connections to 64, gives accepted sockets a 10-second timeout, and acquires the connection slot before creating the request thread. The underlying Agent API dispatcher is renewed on a 60-second quota window so the persistent gateway does not permanently exhaust stdio-style lifetime quotas.

```text
REMOTE_ACCESS != EPISTEMIC_PRIVILEGE
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

- a known CONTROL mutation operation;
- exact parameters that pass the Agent API forbidden-field boundary;
- expected current CONTROL store fingerprint;
- coordination-only authority.

A caller-supplied intent is fully revalidated before the external provider is invoked; a valid content hash is not enough to bless invalid semantics.

An external provider forms quorum and returns `qsol-control-consensus-receipt/1`. CONTROL validates exact intent binding, member-set/state fingerprints, epoch/index shape, quorum satisfaction, provider verification, and the no-authority-escalation contract. Provider stdout is capped at 4 MiB and stderr at 1 MiB **while the child is running**; the provider is terminated on overflow. After a proposal receipt passes local validation, CONTROL asks the provider to verify that exact receipt again before returning it.

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
