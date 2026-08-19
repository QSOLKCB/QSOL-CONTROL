#!/usr/bin/env python3
"""Deterministic fake NEXUS JSONL runtime used only by CONTROL adapter tests."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

PHASE_ORDER = ["WHITE", "RED", "BLACK", "YELLOW", "GREEN", "BLUE"]


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def nexus_ref(prefix: str, value: Any) -> str:
    digest = hashlib.sha256(prefix.encode("utf-8") + b"\0" + canonical_bytes(value)).hexdigest()
    return f"{prefix}:{digest}"


class FakeNexus:
    def __init__(
        self,
        *,
        tamper: str | None = None,
        runtime_version: str = "2.0.0",
    ) -> None:
        self.objects: dict[str, dict[str, Any]] = {}
        self.tamper = tamper
        self.runtime_version = runtime_version
        self.operations_seen: list[str] = []

    def create_object(
        self,
        object_type: str,
        payload: dict[str, Any],
        provenance: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = {
            "object_type": object_type,
            "payload": payload,
            "provenance": provenance or {"actor": "nexus"},
        }
        object_id = nexus_ref("object", body)
        obj = {"object_id": object_id, **body}
        self.objects[object_id] = obj
        return obj

    def _with_request_id(self, request: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
        request_id = request.get("request_id")
        return ({"request_id": request_id, **response} if request_id is not None else response)

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        operation = request.get("operation")
        if isinstance(operation, str):
            self.operations_seen.append(operation)
        if operation == "system.health":
            return self._with_request_id(
                request,
                {
                    "status": "ok",
                    "protocol": "nexus/0.14",
                    "runtime_version": self.runtime_version,
                    "control_transport": "jsonl_stdio",
                    "council_chair": {
                        "vote_weight_per_seat": 1,
                        "epistemic_privilege_per_seat": "none",
                    },
                },
            )
        if operation == "system.operations":
            return self._with_request_id(
                request,
                {
                    "status": "ok",
                    "operations": [
                        "system.health",
                        "system.operations",
                        "world.inspect",
                        "receipt.verify",
                        "council.run",
                    ],
                },
            )
        if operation == "world.inspect":
            ref = request.get("object_ref")
            obj = self.objects.get(ref)
            if obj is None:
                return self._with_request_id(
                    request,
                    {"status": "error", "error": {"code": "invalid_request", "message": "missing"}},
                )
            return self._with_request_id(request, {"status": "ok", "object": obj})
        if operation == "receipt.verify":
            ref = request.get("receipt_ref")
            obj = self.objects.get(ref)
            if obj is None or obj.get("object_type") != "receipt":
                return self._with_request_id(
                    request,
                    {"status": "error", "error": {"code": "invalid_request", "message": "not receipt"}},
                )
            payload = obj["payload"]
            missing = ["object:" + "f" * 64] if self.tamper == "receipt_missing" else []
            return self._with_request_id(
                request,
                {
                    "status": "verified" if not missing else "failed",
                    "receipt_ref": ref,
                    "result_ref": payload["result_ref"],
                    "replayable": payload["replayable"],
                    "missing_refs": missing,
                },
            )
        if operation == "council.run":
            return self._council_run(request)
        return self._with_request_id(
            request,
            {"status": "error", "error": {"code": "unknown_operation", "message": "unsupported"}},
        )

    def _council_run(self, request: dict[str, Any]) -> dict[str, Any]:
        members = request.get("members", [])
        question = request.get("question", "")
        evidence_refs = list(request.get("evidence_refs", []))
        evidence_state = request.get("evidence_state", "UNTESTED")
        mode = request.get("mode", "analytical")
        committed_question = (
            "different committed question" if self.tamper == "question_binding" else question
        )
        committed_mode = "historical" if self.tamper == "mode_binding" else mode

        question_obj = self.create_object(
            "question",
            {"text": committed_question, "secret_scrubbed": False, "scrubbed_types": []},
            {"actor": "human_operator"},
        )
        evidence_obj = self.create_object(
            "evidence_snapshot",
            {
                "question_ref": question_obj["object_id"],
                "included_object_refs": evidence_refs,
                "evidence_state": evidence_state,
            },
        )
        roster = [
            {
                "member_id": member["member_id"],
                "adapter_id": member.get("adapter_id", "mock"),
                "model_id": member["model_id"],
                "deployment_metadata": dict(member.get("deployment_metadata", {})),
                "capability_metadata": dict(member.get("capability_metadata", {})),
                "vote_weight": 1,
                "epistemic_privilege": "none",
                "actor_metadata": {"fixture": True},
                "failsafe_state_ref": None,
            }
            for member in members
        ]
        if roster and self.tamper == "roster_missing_model":
            roster[0].pop("model_id")
        if roster and self.tamper == "roster_bad_adapter":
            roster[0]["adapter_id"] = 7
        roster_ids = [row["member_id"] for row in roster]
        presence = self.create_object(
            "world_presence",
            {
                "mode_id": committed_mode,
                "mode_label": committed_mode,
                "region_id": "observatory",
                "region_label": "Observatory",
                "coordinates": [0, 0],
                "member_ids": roster_ids,
                "question_ref": question_obj["object_id"],
                "geometry_id": "fixture-geometry",
                "geometry_topology_ref": "fixture-topology",
            },
        )
        policy = {
            "consensus_numerator": 2,
            "consensus_denominator": 3,
            "minimum_members": 3,
            "first_pass_blind": True,
            "ballot_sealed": True,
            "vote_weight": 1,
            "phase_order": list(PHASE_ORDER),
        }
        frozen = {
            "question_ref": question_obj["object_id"],
            "evidence_snapshot_ref": evidence_obj["object_id"],
            "world_presence_ref": presence["object_id"],
            "world_mode": {"mode_id": committed_mode},
            "geometry_region": {"region_id": "observatory"},
            "roster": roster,
            "policy": policy,
            "failsafe_policy": {"schema_version": "fixture"},
        }
        session_id = nexus_ref("council_session", frozen)

        phases: dict[str, list[dict[str, Any]]] = {}
        for phase in PHASE_ORDER:
            records = [
                {
                    "member_id": member_id,
                    "phase": phase,
                    "content": f"{phase} visible submission from {member_id}",
                    "guard_events": [],
                }
                for member_id in roster_ids
            ]
            if self.tamper == "phase_order" and phase == "RED":
                records.reverse()
            phases[phase] = records

        revealed: list[dict[str, Any]] = []
        commitments: list[dict[str, Any]] = []
        for index, member_id in enumerate(roster_ids):
            if self.tamper in {"below_threshold", "false_consensus"} and len(roster_ids) == 4:
                choice = ["ACCEPT", "ACCEPT", "TEST_FURTHER", "REJECT"][index]
            else:
                choice = "ACCEPT" if index < 2 else "TEST_FURTHER"
            rationale = "supported by admitted evidence" if choice == "ACCEPT" else "needs more evidence"
            commitment = nexus_ref(
                "ballot",
                {
                    "session_id": session_id,
                    "member_id": member_id,
                    "choice": choice,
                    "rationale": rationale,
                },
            )
            commitments.append({"member_id": member_id, "commitment": commitment})
            revealed.append(
                {
                    "member_id": member_id,
                    "choice": choice,
                    "rationale": rationale,
                    "commitment": commitment,
                }
            )
        if self.tamper == "commitment" and revealed:
            revealed[0]["rationale"] = "altered after commitment"

        tally = dict(sorted(Counter(item["choice"] for item in revealed).items()))
        top_count = max(tally.values())
        winners = sorted(choice for choice, count in tally.items() if count == top_count)
        single_winner = len(winners) == 1
        disposition = winners[0] if single_winner else "NO_SINGLE_DISPOSITION"
        total = len(revealed)
        threshold_met = single_winner and top_count * 3 >= total * 2
        if single_winner and top_count == total:
            consensus_label = "UNANIMOUS"
        elif threshold_met and top_count * 5 >= total * 4:
            consensus_label = "STRONG_CONSENSUS"
        elif threshold_met:
            consensus_label = "CONSENSUS"
        elif single_winner and top_count * 2 > total:
            consensus_label = "MAJORITY_NO_CONSENSUS"
        else:
            consensus_label = "NO_CONSENSUS"
        if self.tamper == "false_consensus":
            consensus_label = "CONSENSUS"

        minority = [
            {
                "member_id": item["member_id"],
                "choice": item["choice"],
                "rationale": item["rationale"],
            }
            for item in revealed
            if disposition == "NO_SINGLE_DISPOSITION" or item["choice"] != disposition
        ]
        threshold = {"numerator": 2, "denominator": 3}
        if self.tamper == "threshold":
            threshold = {"numerator": 1, "denominator": 2}
        result = {
            "disposition": disposition,
            "tally": tally,
            "consensus_label": consensus_label,
            "consensus_threshold": threshold,
            "evidence_state": evidence_state,
            "minority_reports": minority,
        }
        telemetry: dict[str, Any] = {"authority": "observational_only"}
        if self.tamper == "credential_output":
            telemetry["api_key"] = "secret-value-without-known-prefix"
        session_payload: dict[str, Any] = {
            **frozen,
            "session_id": session_id,
            "execution_replayable": True,
            "phase_submissions": phases,
            "guard_events": [],
            "ballot_commitments": commitments,
            "revealed_ballots": revealed,
            "result": result,
            "telemetry": telemetry,
            "failsafe": {"policy": {"enabled": True}, "outcomes": []},
        }
        if self.tamper == "hidden_reasoning":
            session_payload["hidden_reasoning"] = "this must never enter CONTROL"
        session = self.create_object("council_session", session_payload)
        receipt = self.create_object(
            "receipt",
            {
                "operation": "council.run",
                "input_refs": [question_obj["object_id"], evidence_obj["object_id"], presence["object_id"]],
                "result_ref": session["object_id"],
                "replayable": True,
                "protocol": "nexus/0.14",
            },
        )
        citizenship_votes = 1 if self.tamper == "extra_votes" else 0
        return self._with_request_id(
            request,
            {
                "status": "ok",
                "session_id": session_id,
                "question_ref": question_obj["object_id"],
                "evidence_snapshot_ref": evidence_obj["object_id"],
                "world_presence_ref": presence["object_id"],
                "mode_id": committed_mode,
                "geometry_region_id": "observatory",
                "session_ref": session["object_id"],
                "receipt_ref": receipt["object_id"],
                "execution_replayable": True,
                "evidence_context_chars": 0,
                "secret_scrub": {"changed": False, "events": []},
                "result": result,
                "telemetry": session_payload["telemetry"],
                "failsafe": session_payload["failsafe"],
                "council_chair": {
                    "vote_weight_per_seat": 1,
                    "epistemic_privilege_per_seat": "none",
                    "seats": [{"member_id": item} for item in roster_ids],
                },
                "citizenship": {
                    "civic_mode": False,
                    "proxy_replacements": [],
                    "additional_votes_created": citizenship_votes,
                },
            },
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log")
    parser.add_argument("--tamper")
    parser.add_argument("--runtime-version", default="2.0.0")
    args = parser.parse_args()
    nexus = FakeNexus(tamper=args.tamper, runtime_version=args.runtime_version)
    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        request = json.loads(line)
        response = nexus.handle(request)
        if args.log:
            with Path(args.log).open("a", encoding="utf-8") as handle:
                handle.write(str(request.get("operation")) + "\n")
        print(json.dumps(response, sort_keys=True, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
