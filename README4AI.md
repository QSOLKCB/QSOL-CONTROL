{
  "document_type": "qsol-control-ai-bootstrap",
  "schema_version": 2,
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
    "operator_orchestration": "owned_by_control",
    "file_and_collection_storage_mechanics": "owned_by_control",
    "search_index_authority": "none"
  },
  "interfaces": {
    "human": "webui_planned",
    "ai": "structured_machine_api_planned",
    "storage_cli": "tools/storage_cli.py",
    "epistemic_authority_rule": "human_and_ai_callers_receive_equal_epistemic_authority"
  },
  "contracts": {
    "json_schema_draft": "https://json-schema.org/draft/2020-12/schema",
    "schema_versioning": "semantic-versioning",
    "schema_version": "1.1.0",
    "python_minimum": "3.11",
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
    "SEARCH_SCORE != TRUTH",
    "SEMANTIC_SIMILARITY != EVIDENCE_STRENGTH",
    "INDEX != CANONICAL_MEMORY",
    "COLLECTION_MEMBERSHIP != ENDORSEMENT",
    "LATTICE_ADDRESS != COLLECTION_MEMBERSHIP",
    "DNA_ENCODING != BIOLOGICAL_CLAIM",
    "PHI_TRAVERSAL != PHYSICAL_TRUTH",
    "CONTROL_MUST_NOT_REWRITE_ORACLE_HISTORY",
    "CONTROL_MUST_NOT_CHANGE_NEXUS_VOTES",
    "MODEL_STATE != MODEL_MIND",
    "VISIBLE_OUTPUT != HIDDEN_CHAIN_OF_THOUGHT",
    "GEOMETRY != TRUTH"
  ],
  "question_modes": ["evidence_only", "council"],
  "persistent_storage": {
    "status": "phase1_files_and_collections_implemented",
    "runtime": "storage/control_store.py",
    "file_definition": "immutable metadata record referencing content-addressed raw bytes",
    "collection_definition": "persistent named group of file references with immutable membership snapshots",
    "object_identity": "sha256(raw_bytes)",
    "collection_membership_order": "lexicographically_sorted_file_ids",
    "collection_history": "immutable_snapshot_chain_plus_atomic_head_pointer",
    "canonical_fingerprint_excludes_rebuildable_search_indexes": true,
    "search": {
      "deterministic_baseline": "qsol.term-frequency-cosine/1",
      "semantic_vector_search": "qsol.cosine-vector-search/1",
      "embedding_generation": "external_adapter_required",
      "index_binding": "exact_collection_snapshot_id",
      "stale_semantic_index": "fail_closed",
      "score_semantics": "retrieval_similarity_only"
    },
    "dna_lattice_projection": {
      "protocol": "qsol-control-dna-lattice/1",
      "codec": "qsol.dna-2bit-codon64/1",
      "alphabet": ["A", "C", "G", "T"],
      "bit_mapping": {"A": "00", "C": "01", "G": "10", "T": "11"},
      "bases_per_byte": 4,
      "bases_per_codon": 3,
      "codon_slots": 64,
      "outer_addressing": "3x3x3_ternary_lattice_27_cells",
      "lexicographic_traversal": "qsol.lexicographic-27/1",
      "phi_gated_traversal": "qsol.phi-stride-27/1",
      "phi_stride": 17,
      "raw_bytes_remain_canonical": true,
      "derived": true,
      "rebuildable": true,
      "authority": "none",
      "compression_claim": false
    }
  },
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
      "file_refs",
      "collection_snapshot_refs",
      "timestamps"
    ],
    "must_not_claim": [
      "hidden_model_reasoning",
      "truth_from_consensus",
      "truth_from_search_similarity",
      "replayability_of_live_stochastic_inference_without_evidence"
    ]
  },
  "validation": {
    "command": "python3 tools/validate_control.py",
    "tests": "python3 -W default -m unittest discover -s tests -v",
    "valid_and_invalid_fixtures_are_executable_contracts": true,
    "dna_projection_round_trip_tests": true
  },
  "read_next": [
    "manifest.json",
    "ai/constitution.json",
    "ai/lattice-contract.json",
    "docs/PERSISTENT-STORAGE.md",
    "ARCHITECTURE.md",
    "SECURITY.md",
    "AGENTS.md",
    "ROADMAP.md"
  ]
}
