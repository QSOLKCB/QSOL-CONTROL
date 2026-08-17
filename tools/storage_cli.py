#!/usr/bin/env python3
"""Small operator CLI for the QSOL-CONTROL persistent store."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from storage.control_store import ControlStore, StorageError
from storage.dna_lattice import (
    LEXICOGRAPHIC_TRAVERSAL,
    PHI_GATED_TRAVERSAL,
    decode_projection,
    encode_projection,
)


def emit(value) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))


def store_from(args: argparse.Namespace) -> ControlStore:
    return ControlStore(args.root)


def actor_from(args: argparse.Namespace) -> str:
    actor = getattr(args, "actor", None) or "local-operator"
    if not actor.strip():
        raise StorageError("audit actor must be non-empty")
    return actor


def command_put_file(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if path.is_symlink():
        raise StorageError("put-file refuses symlink inputs; resolve and inspect the source explicitly")
    record = store_from(args).put_file(
        path.read_bytes(),
        filename=args.filename or path.name,
        media_type=args.media_type,
        created_at=args.created_at,
        privacy_class=args.privacy,
        retention_class=args.retention,
        source={"kind": "filesystem", "locator": str(path)},
    )
    emit(record)
    return 0


def command_create_collection(args: argparse.Namespace) -> int:
    emit(
        store_from(args).create_collection(
            name=args.name,
            created_at=args.created_at,
            privacy_class=args.privacy,
            retention_class=args.retention,
        )
    )
    return 0


def command_update_collection(args: argparse.Namespace) -> int:
    store = store_from(args)
    if args.dry_run:
        emit(
            store.preview_collection_update(
                args.collection,
                add=args.add,
                remove=args.remove,
            )
        )
        return 0

    before = store.get_collection_snapshot(args.collection)
    snapshot = store.update_collection(
        args.collection,
        add=args.add,
        remove=args.remove,
        created_at=args.created_at,
        expected_head_snapshot_id=args.expect_head,
    )
    if snapshot["snapshot_id"] != before["snapshot_id"]:
        store.record_audit_event(
            "collection-update",
            actor=actor_from(args),
            details={
                "collection_id": args.collection,
                "previous_snapshot_id": before["snapshot_id"],
                "new_snapshot_id": snapshot["snapshot_id"],
                "revision": snapshot["revision"],
                "added_file_ids": sorted(args.add),
                "removed_file_ids": sorted(args.remove),
            },
        )
    emit(snapshot)
    return 0


def command_list_files(args: argparse.Namespace) -> int:
    emit(store_from(args).list_collection_files(args.collection))
    return 0


def command_build_lexical(args: argparse.Namespace) -> int:
    emit(store_from(args).build_lexical_index(args.collection, built_at=args.built_at))
    return 0


def command_search(args: argparse.Namespace) -> int:
    emit(store_from(args).search_lexical(args.collection, args.query, limit=args.limit))
    return 0


def command_register_semantic(args: argparse.Namespace) -> int:
    vectors_path = Path(args.vectors)
    embedding_path = Path(args.embedding)
    if vectors_path.is_symlink() or embedding_path.is_symlink():
        raise StorageError("semantic index registration refuses symlink descriptor inputs")
    vectors = json.loads(vectors_path.read_text(encoding="utf-8"))
    embedding = json.loads(embedding_path.read_text(encoding="utf-8"))
    emit(
        store_from(args).register_semantic_index(
            args.collection,
            vectors=vectors,
            embedding=embedding,
            built_at=args.built_at,
        )
    )
    return 0


def command_search_semantic(args: argparse.Namespace) -> int:
    vector = json.loads(args.vector)
    emit(store_from(args).search_semantic(args.collection, vector, limit=args.limit))
    return 0


def command_dna_export(args: argparse.Namespace) -> int:
    store = store_from(args)
    record = store.get_file_record(args.file_id)
    restricted = record["privacy_class"] == "RESTRICTED"

    if restricted and not args.allow_restricted:
        raise StorageError(
            "RESTRICTED File DNA export requires explicit --allow-restricted; encoding is reversible"
        )
    if restricted and not args.acknowledge_reversible_sensitive_export:
        raise StorageError(
            "RESTRICTED File DNA export also requires --acknowledge-reversible-sensitive-export"
        )
    if restricted and not args.actor:
        raise StorageError("RESTRICTED File DNA export requires explicit --actor for audit attribution")

    payload = store.read_file(args.file_id)
    traversal = (
        LEXICOGRAPHIC_TRAVERSAL
        if args.traversal == "lexicographic"
        else PHI_GATED_TRAVERSAL
    )
    projection = encode_projection(payload, traversal_id=traversal)

    if args.dry_run:
        emit(
            {
                "protocol": "qsol-control-dna-export-preview/1",
                "dry_run": True,
                "file_id": args.file_id,
                "privacy_class": record["privacy_class"],
                "traversal_id": traversal,
                "projection_id": projection["projection_id"],
                "content_sha256": projection["content_sha256"],
                "byte_length": projection["byte_length"],
                "restricted_authorized": restricted and args.allow_restricted,
                "would_write": args.output,
            }
        )
        return 0

    if args.output:
        output = Path(args.output)
        if output.is_symlink():
            raise StorageError("dna-export refuses to overwrite a symlink output")
        output.write_text(
            json.dumps(projection, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    else:
        emit(projection)

    store.record_audit_event(
        "dna-export",
        actor=actor_from(args),
        details={
            "file_id": args.file_id,
            "privacy_class": record["privacy_class"],
            "restricted_authorized": restricted and args.allow_restricted,
            "reversible_sensitive_export_acknowledged": bool(
                args.acknowledge_reversible_sensitive_export
            ),
            "traversal_id": traversal,
            "projection_id": projection["projection_id"],
            "content_sha256": projection["content_sha256"],
            "output": str(args.output) if args.output else "stdout",
        },
    )
    return 0


def command_dna_decode(args: argparse.Namespace) -> int:
    projection_path = Path(args.projection)
    if projection_path.is_symlink():
        raise StorageError("dna-decode refuses symlink projection inputs")
    projection = json.loads(projection_path.read_text(encoding="utf-8"))
    payload = decode_projection(projection)
    output = Path(args.output)
    if output.is_symlink():
        raise StorageError("dna-decode refuses to overwrite a symlink output")
    output.write_bytes(payload)
    emit(
        {
            "status": "verified",
            "projection_id": projection["projection_id"],
            "output": str(output),
            "bytes": len(payload),
            "content_sha256": projection["content_sha256"],
        }
    )
    return 0


def command_verify(args: argparse.Namespace) -> int:
    emit(store_from(args).verify())
    return 0


def command_fingerprint(args: argparse.Namespace) -> int:
    store = store_from(args)
    result = store.fingerprint()
    store.record_audit_event(
        "fingerprint",
        actor=actor_from(args),
        details={"fingerprint": result["fingerprint"]},
    )
    emit(result)
    return 0


def command_audit(args: argparse.Namespace) -> int:
    emit(store_from(args).list_audit_events())
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="QSOL-CONTROL persistent storage")
    parser.add_argument("--root", default=".qsol-control-store", help="storage directory")
    sub = parser.add_subparsers(dest="command", required=True)

    put_file = sub.add_parser("put-file", help="persist one File")
    put_file.add_argument("path")
    put_file.add_argument("--filename")
    put_file.add_argument("--media-type", default="text/plain")
    put_file.add_argument("--created-at")
    put_file.add_argument("--privacy", default="INTERNAL")
    put_file.add_argument("--retention", default="ARCHIVE")
    put_file.set_defaults(func=command_put_file)

    create = sub.add_parser("create-collection", help="create a persistent Collection")
    create.add_argument("name")
    create.add_argument("--created-at")
    create.add_argument("--privacy", default="INTERNAL")
    create.add_argument("--retention", default="ARCHIVE")
    create.set_defaults(func=command_create_collection)

    update = sub.add_parser("update-collection", help="create a new membership snapshot")
    update.add_argument("collection")
    update.add_argument("--add", action="append", default=[])
    update.add_argument("--remove", action="append", default=[])
    update.add_argument("--created-at")
    update.add_argument(
        "--expect-head",
        help="compare-and-swap guard: refuse if current HEAD is not this snapshot id",
    )
    update.add_argument("--dry-run", action="store_true", help="validate and preview without writing")
    update.add_argument("--actor", help="audit actor for a committed update")
    update.set_defaults(func=command_update_collection)

    list_files = sub.add_parser("list-files", help="list current Collection members")
    list_files.add_argument("collection")
    list_files.set_defaults(func=command_list_files)

    lexical = sub.add_parser("build-lexical", help="build deterministic lexical baseline")
    lexical.add_argument("collection")
    lexical.add_argument("--built-at")
    lexical.set_defaults(func=command_build_lexical)

    search = sub.add_parser("search", help="search the deterministic lexical baseline")
    search.add_argument("collection")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=10)
    search.set_defaults(func=command_search)

    semantic = sub.add_parser("register-semantic", help="register externally generated vectors")
    semantic.add_argument("collection")
    semantic.add_argument("--vectors", required=True, help="JSON mapping file_id to vector")
    semantic.add_argument("--embedding", required=True, help="JSON embedding descriptor")
    semantic.add_argument("--built-at")
    semantic.set_defaults(func=command_register_semantic)

    semantic_search = sub.add_parser("search-semantic", help="search registered semantic vectors")
    semantic_search.add_argument("collection")
    semantic_search.add_argument("vector", help="JSON vector, e.g. '[0.1, 0.9]'")
    semantic_search.add_argument("--limit", type=int, default=10)
    semantic_search.set_defaults(func=command_search_semantic)

    dna_export = sub.add_parser(
        "dna-export",
        help="export one File as a reversible DNA/lattice projection",
    )
    dna_export.add_argument("file_id")
    dna_export.add_argument(
        "--traversal",
        choices=["lexicographic", "phi-gated"],
        default="phi-gated",
    )
    dna_export.add_argument("--output", help="write projection JSON instead of stdout")
    dna_export.add_argument(
        "--allow-restricted",
        action="store_true",
        help="first acknowledgement: permit reversible export of a RESTRICTED File",
    )
    dna_export.add_argument(
        "--acknowledge-reversible-sensitive-export",
        action="store_true",
        help="second acknowledgement that DNA encoding is reversible and may disclose content",
    )
    dna_export.add_argument(
        "--actor",
        help="audit actor; required for RESTRICTED export",
    )
    dna_export.add_argument(
        "--dry-run",
        action="store_true",
        help="validate and show projection identity without writing or auditing",
    )
    dna_export.set_defaults(func=command_dna_export)

    dna_decode = sub.add_parser("dna-decode", help="verify and decode a DNA/lattice projection")
    dna_decode.add_argument("projection")
    dna_decode.add_argument("--output", required=True)
    dna_decode.set_defaults(func=command_dna_decode)

    verify = sub.add_parser("verify", help="verify canonical storage and collection lineage")
    verify.set_defaults(func=command_verify)

    fingerprint = sub.add_parser("fingerprint", help="fingerprint canonical persistent state")
    fingerprint.add_argument("--actor", help="audit actor; defaults to local-operator")
    fingerprint.set_defaults(func=command_fingerprint)

    audit = sub.add_parser("audit", help="list local CONTROL audit events")
    audit.set_defaults(func=command_audit)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except (StorageError, OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
