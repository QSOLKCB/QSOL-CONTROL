# Phase 10 Network and Browser Threat Model

QSOL-CONTROL is a **local operator control plane**, not a remote multi-user service.
Phase 10 threat-models the network/browser surface that actually exists and refuses to
claim protections for a deployment mode CONTROL does not implement.

```text
LOCAL_ONLY != INTERNET_SAFE_BY_DEFAULT
SESSION_TOKEN != MULTI_USER_AUTHORIZATION
LOOPBACK != TRUSTED_CONTENT
BROWSER_RENDER != SEMANTIC_AUTHORITY
```

## Protected assets

- CONTROL canonical File/Collection/run/model/replay state;
- INTERNAL and RESTRICTED metadata/content;
- ORACLE read-only provenance and receipt references;
- NEXUS Council request/result/receipt integrity;
- WebUI session token;
- operator intent at state-changing routes;
- release/recovery bundle integrity;
- authority boundaries between CONTROL, ORACLE, NEXUS, ARK, INT, and SUBSTRATE.

Credentials are not a protected CONTROL record class because they are **forbidden
material** and must not be persisted in the first place.

## Implemented transport surfaces

### WebUI

The WebUI is HTTP on loopback only. It has no TLS because it is not intended to leave
the host. The reviewed boundary requires:

- bind host in `127.0.0.1`, `::1`, or `localhost` only;
- non-loopback `Host` rejection to resist DNS rebinding;
- unpredictable per-process session token;
- token authentication after session bootstrap;
- no CORS;
- same-origin checks for state-changing requests when `Origin` is present;
- POST for state-changing replay/storage operations;
- CSP, framing denial, `nosniff`, no-referrer, same-origin resource policy, no-store;
- retrieved/untrusted values rendered with `textContent`, not `innerHTML`.

### Agent API

The agent API is JSONL over local stdin/stdout. It opens no network listener. Requests
remain untrusted and are governed by operation whitelists, quotas, process ceilings,
strict JSON parsing, bounded payloads, and the same epistemic authority as a human
caller.

## Threats and mitigations

### DNS rebinding / hostile Host

**Threat:** a hostile site resolves a name to loopback and tries to drive the local
WebUI through a browser.

**Mitigation:** reject non-loopback Host values and do not enable CORS. Mutation routes
also enforce the session token and same-origin policy.

### CSRF / cross-origin mutation

**Threat:** another origin causes the browser to submit a state-changing CONTROL
request.

**Mitigation:** session token + same-origin checks + no CORS + non-simple JSON/POST
operator API shape. `Origin` mismatch fails closed.

### Session-token theft

**Threat:** malware, a browser extension with sufficient local privileges, or a
compromised browser profile obtains the session token.

**Mitigation:** token is per-process, unpredictable, returned only by local bootstrap,
and responses are no-store. **Residual risk:** CONTROL does not claim to defend against
host-level malware or a browser extension already authorized to inspect localhost.

### XSS / untrusted rendering

**Threat:** File metadata, model output, provenance, or parent-system strings contain
HTML/script payloads.

**Mitigation:** browser rendering uses DOM text nodes/`textContent`; CSP blocks inline
script expansion, framing, object/plugin content, and base-URI substitution. Server
responses keep JSON and static content separate.

### Request flooding / local DoS

**Threat:** a local process or page repeatedly invokes CONTROL and exhausts resources.

**Mitigation:** AI API request/mutation quotas and process-wide ceilings; bounded File,
response, traversal, model-state, replay, archive, and recovery sizes. The WebUI remains
single-operator local software and does not promise hostile multi-tenant fairness.

### Reverse proxy / remote bind accident

**Threat:** an operator places the loopback service behind a reverse proxy, container
port-forward, SSH tunnel, or other exposure mechanism and assumes CONTROL now has
remote authentication.

**Mitigation:** this is explicitly outside the implemented security contract. Remote
multi-user deployment requires a separate threat model, authentication, authorization,
TLS/transport policy, session lifecycle, record-class ACLs, audit policy, and secret
rotation. Phase 10 does not silently inherit those properties from loopback.

### Parent-system command injection

**Threat:** untrusted browser/model content becomes an arbitrary ORACLE or NEXUS
operation.

**Mitigation:** ORACLE adapter is read-only; NEXUS exposes the reviewed Council path and
no generic operation passthrough. Browser/API strings never become shell commands.

### Secret persistence through metadata/imports

**Threat:** credential-labelled fields or credential-bearing locators are stored in
File/Collection metadata, then preserved forever by content-addressed recovery.

**Mitigation:** write-time marker rejection remains in the storage runtime; Phase 10
adds a read/import-side deterministic metadata audit that rejects credential-labelled
keys, high-confidence token markers, credential-bearing query parameters, duplicate
JSON members, malformed identities, and rehashed hostile records. The audit does not
silently redact or rewrite canonical history.

### Archive/decompression bombs

**Threat:** an untrusted compressed archive expands far beyond its on-disk size or
uses pathological member counts/paths.

**Mitigation:** compressed untrusted imports are default-deny. The Phase 10 release
verifier accepts only `ZIP_STORED`, bounds archive bytes/member count/member bytes/total
bytes before payload reads, rejects symlinks/traversal/duplicates, performs no
extraction, and performs no decompression. Existing portable-CONCAP ZIP support is an
**export** format, not an accepted ZIP import path.

### Migration authority escalation

**Threat:** a version migration rewrites old state and silently changes its meaning or
authority.

**Mitigation:** migration policy is versioned, source-preserving, copy-then-verify, and
receipt-based. Unknown majors and downgrades fail closed. Current declared Phase 10
steps require no canonical store rewrite.

## Trust assumptions

Phase 10 assumes:

- the local OS account and filesystem permissions are not already fully compromised;
- Python and the browser runtime are within the operator's trusted computing base;
- a loopback-only deployment is actually kept loopback-only;
- callers do not treat compatibility, hashes, replay classifications, or release
  reproducibility as truth authority.

## Explicit non-goals

- internet-facing service hardening;
- multi-user authentication/authorization;
- browser-extension isolation;
- host-malware resistance;
- TLS termination or reverse-proxy configuration;
- distributed rate limiting or distributed consensus;
- automatic secret rotation;
- hidden chain-of-thought protection by storing it. CONTROL refuses to store it.

## Security invariants

```text
REMOTE_MULTI_USER_DEPLOYMENT = false
LOOPBACK_BIND != REMOTE_AUTH
SESSION_TOKEN != EPISTEMIC_PRIVILEGE
CORS_ENABLED = false
MODEL_OUTPUT = UNTRUSTED_INPUT
COMPRESSED_UNTRUSTED_INPUT != ACCEPTED_BY_DEFAULT
MIGRATION != REINTERPRETATION
RELEASE_HASH != SEMANTIC_TRUTH
CONTROL_CALL != ORACLE_AUTHORITY
CONTROL_CALL != NEXUS_GOVERNANCE
```
