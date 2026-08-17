{
  "document_type": "qsol-control-ai-bootstrap",
  "schema_version": 1,
  "protocol": "QSOL-CONTROL/0.1",
  "audience": ["ai", "agents", "automated_reviewers", "tooling"],
  "human_document": "README.md",
  "machine_entrypoint": "manifest.json",
  "role": "human_and_ai_control_plane",
  "verbs": {
    "QSOL-SUBSTRATE": "KNOWS",
    "QSOL-ARK": "SURVIVES",
    "QSOL-INT": "COMPOSES",
    "QSOL-ORACLE": "WITNESSES",
    "QSOL-NEXUS": "REASONS",
    "QSOL-CONTROL": "OPERATES",
    "LATTICE_MEMORY": "REMEMBERS"
  },
  "authority": {
    "semantic": "none",
    "evidence": "none",
    "council_vote": "none",
    "oracle_history": "none",
    "recovery": "none",
    "operator_orchestration": "owned_by_control"
  },
  "interfaces": {
    "human": "webui",
    "ai": "structured_machine_api",
    "epistemic_authority_rule": "human_and_ai_callers_receive_equal_epistemic_authority"
  },
  "contracts": {
    "json_schema_draft": "https://json-schema.org/draft/2020-12/schema",
    "schema_versioning": "semantic-versioning",
    "schema_version": "1.0.0",
    "python_minimum_for_phase0_validation": "3.11",
    "canonical_examples": "examples/schema/",
    "unknown_major_or_lattice_profile": "fail_closed_do_not_guess_semantics"
  },
  "core_invariants": [
    "CONTROL_DISPLAY != AUTHORITY",
    "CONTROL_OPERATION != TRUTH",
    "VOTE != EVIDENCE",
    "CONSENSUS != TRUTH",
    "CONFIDENCE != PROBABILITY",
    "STORED != TRUE",
    "PERSISTED != CANONICAL",
    "MODEL_STATE != EVIDENCE",
    "AI_RESPONSE != FACT",
    "MEMORY != AUTHORITY",
    "CONTROL_MUST_NOT_REWRITE_ORACLE_HISTORY",
    "CONTROL_MUST_NOT_CHANGE_NEXUS_VOTES",
    "MODEL_STATE != MODEL_MIND",
    "VISIBLE_OUTPUT != HIDDEN_CHAIN_OF_THOUGHT",
    "GEOMETRY != TRUTH"
  ],
  "question_modes": ["evidence_only", "council"],
  "lattice": {
    "name": "qsol-3x3x3-sierpinski-derived-memory",
    "profile": "qsol-3x3x3-sierpinski-derived-memory/1",
    "top_level_cells": 27,
    "authority": "storage_only",
    "axes": {
      "x_information_role": ["question", "response", "evidence"],
      "y_epistemic_role": ["observed", "derived", "unresolved"],
      "z_temporal_role": ["current", "historical", "recovery"]
    },
    "recursive_addressing": true,
    "literal_sierpinski_claim": false,
    "migration_rule": "preserve_original_profile_and_address; use_explicit_migration_receipt"
  },
  "model_state": {
    "purpose": "future_ai_archaeology_and_reproducibility",
    "captures_hidden_chain_of_thought": false,
    "privacy_classes": ["PUBLIC", "INTERNAL", "RESTRICTED", "FORBIDDEN"],
    "retention_classes": ["TRANSIENT", "SESSION", "ARCHIVE"],
    "redaction_before_durable_storage": true,
    "credentials_are_forbidden_persistence": true,
    "captures_when_available": [
      "provider",
      "runtime",
      "model_id",
      "revision",
      "weight_hash",
      "tokenizer_identity",
      "quantization",
      "context_limit",
      "sampling_parameters",
      "seed",
      "council_seat",
      "mode",
      "tool_permissions",
      "nexus_identity",
      "oracle_identity",
      "substrate_identity",
      "control_run_id",
      "execution_timestamp",
      "relevant_runtime_hardware_metadata"
    ]
  },
  "run_record": {
    "preserve": [
      "question",
      "requester_kind",
      "admitted_evidence_refs",
      "council_roster",
      "visible_model_outputs",
      "sealed_votes",
      "consensus_status",
      "minority_reports",
      "oracle_receipts",
      "model_states",
      "lattice_addresses",
      "timestamps"
    ],
    "must_not_claim": [
      "hidden_model_reasoning",
      "truth_from_consensus",
      "replayability_of_live_stochastic_inference_without_evidence"
    ]
  },
  "validation": {
    "command": "python3 tools/validate_control.py",
    "tests": "python3 -W default -m unittest discover -s tests -v",
    "valid_and_invalid_fixtures_are_executable_contracts": true
  },
  "read_next": [
    "manifest.json",
    "ai/constitution.json",
    "ai/lattice-contract.json",
    "ARCHITECTURE.md",
    "SECURITY.md",
    "AGENTS.md",
    "ROADMAP.md"
  ]
}
