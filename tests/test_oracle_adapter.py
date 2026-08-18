import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from adapters.oracle import (
    FEED_PROTOCOL,
    OracleAdapter,
    OracleAdapterError,
)
from storage.control_store import ControlStore, canonical_json_bytes

BASE_TIME = "2026-08-19T08:00:00+09:30"


def canonical_hash(value):
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def make_event(
    sequence,
    *,
    event_id,
    subject,
    state,
    observed_at,
    previous_hash,
    payload_sha256=None,
    provenance_kind="primary_observation",
    event_type="evidence.observed",
):
    event = {
        "protocol": "QSOL-ORACLE/1",
        "sequence": sequence,
        "event_id": event_id,
        "event_type": event_type,
        "subject": subject,
        "observed_at": observed_at,
        "source": {"kind": "fixture", "locator": f"fixture:{event_id}"},
        "provenance_kind": provenance_kind,
        "evidence": {"state": state, "payload_sha256": payload_sha256},
        "authority": "observation-only",
        "previous_hash": previous_hash,
        "note": "fixture",
    }
    event["event_hash"] = canonical_hash(event)
    return event


class OracleAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.oracle = self.root / "oracle"
        self.oracle.mkdir()
        (self.oracle / "ledger").mkdir()
        (self.oracle / "contracts").mkdir()

        self.contract = {
            "protocol": "QSOL-TIMELOCK/1",
            "contract_id": "qsol-context-publication-2056",
            "subject": "QSOLKCB/QSOL-CONTEXT",
            "created_at": "2026-08-18T06:18:00+09:30",
            "not_before": "2056-08-18T00:00:00+09:30",
            "states": ["locked", "eligible", "blocked", "executed"],
            "preconditions": ["deadline_reached", "publication_clearance_receipt_valid"],
            "fail_closed": True,
            "credential_policy": {"store_long_lived_credentials": False},
        }
        (self.oracle / "contracts" / "qsol-context-2056.json").write_bytes(
            canonical_json_bytes(self.contract)
        )
        contract_sha = canonical_hash(self.contract)

        events = []
        genesis = make_event(
            0,
            event_id="oracle.genesis",
            subject="QSOLKCB/QSOL-ORACLE",
            state="observed",
            observed_at="2026-08-19T07:55:00+09:30",
            previous_hash=None,
            provenance_kind="metadata",
            event_type="oracle.genesis",
        )
        events.append(genesis)
        timelock = make_event(
            1,
            event_id="timelock.qsol-context.2056",
            subject="QSOLKCB/QSOL-CONTEXT",
            state="observed",
            observed_at="2026-08-19T07:56:00+09:30",
            previous_hash=genesis["event_hash"],
            payload_sha256=contract_sha,
            event_type="timelock.directive_recorded",
        )
        events.append(timelock)
        known = make_event(
            2,
            event_id="known.fixture",
            subject="fixture:known",
            state="observed",
            observed_at="2026-08-19T08:00:00+09:30",
            previous_hash=timelock["event_hash"],
            payload_sha256="a" * 64,
        )
        events.append(known)
        conflict = make_event(
            3,
            event_id="conflict.fixture",
            subject="fixture:conflict",
            state="conflict",
            observed_at="2026-08-19T08:01:00+09:30",
            previous_hash=known["event_hash"],
            payload_sha256="b" * 64,
        )
        events.append(conflict)
        (self.oracle / "ledger" / "events.jsonl").write_text(
            "\n".join(
                json.dumps(event, sort_keys=True, separators=(",", ":"))
                for event in events
            )
            + "\n",
            encoding="utf-8",
        )
        self.events = events

        self.manifest = {
            "type": "qsol-oracle-manifest",
            "protocol": "QSOL-ORACLE/1",
            "schema_version": "1.1.0",
            "ledger_model": "single-writer-append-only",
            "ledger": "ledger/events.jsonl",
            "founding_timelock": "contracts/qsol-context-2056.json",
            "response_states": ["known", "conflict", "unknown"],
            "provenance_kinds": [
                "primary_observation",
                "derived_statement",
                "correction",
                "supersession",
                "metadata",
            ],
            "freshness_states": ["fresh", "stale", "undated", "future-dated"],
            "feed_schema": "schema/feed-receipt.schema.json",
            "collectors": ["github.repository"],
        }
        (self.oracle / "manifest.json").write_bytes(canonical_json_bytes(self.manifest))
        self.adapter = OracleAdapter(self.oracle)

    def tearDown(self):
        self.temp.cleanup()

    def tree_fingerprint(self):
        rows = []
        for path in sorted(p for p in self.oracle.rglob("*") if p.is_file()):
            rows.append(
                (
                    path.relative_to(self.oracle).as_posix(),
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                )
            )
        return rows

    def test_discovery_is_read_only_and_reports_protocol(self):
        report = self.adapter.discover()
        self.assertEqual(report["availability"], "available")
        self.assertEqual(report["oracle_protocol"], "QSOL-ORACLE/1")
        self.assertEqual(report["write_capabilities"], [])
        self.assertIn("timelock-status", report["capabilities"])
        self.assertIn("feed-receipt-verification", report["capabilities"])

    def test_exact_subject_queries_return_known_conflict_unknown(self):
        known = self.adapter.query_evidence(
            "fixture:known",
            evaluated_at="2026-08-19T08:05:00+09:30",
            max_age_seconds=600,
        )
        conflict = self.adapter.query_evidence(
            "fixture:conflict",
            evaluated_at="2026-08-19T08:05:00+09:30",
            max_age_seconds=600,
        )
        unknown = self.adapter.query_evidence(
            "fixture:absent",
            evaluated_at="2026-08-19T08:05:00+09:30",
            suggested_searches=["primary source for fixture:absent"],
        )
        self.assertEqual(known["state"], "known")
        self.assertEqual(conflict["state"], "conflict")
        self.assertEqual(unknown["state"], "unknown")
        self.assertFalse(unknown["search_suggestions_are_evidence"])
        self.assertEqual(len(known["evidence_refs"]), 1)
        self.assertEqual(
            known["evidence_refs"][0]["event_hash"], self.events[2]["event_hash"]
        )

    def test_freshness_is_visible_but_never_truth_semantics(self):
        fresh = self.adapter.query_evidence(
            "fixture:known",
            evaluated_at="2026-08-19T08:05:00+09:30",
            max_age_seconds=600,
        )
        stale = self.adapter.query_evidence(
            "fixture:known",
            evaluated_at="2026-08-20T08:05:00+09:30",
            max_age_seconds=600,
        )
        future = self.adapter.query_evidence(
            "fixture:known",
            evaluated_at="2026-08-19T07:59:00+09:30",
            max_age_seconds=600,
        )
        self.assertEqual(fresh["freshness"]["state"], "fresh")
        self.assertEqual(stale["freshness"]["state"], "stale")
        self.assertEqual(future["freshness"]["state"], "future-dated")
        self.assertFalse(stale["freshness"]["stale_means_false"])
        self.assertFalse(fresh["freshness"]["fresh_means_true"])

    def test_timelock_view_never_authorizes_execution(self):
        locked = self.adapter.timelock_status(
            evaluated_at="2026-08-19T08:05:00+09:30"
        )
        eligible = self.adapter.timelock_status(
            evaluated_at="2056-08-18T00:00:01+09:30"
        )
        self.assertEqual(locked["state"], "locked")
        self.assertEqual(eligible["state"], "eligible")
        self.assertFalse(locked["execution_authorized"])
        self.assertFalse(eligible["execution_authorized"])
        self.assertTrue(locked["witnessed"])

    def test_tampered_ledger_fails_closed(self):
        ledger = self.oracle / "ledger" / "events.jsonl"
        text = ledger.read_text(encoding="utf-8").replace(
            '"subject":"fixture:known"', '"subject":"fixture:tampered"'
        )
        ledger.write_text(text, encoding="utf-8")
        with self.assertRaisesRegex(OracleAdapterError, "event_hash mismatch"):
            self.adapter.query_evidence("fixture:known", evaluated_at=BASE_TIME)

    def test_feed_receipt_validation_preserves_observation_only_boundary(self):
        observation = {"full_name": "QSOLKCB/QSOL-ORACLE", "private": False}
        receipt = {
            "protocol": FEED_PROTOCOL,
            "collector": "github.repository",
            "subject": "QSOLKCB/QSOL-ORACLE",
            "source": {"locator": "fixture:repo", "payload_sha256": "c" * 64},
            "acquisition": {"mode": "fixture", "fixture_sha256": "d" * 64},
            "freshness": {
                "state": "fresh",
                "source_time": "2026-08-19T08:00:00Z",
                "evaluated_at": "2026-08-19T08:05:00Z",
                "max_age_seconds": 600,
                "age_seconds": 300,
                "stale_means_false": False,
                "fresh_means_true": False,
            },
            "observation": observation,
            "observation_sha256": canonical_hash(observation),
            "authority": "observation-only",
            "truth_claim": False,
        }
        receipt["receipt_sha256"] = canonical_hash(receipt)
        result = self.adapter.validate_feed_receipt(receipt)
        self.assertEqual(result["authority"], "reference-only")
        self.assertEqual(
            result["oracle_receipt_sha256"], receipt["receipt_sha256"]
        )
        tampered = dict(receipt)
        tampered["truth_claim"] = True
        with self.assertRaisesRegex(OracleAdapterError, "semantic truth"):
            self.adapter.validate_feed_receipt(tampered)

    def test_persist_receipt_writes_only_to_control_and_binds_exact_payload(self):
        before = self.tree_fingerprint()
        response = self.adapter.query_evidence(
            "fixture:known",
            evaluated_at="2026-08-19T08:05:00+09:30",
        )
        control_root = self.root / "control-store"
        ref = self.adapter.persist_receipt(
            control_root,
            response,
            source_ref=f"oracle:event:{self.events[2]['event_hash']}",
            created_at="2026-08-19T08:06:00+09:30",
        )
        after = self.tree_fingerprint()
        self.assertEqual(before, after)
        self.assertEqual(ref["authority"], "reference-only")
        store = ControlStore(control_root)
        self.assertEqual(
            store.read_file(ref["file_id"]), canonical_json_bytes(response)
        )
        record = store.get_file_record(ref["file_id"])
        self.assertFalse(record["metadata"]["copied_authority"])
        self.assertEqual(
            record["metadata"]["payload_sha256"],
            hashlib.sha256(canonical_json_bytes(response)).hexdigest(),
        )

    def test_hash_valid_fabricated_oracle_event_cannot_be_cached(self):
        fabricated = make_event(
            4,
            event_id="fabricated.fixture",
            subject="fixture:fabricated",
            state="observed",
            observed_at="2026-08-19T08:02:00+09:30",
            previous_hash=self.events[-1]["event_hash"],
            payload_sha256="e" * 64,
        )
        with self.assertRaisesRegex(OracleAdapterError, "not present in verified parent history"):
            self.adapter.persist_receipt(
                self.root / "control-fabricated",
                fabricated,
                source_ref=f"oracle:event:{fabricated['event_hash']}",
                created_at="2026-08-19T08:06:00+09:30",
            )

    def test_cached_query_response_must_match_verified_historical_ledger(self):
        response = self.adapter.query_evidence(
            "fixture:known",
            evaluated_at="2026-08-19T08:05:00+09:30",
        )
        forged = dict(response)
        forged["state"] = "unknown"
        forged["response_sha256"] = canonical_hash(
            {key: value for key, value in forged.items() if key != "response_sha256"}
        )
        with self.assertRaisesRegex(OracleAdapterError, "state does not match verified history"):
            self.adapter.persist_receipt(
                self.root / "control-forged-query",
                forged,
                source_ref="oracle-query:forged",
                created_at="2026-08-19T08:06:00+09:30",
            )

    def test_raw_timelock_receipt_must_match_witnessed_parent_contract(self):
        altered = dict(self.contract)
        altered["not_before"] = "2057-08-18T00:00:00+09:30"
        with self.assertRaisesRegex(OracleAdapterError, "does not match the parent contract"):
            self.adapter.persist_receipt(
                self.root / "control-forged-timelock",
                altered,
                source_ref="oracle:timelock:forged",
                created_at="2026-08-19T08:06:00+09:30",
            )

    def test_receipt_storage_cannot_overlap_oracle_repository(self):
        response = self.adapter.query_evidence(
            "fixture:known", evaluated_at=BASE_TIME
        )
        with self.assertRaisesRegex(OracleAdapterError, "must not overlap"):
            self.adapter.persist_receipt(
                self.oracle,
                response,
                source_ref="oracle:test",
                created_at=BASE_TIME,
            )

    def test_unknown_protocol_major_fails_closed(self):
        manifest = dict(self.manifest)
        manifest["protocol"] = "QSOL-ORACLE/2"
        (self.oracle / "manifest.json").write_bytes(canonical_json_bytes(manifest))
        with self.assertRaisesRegex(OracleAdapterError, "unsupported ORACLE protocol major"):
            self.adapter.discover()


if __name__ == "__main__":
    unittest.main()
