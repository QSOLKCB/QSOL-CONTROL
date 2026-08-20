import json
import unittest
from pathlib import Path

from api.common import (
    AGENT_API_PROTOCOL,
    AGENT_ERROR_PROTOCOL,
    AGENT_REQUEST_PROTOCOL,
    AGENT_RESPONSE_PROTOCOL,
    OPERATIONS,
)

ROOT = Path(__file__).resolve().parents[1]


class AgentAPIContractTests(unittest.TestCase):
    def load(self, relative):
        return json.loads((ROOT / relative).read_text(encoding="utf-8"))

    def test_contract_matches_runtime_operation_catalogue(self):
        contract = self.load("ai/agent-api-contract.json")
        self.assertEqual(contract["protocol"], AGENT_API_PROTOCOL)
        self.assertEqual(contract["request_protocol"], AGENT_REQUEST_PROTOCOL)
        self.assertEqual(contract["response_protocol"], AGENT_RESPONSE_PROTOCOL)
        self.assertEqual(contract["error_protocol"], AGENT_ERROR_PROTOCOL)
        self.assertEqual(
            [item["name"] for item in contract["operations"]], list(OPERATIONS)
        )
        self.assertEqual(contract["transport"], "jsonl-stdio")
        self.assertFalse(contract["remote_multi_user_deployment"])

    def test_contract_preserves_authority_firewall(self):
        contract = self.load("ai/agent-api-contract.json")
        forbidden = contract["forbidden_surfaces"]
        self.assertEqual(forbidden["oracle_write_operations"], [])
        self.assertFalse(forbidden["nexus_arbitrary_operation_passthrough"])
        self.assertFalse(forbidden["nexus_worldstore_mutation"])
        self.assertFalse(forbidden["nexus_vote_weight_override"])
        self.assertFalse(forbidden["nexus_ballot_override"])
        self.assertFalse(forbidden["nexus_consensus_threshold_override"])
        self.assertFalse(forbidden["hidden_chain_of_thought"])
        self.assertFalse(forbidden["model_mind"])
        self.assertFalse(forbidden["synthetic_truth_score"])
        self.assertTrue(contract["caller_authority"]["equal_epistemic_privilege"])
        self.assertIn(
            "HUMAN_CALLER_AUTHORITY == AI_CALLER_AUTHORITY", contract["invariants"]
        )

    def test_request_and_response_schemas_pin_protocols_and_operations(self):
        request = self.load("schema/agent-api-request.schema.json")
        response = self.load("schema/agent-api-response.schema.json")
        self.assertEqual(request["properties"]["protocol"]["const"], AGENT_REQUEST_PROTOCOL)
        self.assertEqual(request["properties"]["operation"]["enum"], list(OPERATIONS))
        protocols = {
            branch["properties"]["protocol"]["const"] for branch in response["oneOf"]
        }
        self.assertEqual(protocols, {AGENT_RESPONSE_PROTOCOL, AGENT_ERROR_PROTOCOL})

    def test_manifest_and_ai_bootstrap_register_phase6(self):
        manifest = self.load("manifest.json")
        bootstrap = self.load("README4AI.md")
        self.assertEqual(manifest["agent_api_contract"], "ai/agent-api-contract.json")
        self.assertEqual(manifest["agent_api_document"], "docs/AGENT-API.md")
        self.assertEqual(manifest["interfaces"]["ai"], "structured-jsonl-stdio-api")
        self.assertEqual(manifest["validation"]["agent_api_command"], "python3 tools/agent_api.py")
        self.assertEqual(bootstrap["interfaces"]["ai"], "structured_jsonl_stdio_api")
        self.assertEqual(bootstrap["agent_api"]["status"], "implemented_phase6")
        self.assertTrue(bootstrap["agent_api"]["human_ai_epistemic_authority_equal"])

    def test_phase6_roadmap_is_complete_without_claiming_phase7(self):
        roadmap = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")
        phase6 = roadmap.split("## Phase 6 — AI / agent API", 1)[1].split(
            "## Phase 7 — Replay and longitudinal research", 1
        )[0]
        self.assertNotIn("- [ ]", phase6)
        phase7 = roadmap.split("## Phase 7 — Replay and longitudinal research", 1)[1]
        self.assertIn("- [ ] Implement replay classification.", phase7)


if __name__ == "__main__":
    unittest.main()
