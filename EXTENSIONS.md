# QSOL-CONTROL Post-Roadmap Extensions

The numbered QSOL-CONTROL core roadmap is complete through Phase 10 and remains contract `2.6.0`.

PR #15 adds optional post-roadmap extension surfaces without changing the completed core authority model:

- authenticated **and record-authorized** remote Agent API gateway with durable principal audit, renewable quotas, bounded connections, Host/TLS controls, and no remote WebUI;
- native iOS/SwiftUI reference client;
- native Android/Kotlin reference client;
- external distributed-consensus coordination adapter with fully validated mutation intents, bounded provider I/O, and post-proposal receipt verification;
- permanent machine-readable prohibitions for truth scoring, hidden chain-of-thought capture, and unsupported lattice/DNA/φ ontology claims.

Machine entrypoint: [`extensions/manifest.json`](extensions/manifest.json).

Detailed boundaries: [`docs/POST-ROADMAP-EXTENSIONS.md`](docs/POST-ROADMAP-EXTENSIONS.md).

```text
CORE_2_6_0 != EXTENSION_SURFACE
AUTHENTICATION != RECORD_AUTHORIZATION
REMOTE_GATEWAY != REMOTE_WEBUI
REMOTE_ACCESS != EPISTEMIC_PRIVILEGE
CONSENSUS_RECEIPT != SEMANTIC_AUTHORITY
MOBILE_CLIENT != CONTROL_AUTHORITY
```
