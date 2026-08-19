import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


class NexusAdapterContractTests(unittest.TestCase):
    def load(self, relative):
        return json.loads((ROOT / relative).read_text(encoding="utf-8"))

    def test_manifest_registers_phase3_surfaces(self):
        manifest = self.load("manifest.json")
        # Phase-specific tests pin the NEXUS surfaces, not the repository's
        # forever-global schema version. Later phases may legitimately advance
        # that version under the manifest semantic-versioning policy.
        self.assertRegex(manifest["schema_version"], SEMVER_RE)
        self.assertEqual(
            manifest["nexus_adapter_contract"], "ai/nexus-adapter-contract.json"
        )
        self.assertEqual(
            manifest["nexus_adapter_document"], "docs/NEXUS-ADAPTER.md"
        )
        self.assertEqual(
            manifest["interfaces"]["nexus_adapter_cli"], "tools/nexus_adapter.py"
        )
        self.assertEqual(
            manifest["schemas"]["nexus_discovery"],
            "schema/nexus-discovery.schema.json",
        )
        self.assertEqual(
            manifest["schemas"]["nexus_council_response"],
            "schema/nexus-council-response.schema.json",
        )
        self.assertGreaterEqual(
            manifest["status"]["completed_through_roadmap_phase"], 3
        )
        self.assertEqual(
            manifest["status"]["live_nexus_adapter"],
            "implemented-phase-3-local-jsonl",
        )

    def test_machine_contract_preserves_nexus_governance(self):
        contract = self.load("ai/nexus-adapter-contract.json")
        self.assertEqual(contract["protocol"], "qsol-control-nexus-adapter/1")
        surface = contract["control_surface"]
        self.assertEqual(surface["mutation_operations"], ["council.run"])
        self.assertFalse(surface["world_create_exposed"])
        self.assertFalse(surface["arbitrary_operation_passthrough"])
        self.assertFalse(surface["stenographer_operations_used"])

        gate = contract["governance_gate"]
        self.assertFalse(gate["control_can_alter_vote_weight"])
        self.assertFalse(gate["control_can_alter_ballot_contents"])
        self.assertFalse(gate["control_can_alter_roster_authority"])
        self.assertFalse(gate["control_can_alter_consensus_threshold"])
        self.assertFalse(gate["control_can_rewrite_worldstore_history"])
        self.assertTrue(gate["nexus_owns_worldstore_history"])
        self.assertTrue(gate["nexus_owns_council_governance"])

        hidden = contract["hidden_reasoning"]
        self.assertFalse(hidden["capture"])
        self.assertFalse(hidden["request"])
        self.assertFalse(hidden["stenographer_read"])

    def test_public_schemas_pin_no_control_governance_escalation(self):
        discovery = self.load("schema/nexus-discovery.schema.json")
        props = discovery["properties"]
        self.assertEqual(props["adapter_mutation_operations"]["const"], ["council.run"])
        self.assertFalse(props["direct_worldstore_mutation_exposed"]["const"])
        self.assertEqual(props["governance_override_operations"]["const"], [])
        self.assertFalse(props["hidden_chain_of_thought_capture"]["const"])

        response = self.load("schema/nexus-council-response.schema.json")
        governance = response["properties"]["governance"]["properties"]
        self.assertFalse(governance["control_direct_worldstore_mutation"]["const"])
        self.assertFalse(governance["control_ballot_override"]["const"])
        self.assertFalse(governance["control_threshold_override"]["const"])
        self.assertFalse(governance["control_vote_weight_override"]["const"])
        self.assertEqual(
            response["properties"]["hidden_chain_of_thought_captured"]["const"],
            False,
        )


if __name__ == "__main__":
    unittest.main()
