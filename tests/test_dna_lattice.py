import unittest

from storage.dna_lattice import (
    DnaLatticeError,
    LEXICOGRAPHIC_TRAVERSAL,
    PHI_GATED_TRAVERSAL,
    codon_from_index,
    codon_index,
    decode_bases,
    decode_projection,
    encode_bases,
    encode_projection,
    lexicographic_cells,
    phi_gated_cells,
)


class DnaLatticeCodecTests(unittest.TestCase):
    def test_byte_codec_round_trip(self):
        payload = bytes(range(256))
        bases = encode_bases(payload)
        self.assertEqual(len(bases), len(payload) * 4)
        self.assertEqual(decode_bases(bases), payload)

    def test_known_bit_mapping(self):
        # 0b00011011 -> 00 01 10 11 -> A C G T
        self.assertEqual(encode_bases(bytes([0x1B])), "ACGT")
        self.assertEqual(decode_bases("ACGT"), bytes([0x1B]))

    def test_all_64_codons_are_bijective(self):
        codons = {codon_from_index(index) for index in range(64)}
        self.assertEqual(len(codons), 64)
        for index in range(64):
            self.assertEqual(codon_index(codon_from_index(index)), index)

    def test_lexicographic_lattice_has_exactly_27_cells(self):
        cells = lexicographic_cells()
        self.assertEqual(len(cells), 27)
        self.assertEqual(len(set(cells)), 27)
        self.assertEqual(cells[0], "L[0,0,0]")
        self.assertEqual(cells[-1], "L[2,2,2]")

    def test_phi_gated_path_is_single_visit_per_cell(self):
        cells = phi_gated_cells()
        self.assertEqual(len(cells), 27)
        self.assertEqual(set(cells), set(lexicographic_cells()))
        self.assertEqual(cells[0], "L[0,0,0]")
        self.assertEqual(cells[1], "L[1,2,2]")  # lexicographic cell index 17

    def test_projection_round_trip_phi_gated(self):
        payload = b"QSOL-CONTROL persistent memory\x00\xff"
        projection = encode_projection(payload, traversal_id=PHI_GATED_TRAVERSAL)
        self.assertEqual(decode_projection(projection), payload)
        self.assertEqual(projection["authority"], "none")
        self.assertTrue(projection["derived"])
        self.assertEqual(projection["base_length"], len(payload) * 4)

    def test_projection_round_trip_lexicographic(self):
        payload = b"lexicographic deterministic storage"
        projection = encode_projection(payload, traversal_id=LEXICOGRAPHIC_TRAVERSAL)
        self.assertEqual(decode_projection(projection), payload)

    def test_empty_payload_round_trip(self):
        projection = encode_projection(b"")
        self.assertEqual(projection["codon_count"], 0)
        self.assertEqual(decode_projection(projection), b"")

    def test_tampered_projection_identity_fails(self):
        projection = encode_projection(b"untampered")
        projection["cells"]["L[0,0,0]"] += "AAA"
        with self.assertRaisesRegex(DnaLatticeError, "identity"):
            decode_projection(projection)

    def test_unknown_traversal_fails_closed(self):
        with self.assertRaisesRegex(DnaLatticeError, "unknown traversal"):
            encode_projection(b"data", traversal_id="qsol.magic-spiral/9000")

    def test_dna_symbols_do_not_create_authority(self):
        projection = encode_projection(b"six models agree")
        projection["authority"] = "truth"
        with self.assertRaisesRegex(DnaLatticeError, "authority"):
            decode_projection(projection)


if __name__ == "__main__":
    unittest.main()
