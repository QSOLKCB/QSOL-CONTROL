import unittest

from storage.restore_capsule import (
    MAGIC,
    RestoreCapsuleError,
    capsule_contains_restricted,
    decode_capsule_dna,
    encode_capsule_dna,
    pack_capsule,
    parse_capsule,
    recovery_schedule,
    verify_capsule,
)


class RestoreCapsuleTests(unittest.TestCase):
    def entries(self):
        return [
            {
                "logical_path": "identity/context.json",
                "data": b'{"preferred_name":"Trent"}\n',
                "kind": "json",
                "privacy_class": "RESTRICTED",
                "recovery_class": "NEAR_SHELL",
                "source_ref": "QSOL-CONTEXT:identity/context.json",
            },
            {
                "logical_path": "ai/honesty-contract.json",
                "data": b'{"invariant":"CLAIMED_EXECUTION != EXECUTED"}\n',
                "kind": "contract",
                "privacy_class": "INTERNAL",
                "recovery_class": "MID_SHELL",
                "source_ref": "QSOL-CONTEXT:ai/honesty-contract.json",
            },
            {
                "logical_path": "history/corpus-fingerprint.json",
                "data": b'{"history":"optional"}\n',
                "kind": "json",
                "privacy_class": "RESTRICTED",
                "recovery_class": "OUTER_SHELL",
                "source_ref": "QSOL-CORPUS:restore/profile.json",
            },
            {
                "logical_path": "recovery/canary.txt",
                "data": b"fair dinkum\n",
                "kind": "text",
                "privacy_class": "PUBLIC",
                "recovery_class": "RESONANCE_NODE",
                "source_ref": "QSOL-ARK:capsules/minimal/ARK-CANARY.txt",
            },
            {
                "logical_path": "recovery/optional-note.txt",
                "data": b"optional historical detail\n",
                "kind": "text",
                "privacy_class": "INTERNAL",
                "recovery_class": "WIGGLE_ZONE",
                "source_ref": "synthetic:test",
            },
        ]

    def test_pack_is_byte_deterministic_independent_of_input_order(self):
        forward = pack_capsule(self.entries())
        reverse = pack_capsule(list(reversed(self.entries())))
        self.assertEqual(forward, reverse)
        self.assertTrue(forward.startswith(MAGIC))

    def test_verify_is_fixed_point_and_preserves_hashes(self):
        capsule = pack_capsule(self.entries())
        report = verify_capsule(capsule)
        self.assertEqual(report["status"], "verified")
        self.assertTrue(report["fixed_point"])
        self.assertEqual(report["entry_count"], 5)
        manifest, extracted = parse_capsule(capsule)
        self.assertEqual(len(extracted), 5)
        self.assertEqual(manifest["authority"], "none")

    def test_recovery_schedule_uses_qec_shell_order_then_utf8_path(self):
        capsule = pack_capsule(self.entries())
        self.assertEqual(
            recovery_schedule(capsule),
            (
                "identity/context.json",
                "ai/honesty-contract.json",
                "history/corpus-fingerprint.json",
                "recovery/canary.txt",
                "recovery/optional-note.txt",
            ),
        )

    def test_phi_shell_progression_is_pinned_in_manifest(self):
        capsule = pack_capsule(self.entries())
        manifest, _ = parse_capsule(capsule)
        shells = {entry["recovery_class"]: entry["phi_shell_milli"] for entry in manifest["entries"]}
        self.assertEqual(shells["NEAR_SHELL"], 1000)
        self.assertEqual(shells["MID_SHELL"], 1618)
        self.assertEqual(shells["OUTER_SHELL"], 2618)
        self.assertEqual(shells["RESONANCE_NODE"], 4236)
        self.assertEqual(shells["WIGGLE_ZONE"], 6854)
        self.assertEqual(1000 + 1618, 2618)
        self.assertEqual(1618 + 2618, 4236)
        self.assertEqual(2618 + 4236, 6854)

    def test_tampered_payload_fails_verification(self):
        capsule = bytearray(pack_capsule(self.entries()))
        capsule[-1] ^= 1
        with self.assertRaisesRegex(RestoreCapsuleError, "payload hash"):
            verify_capsule(bytes(capsule))

    def test_path_traversal_is_rejected(self):
        entry = dict(self.entries()[0])
        entry["logical_path"] = "../identity.json"
        with self.assertRaisesRegex(RestoreCapsuleError, "parent"):
            pack_capsule([entry])

    def test_duplicate_logical_path_is_rejected(self):
        duplicate = [self.entries()[0], dict(self.entries()[0])]
        with self.assertRaisesRegex(RestoreCapsuleError, "unique"):
            pack_capsule(duplicate)

    def test_restricted_content_is_detectable(self):
        self.assertTrue(capsule_contains_restricted(pack_capsule(self.entries())))

    def test_restore_capsule_dna_round_trip(self):
        capsule = pack_capsule(self.entries())
        projection = encode_capsule_dna(capsule)
        self.assertEqual(decode_capsule_dna(projection), capsule)
        self.assertEqual(projection["restore_capsule_sha256"], verify_capsule(capsule)["capsule_sha256"])

    def test_restore_capsule_does_not_claim_model_identity(self):
        capsule = pack_capsule(self.entries())
        manifest, _ = parse_capsule(capsule)
        self.assertIn("RESTORED_CONTEXT != ORIGINAL_ASSISTANT_INSTANCE", manifest["boundaries"])
        self.assertIn("RESTORE_CAPSULE != MODEL_MEMORY", manifest["boundaries"])


if __name__ == "__main__":
    unittest.main()
