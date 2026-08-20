{
  "document_type": "qsol-control-extension-ai-bootstrap",
  "schema_version": 1,
  "protocol": "qsol-control-post-roadmap-extensions/1",
  "core_entrypoint": "../manifest.json",
  "core_contract_version": "2.6.0",
  "extension_entrypoint": "manifest.json",
  "human_document": "../docs/POST-ROADMAP-EXTENSIONS.md",
  "extension_surfaces": [
    "authenticated_remote_agent_gateway",
    "ios_swiftui_reference_client",
    "android_kotlin_reference_client",
    "external_consensus_coordination_adapter"
  ],
  "permanent_nongoals": "../ai/permanent-nongoals.json",
  "authority": "none",
  "read_next": [
    "manifest.json",
    "../ai/remote-gateway-contract.json",
    "../ai/mobile-client-contract.json",
    "../ai/consensus-adapter-contract.json",
    "../ai/permanent-nongoals.json",
    "../docs/POST-ROADMAP-EXTENSIONS.md"
  ],
  "invariants": [
    "CORE_2_6_0 != EXTENSION_SURFACE",
    "REMOTE_ACCESS != EPISTEMIC_PRIVILEGE",
    "CONSENSUS_RECEIPT != SEMANTIC_AUTHORITY",
    "MOBILE_CLIENT != CONTROL_AUTHORITY",
    "AUTOMATIC_TRUTH_SCORING = FORBIDDEN",
    "HIDDEN_CHAIN_OF_THOUGHT_CAPTURE = FORBIDDEN"
  ]
}
