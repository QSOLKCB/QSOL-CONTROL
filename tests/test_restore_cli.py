import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "tools" / "restore_cli.py"


class RestoreCliTests(unittest.TestCase):
    def run_cli(self, *args, check=True):
        result = subprocess.run(
            [sys.executable, str(CLI), *map(str, args)],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        if check and result.returncode != 0:
            self.fail(f"CLI failed ({result.returncode})\nstdout={result.stdout}\nstderr={result.stderr}")
        return result

    def write_spec(self, root: Path) -> Path:
        (root / "identity").mkdir(parents=True)
        (root / "identity" / "context.json").write_text(
            '{"preferred_name":"Trent"}\n', encoding="utf-8"
        )
        spec = {
            "protocol": "qsol-control-restore-pack-spec/1",
            "capsule": "identity.dat",
            "recovery_class": "NEAR_SHELL",
            "entries": [
                {
                    "logical_path": "identity/context.json",
                    "source_path": "identity/context.json",
                    "kind": "json",
                    "privacy_class": "RESTRICTED",
                    "recovery_class": "NEAR_SHELL",
                    "source_ref": "synthetic:test",
                }
            ],
        }
        spec_path = root / "identity.pack.json"
        spec_path.write_text(json.dumps(spec), encoding="utf-8")
        return spec_path

    def test_pack_verify_unpack_and_dna_round_trip(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            spec = self.write_spec(root)
            capsule = root / "identity.dat"
            packed = self.run_cli(
                "pack", "--spec", spec, "--source-root", root, "--output", capsule
            )
            packed_report = json.loads(packed.stdout)
            self.assertEqual(packed_report["status"], "verified")
            self.assertTrue(capsule.is_file())

            verified = self.run_cli("verify", capsule)
            verified_report = json.loads(verified.stdout)
            self.assertTrue(verified_report["fixed_point"])
            self.assertEqual(verified_report["entry_count"], 1)

            unpacked = root / "unpacked"
            self.run_cli("unpack", capsule, "--output-dir", unpacked)
            self.assertEqual(
                (unpacked / "identity" / "context.json").read_text(encoding="utf-8"),
                '{"preferred_name":"Trent"}\n',
            )

            dna = root / "identity.dna.json"
            rejected = self.run_cli("dna-export", capsule, "--output", dna, check=False)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("--allow-restricted", rejected.stderr)

            self.run_cli(
                "dna-export",
                capsule,
                "--output",
                dna,
                "--allow-restricted",
                "--acknowledge-reversible-sensitive-export",
            )
            rebuilt = root / "identity.rebuilt.dat"
            self.run_cli("dna-decode", dna, "--output", rebuilt)
            self.assertEqual(rebuilt.read_bytes(), capsule.read_bytes())

    def test_pack_source_root_escape_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            safe = root / "safe"
            safe.mkdir()
            outside = root / "outside.txt"
            outside.write_text("nope", encoding="utf-8")
            spec = {
                "protocol": "qsol-control-restore-pack-spec/1",
                "capsule": "escape.dat",
                "recovery_class": "NEAR_SHELL",
                "entries": [
                    {
                        "logical_path": "outside.txt",
                        "source_path": "../outside.txt",
                        "kind": "text",
                        "privacy_class": "INTERNAL",
                        "recovery_class": "NEAR_SHELL",
                        "source_ref": "synthetic:test",
                    }
                ],
            }
            spec_path = safe / "escape.pack.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            result = self.run_cli(
                "pack",
                "--spec",
                spec_path,
                "--source-root",
                safe,
                "--output",
                safe / "escape.dat",
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("escapes the declared source root", result.stderr)


if __name__ == "__main__":
    unittest.main()
