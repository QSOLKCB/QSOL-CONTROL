#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys


def sha256_ref(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def emit(result):
    print(json.dumps({"protocol": "qsol-external-consensus-response/1", "ok": True, "result": result}, sort_keys=True, separators=(",", ":")))


def main() -> int:
    request = json.loads(sys.stdin.readline())
    operation = request["operation"]
    payload = request["payload"]
    if operation == "system.health":
        emit({"status": "ok", "provider_protocol": "fixture-consensus/1"})
    elif operation == "commit.propose":
        emit({
            "protocol": "qsol-control-consensus-receipt/1",
            "intent_id": payload["intent_id"],
            "cluster_id": "fixture-cluster",
            "epoch": 7,
            "commit_index": 42,
            "member_set_id": sha256_ref(b"fixture-members"),
            "quorum": {"required": 2, "observed": 3},
            "state_fingerprint": payload["expected_store_fingerprint"],
            "provider_protocol": "fixture-consensus/1",
            "verified": True,
            "authority": "coordination-only",
            "semantic_authority_claimed": False
        })
    elif operation == "receipt.verify":
        emit({"verified": True, "intent_id": payload["intent_id"]})
    else:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
