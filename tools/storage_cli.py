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

from storage.control_store import ControlStore
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


def command_put_file(args: argparse.Namespace) -> int:
    path = Path(args.path)
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
    emit(
        store_from(args).update_collection(
            args.collection,
            add=args.add,
            remove=args.remove,
            created_at=args.created_at,
        )
    )
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
    vectors = json.loads(Path(args.vectors).read_text(encoding="utf-8"))
    embedding = json.loads(Path(args.embedding).read_text(encoding="utf-8"))
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
    payload = store.read_file(args.file_id)
    traversal = (
        LEXICOGRAPHIC_TRAVERSAL
        if args.traversal == "lexicographic"
        else PHI_GATED_TRAVERSAL
    )
    projection = encode_projection(payload, traversal_id=traversal)
    if args.output:
        Path(args.output).write_text(
            json.dumps(projection, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    else:
        emit(projection)
    return 0


def command_dna_decode(args: argparse.Namespace) -> int:
    projection = json.loads(Path(args.projection).read_text(encoding="utf-8"))
    payload = decode_projection(projection)
    output = Path(args.output)
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
    emit(store_from(args).fingerprint())
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

    dna_export = sub.add_parser("dna-export", help="export one File as a reversible DNA/lattice projection")
    dna_export.add_argument("file_id")
    dna_export.add_argument(
        "--traversal",
        choices=["lexicographic", "phi-gated"],
        default="phi-gated",
    )
    dna_export.add_argument("--output", help="write projection JSON instead of stdout")
    dna_export.set_defaults(func=command_dna_export)

    dna_decode = sub.add_parser("dna-decode", help="verify and decode a DNA/lattice projection")
    dna_decode.add_argument("projection")
    dna_decode.add_argument("--output", required=True)
    dna_decode.set_defaults(func=command_dna_decode)

    verify = sub.add_parser("verify", help="verify canonical storage and collection lineage")
    verify.set_defaults(func=command_verify)

    fingerprint = sub.add_parser("fingerprint", help="fingerprint canonical persistent state")
    fingerprint.set_defaults(func=command_fingerprint)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
