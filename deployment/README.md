# Render edge — reviewed read-only phase

The optional Render edge is isolated in `deployment/`; **QSOL-CONTROL core,
NEXUS/FED/ORACLE donors, and the existing NEXUS GitHub Pages site remain unchanged**.
This deployment is a preview of read-only integration, **not** a production
multi-tenant, persistent, federated Council environment.

## Real integration

- **CONTROL:** authenticates a 256-bit randomly generated bearer secret using
  the existing `qsol-control-remote-gateway/1` implementation on **loopback**.
  Only `control.health` and `control.capabilities` are allowlisted.
  The unmodified CONTROL dispatcher, principal mapping, rate counter and audit
  execute on the local boundary for `POST /v1/agent`.
- **NEXUS:** a bounded local JSONL process is spawned only for
  `system.health` / `system.operations` by the existing
  `adapters/nexus.py` discovery validator. No Council execution is exposed.
- **FED:** the pinned Python SDK independently verifies its Phase 6 conformance
  fixture. This is **not** a live federation node, membership, signature or
  network interoperability claim.
- **ORACLE:** existing `adapters/oracle.py` verifies the pinned ledger and
  supports exact-subject read-only evidence queries. Unknown is preserved.
- **Provenance:** build-time `git fetch` pins exact 40-hex source commits for
  NEXUS, FED and ORACLE. The start path verifies commit and origin identities.
  No runtime GitHub fetches. Source provenance pinning is not authorship or
  semantic-truth certification.

All endpoints except `GET /healthz` and static operator assets require a
valid, locally generated bearer token. The operator browser stores the bearer
only in memory. Strict same-origin check, response no-store headers, bounded
input and output, bounded concurrency and explicit API route allowlists apply.
No CORS. Operator functionality is hosted at Render's same HTTPS origin;
GitHub Pages is **not** granted cross-origin API access.

## Before creating a Render service

1. Review PR, verify exact commit and green CI, then merge.
2. Generate a random **operator token locally** (do not put it in GitHub or a
   ChatGPT message):

   ```bash
   python3 - <<'PY'
   import hashlib, secrets
   token = secrets.token_urlsafe(48)
   print("Save this privately as your operator token:")
   print(token)
   print("Set QSOL_GATEWAY_TOKEN_SHA256 to:")
   print("sha256:" + hashlib.sha256(token.encode()).hexdigest())
   PY
   ```

3. Open Render Blueprint for the merged `QSOL-CONTROL` repository and confirm
   **only one new Free Python web service**, `qsol-control-edge` in Singapore.
   If Free is unavailable, **do not accept a paid fallback**.
4. Supply the SHA-256 digest **only** in the Render secret environment variable
   `QSOL_GATEWAY_TOKEN_SHA256`; keep the raw token private.
5. Ensure the public hostname is `qsol-control-edge.onrender.com` or use
   `QSOL_EDGE_PUBLIC_HOST` set to the actual exact DNS host if Render chose
   another name. Do not place a URL or scheme there.
6. Apply the Blueprint, inspect build output, check Render health
   `/healthz`, open the service root, authenticate using your raw token and
   run an inspection. Confirm only `control.health` and
   `control.capabilities` can be accessed through `/v1/agent`.
7. Check the service status, logs, billing and public response; only then
   claim it is live. In Render, keep `afterzero-arena` suspended.

## Local checks

```sh
python3 -B -m unittest discover -s deployment -p 'test_*.py' -v
python3 -B tools/validate_control.py
python3 -B tools/validate_extensions.py
python3 -B -m deployment.pinned_sources   # explicitly downloads pinned public sources
python3 -B -m deployment.pinned_sources --verify
python3 -B -m deployment.edge --probe
```

To validate the Blueprint itself, run the Render CLI:

```sh
render blueprints validate render.yaml
```

The GitHub workflow runs focused adversarial HTTP tests and the real
read-only donor probe. Full CONTROL release CI remains separate.

## Operational boundaries and residual risk

- This Free Render instance has an **ephemeral filesystem**. CONTROL audit
  files and all process state are lost on restart/redeploy/idle spin-down.
  Hence it does **not** meet the durable-audit requirements of a production
  multi-user deployment, even though the reference gateway records
  per-request audit while the process runs.
- Free instances have monthly bandwidth/build limits and cold starts.
  Avoid paid plans or disks without a separate budget decision.
- The gateway does not allow public NEXUS `council.run`, FED peer transport,
  ORACLE ledger mutation, CONTROL File/Collection writes, replay execution,
  model inference, or provider credential enrollment.
- There is deliberately no untrusted forwarded-IP or shared proxy-socket IP
  quota. Only a validated CONTROL principal is charged the 35-request/minute
  per-process limit. Authentication failures cannot consume another operator's
  quota. Anonymous traffic is constrained only by bounded sockets/timeouts and
  Render's upstream controls; it may still cause denial of service.
- Process-local counters reset on restart. There is no distributed rate limit.
  Do not handle sensitive personal records or production operator workflows
  until stronger controls exist.
- Source pin verification compares **every tracked worktree blob** with its
  Git HEAD object identity, and rejects any extra file including ignored
  shadow modules or bytecode. Build/probe/runtime use Python `-B` to avoid
  writing `__pycache__` under pinned donor trees. The startup guard rejects
  drift rather than repairing it silently.
- The origin service delegates TLS to Render's managed edge and accepts only
  HTTPS-originated requests as indicated by Render's forwarding header; it
  must not be made directly accessible on a raw host port.
- A valid hash, signed envelope, recorded event, evidence search, FED
  conformance result, or unanimous Council vote creates **no semantic authority**.

```text
READONLY_GATEWAY != PERSISTENT_WORLD
SDK_CONFORMANCE != LIVE_FEDERATION
AUTHENTICATED != AUTHORITATIVE
AUDIT_ON_EPHEMERAL_FS != DURABLE_AUDIT
SOURCE_PIN != SEMANTIC_TRUTH
```
