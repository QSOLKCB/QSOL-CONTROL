#!/usr/bin/env python3
"""Reversible DNA-symbol projection over the QSOL 3x3x3 lattice.

The DNA alphabet is a digital codec and recovery representation, not a biological
claim. Raw File bytes remain canonical persistent content.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from typing import Any

DNA_ALPHABET = ("A", "C", "G", "T")
BASE_TO_VALUE = {base: value for value, base in enumerate(DNA_ALPHABET)}
VALUE_TO_BASE = dict(enumerate(DNA_ALPHABET))
DNA_RE = re.compile(r"^[ACGT]*$")
LATTICE_PROFILE = "qsol-3x3x3-sierpinski-derived-memory/1"
LEXICOGRAPHIC_TRAVERSAL = "qsol.lexicographic-27/1"
PHI_GATED_TRAVERSAL = "qsol.phi-stride-27/1"
PHI_STRIDE = 17  # fixed protocol constant; gcd(17, 27) == 1
TRAVERSAL_MODULUS = 27


class DnaLatticeError(ValueError):
    """Raised when a DNA/lattice projection is malformed or not reversible."""


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def lexicographic_cells() -> tuple[str, ...]:
    """Return all 27 lattice cells in canonical coordinate order."""
    return tuple(
        f"L[{x},{y},{z}]"
        for x in range(3)
        for y in range(3)
        for z in range(3)
    )


def phi_gated_cells() -> tuple[str, ...]:
    """Return one deterministic phi-derived single path through all 27 cells.

    This is a discrete addressing traversal. It is not evidence that the lattice is
    physically spiral-shaped or that phi has privileged storage semantics.
    """
    cells = lexicographic_cells()
    order = tuple(
        cells[(step * PHI_STRIDE) % TRAVERSAL_MODULUS]
        for step in range(TRAVERSAL_MODULUS)
    )
    if len(set(order)) != TRAVERSAL_MODULUS:
        raise DnaLatticeError("phi traversal must visit every lattice cell exactly once")
    return order


def traversal_cells(traversal_id: str) -> tuple[str, ...]:
    if traversal_id == LEXICOGRAPHIC_TRAVERSAL:
        return lexicographic_cells()
    if traversal_id == PHI_GATED_TRAVERSAL:
        return phi_gated_cells()
    raise DnaLatticeError(f"unknown traversal: {traversal_id}")


def traversal_parameters(traversal_id: str) -> dict[str, Any]:
    if traversal_id == LEXICOGRAPHIC_TRAVERSAL:
        return {
            "mode": "lexicographic",
            "modulus": TRAVERSAL_MODULUS,
            "rule": "cell_index(n)=n",
        }
    if traversal_id == PHI_GATED_TRAVERSAL:
        return {
            "mode": "fixed-modular-stride",
            "stride": PHI_STRIDE,
            "modulus": TRAVERSAL_MODULUS,
            "rule": "cell_index(n)=(17*n) mod 27",
        }
    raise DnaLatticeError(f"unknown traversal: {traversal_id}")


def encode_bases(data: bytes) -> str:
    """Encode bytes as four 2-bit DNA symbols per byte, high bits first."""
    output: list[str] = []
    for byte in data:
        output.extend(
            VALUE_TO_BASE[(byte >> shift) & 0b11]
            for shift in (6, 4, 2, 0)
        )
    return "".join(output)


def decode_bases(bases: str) -> bytes:
    """Decode a base string created by encode_bases()."""
    if not isinstance(bases, str) or not DNA_RE.fullmatch(bases):
        raise DnaLatticeError("DNA sequence may contain only A, C, G, T")
    if len(bases) % 4 != 0:
        raise DnaLatticeError("DNA base length must be divisible by 4 for byte decoding")
    output = bytearray()
    for start in range(0, len(bases), 4):
        value = 0
        for base in bases[start:start + 4]:
            value = (value << 2) | BASE_TO_VALUE[base]
        output.append(value)
    return bytes(output)


def codon_index(codon: str) -> int:
    """Map exactly three DNA bases to one 6-bit codon slot 0..63."""
    if not isinstance(codon, str) or len(codon) != 3 or not DNA_RE.fullmatch(codon):
        raise DnaLatticeError("codon must contain exactly three A/C/G/T bases")
    first, second, third = (BASE_TO_VALUE[base] for base in codon)
    return first * 16 + second * 4 + third


def codon_from_index(value: int) -> str:
    if not isinstance(value, int) or not 0 <= value < 64:
        raise DnaLatticeError("codon index must be an integer 0..63")
    return "".join(
        VALUE_TO_BASE[part]
        for part in ((value >> 4) & 0b11, (value >> 2) & 0b11, value & 0b11)
    )


def encode_projection(
    data: bytes,
    *,
    traversal_id: str = PHI_GATED_TRAVERSAL,
) -> dict[str, Any]:
    """Encode raw bytes into codons distributed over the 27-cell lattice.

    Codons are assigned round-robin along the versioned traversal. Cell-local strings
    retain cycle order. Reconstruction therefore needs no per-codon sequence metadata.
    """
    raw = bytes(data)
    bases = encode_bases(raw)
    padding_bases = (-len(bases)) % 3
    padded = bases + ("A" * padding_bases)
    codons = [padded[index:index + 3] for index in range(0, len(padded), 3)]
    order = traversal_cells(traversal_id)
    parameters = traversal_parameters(traversal_id)
    cells: dict[str, list[str]] = {cell: [] for cell in lexicographic_cells()}
    for sequence, codon in enumerate(codons):
        cells[order[sequence % TRAVERSAL_MODULUS]].append(codon)
    compact_cells = {cell: "".join(cells[cell]) for cell in lexicographic_cells()}
    histogram = Counter(codon_index(codon) for codon in codons)
    projection_payload = {
        "protocol": "qsol-control-dna-lattice/1",
        "codec": "qsol.dna-2bit-codon64/1",
        "alphabet": list(DNA_ALPHABET),
        "bit_mapping": {"A": "00", "C": "01", "G": "10", "T": "11"},
        "lattice_profile": LATTICE_PROFILE,
        "traversal_id": traversal_id,
        "traversal_parameters": parameters,
        "traversal_rule": "round_robin_codon_assignment_across_versioned_27_cell_path",
        "byte_length": len(raw),
        "base_length": len(bases),
        "padding_bases": padding_bases,
        "codon_count": len(codons),
        "content_sha256": sha256_hex(raw),
        "cells": compact_cells,
        "codon_histogram": {str(index): histogram[index] for index in sorted(histogram)},
        "derived": True,
        "rebuildable": True,
        "authority": "none",
        "storage_claim": "reversible_recovery_projection_not_compression_claim",
    }
    projection_id = f"sha256:{sha256_hex(canonical_json_bytes(projection_payload))}"
    return {"projection_id": projection_id, **projection_payload}


def decode_projection(projection: dict[str, Any]) -> bytes:
    """Verify and decode a qsol-control-dna-lattice/1 projection."""
    if not isinstance(projection, dict):
        raise DnaLatticeError("projection must be an object")
    if projection.get("protocol") != "qsol-control-dna-lattice/1":
        raise DnaLatticeError("projection protocol mismatch")
    if projection.get("codec") != "qsol.dna-2bit-codon64/1":
        raise DnaLatticeError("projection codec mismatch")
    if projection.get("lattice_profile") != LATTICE_PROFILE:
        raise DnaLatticeError("unsupported lattice profile")
    if projection.get("alphabet") != list(DNA_ALPHABET):
        raise DnaLatticeError("DNA alphabet mapping mismatch")
    if projection.get("derived") is not True or projection.get("rebuildable") is not True:
        raise DnaLatticeError("DNA projection must remain derived and rebuildable")
    if projection.get("authority") != "none":
        raise DnaLatticeError("DNA projection must not claim authority")

    identity_payload = {key: value for key, value in projection.items() if key != "projection_id"}
    expected_projection_id = f"sha256:{sha256_hex(canonical_json_bytes(identity_payload))}"
    if projection.get("projection_id") != expected_projection_id:
        raise DnaLatticeError("DNA projection identity mismatch")

    traversal_id = projection.get("traversal_id")
    expected_parameters = traversal_parameters(traversal_id)
    if projection.get("traversal_parameters") != expected_parameters:
        raise DnaLatticeError("DNA traversal parameters do not match the versioned traversal")
    order = traversal_cells(traversal_id)
    cells = projection.get("cells")
    if not isinstance(cells, dict) or set(cells) != set(lexicographic_cells()):
        raise DnaLatticeError("DNA projection must define exactly the 27 lattice cells")
    for cell, sequence in cells.items():
        if not isinstance(sequence, str) or not DNA_RE.fullmatch(sequence):
            raise DnaLatticeError(f"cell {cell} contains invalid DNA symbols")
        if len(sequence) % 3 != 0:
            raise DnaLatticeError(f"cell {cell} must contain whole codons")

    codon_count = projection.get("codon_count")
    if not isinstance(codon_count, int) or codon_count < 0:
        raise DnaLatticeError("codon_count is invalid")
    expected_per_cell = Counter(
        order[index % TRAVERSAL_MODULUS] for index in range(codon_count)
    )
    for cell in lexicographic_cells():
        if len(cells[cell]) != expected_per_cell[cell] * 3:
            raise DnaLatticeError("cell codon count does not match traversal assignment")

    cell_offsets = {cell: 0 for cell in lexicographic_cells()}
    codons: list[str] = []
    for sequence in range(codon_count):
        cell = order[sequence % TRAVERSAL_MODULUS]
        start = cell_offsets[cell]
        codon = cells[cell][start:start + 3]
        if len(codon) != 3:
            raise DnaLatticeError("DNA projection ended before declared codon_count")
        codons.append(codon)
        cell_offsets[cell] += 3

    padded = "".join(codons)
    base_length = projection.get("base_length")
    byte_length = projection.get("byte_length")
    padding_bases = projection.get("padding_bases")
    if not isinstance(base_length, int) or base_length < 0:
        raise DnaLatticeError("base_length is invalid")
    if not isinstance(byte_length, int) or byte_length < 0:
        raise DnaLatticeError("byte_length is invalid")
    if not isinstance(padding_bases, int) or padding_bases not in {0, 1, 2}:
        raise DnaLatticeError("padding_bases is invalid")
    if len(padded) != base_length + padding_bases:
        raise DnaLatticeError("padded base length mismatch")
    if base_length != byte_length * 4:
        raise DnaLatticeError("DNA base length must equal four bases per byte")

    raw = decode_bases(padded[:base_length])
    if len(raw) != byte_length:
        raise DnaLatticeError("decoded byte length mismatch")
    if sha256_hex(raw) != projection.get("content_sha256"):
        raise DnaLatticeError("decoded content hash mismatch")

    histogram = Counter(codon_index(codon) for codon in codons)
    expected_histogram = {str(index): histogram[index] for index in sorted(histogram)}
    if projection.get("codon_histogram") != expected_histogram:
        raise DnaLatticeError("codon histogram mismatch")
    return raw
