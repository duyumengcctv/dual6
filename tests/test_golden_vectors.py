"""Golden byte vectors shared with the future Rust backend."""

from __future__ import annotations

import json
import pathlib
import unittest

from dual6 import (
    decode_digit,
    encode_digit,
    pack_block64,
    pack_block64_dp,
    pack_digits,
    pack_dual_plane,
    pack_dual_plane_v1,
    pack_dual_plane_v2,
    unpack_block64,
    unpack_block64_dp,
    unpack_dual_plane,
    unpack_dual_plane_v1,
    unpack_dual_plane_v2,
)

VECTOR_PATH = pathlib.Path(__file__).parent / "vectors" / "golden_vectors.json"


class TestGoldenVectors(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.vectors = json.loads(VECTOR_PATH.read_text(encoding="utf-8"))

    def test_digit_vectors(self) -> None:
        for case in self.vectors["digit"]:
            self.assertEqual(encode_digit(case["bit"], case["trit"]), case["digit"])
            self.assertEqual(decode_digit(case["digit"]), (case["bit"], case["trit"]))

    def test_pack5_vectors(self) -> None:
        for case in self.vectors["pack5"]:
            self.assertEqual(pack_digits(case["digits"]), case["value"])

    def test_block64_vectors(self) -> None:
        for case in self.vectors["block64"]:
            data = pack_block64(case["symbols"])
            self.assertEqual(data.hex(), case["hex"])
            self.assertEqual(unpack_block64(data), case["symbols"])

    def test_block64_dp_vectors(self) -> None:
        for case in self.vectors["block64_dp"]:
            data = pack_block64_dp(case["bits"], case["trits"])
            self.assertEqual(data.hex(), case["hex"])
            self.assertEqual(unpack_block64_dp(data), (case["bits"], case["trits"]))

    def test_d6p0_vectors(self) -> None:
        for case in self.vectors["d6p0"]:
            data = pack_dual_plane(case["bits"], case["trits"])
            self.assertEqual(data.hex(), case["hex"])
            self.assertEqual(unpack_dual_plane(data), (case["bits"], case["trits"]))

    def test_d6p1_vectors(self) -> None:
        for case in self.vectors["d6p1"]:
            data = pack_dual_plane_v1(case["bits"], case["trits"])
            self.assertEqual(data.hex(), case["hex"])
            self.assertEqual(unpack_dual_plane_v1(data), (case["bits"], case["trits"]))

    def test_d6p2_vectors(self) -> None:
        for case in self.vectors["d6p2"]:
            data = pack_dual_plane_v2(
                case["bits"],
                case["trits"],
                dtype=case["dtype"],
                block_symbols=case["block_symbols"],
            )
            self.assertEqual(data.hex(), case["hex"])
            bits, trits, meta = unpack_dual_plane_v2(data)
            self.assertEqual((bits, trits), (case["bits"], case["trits"]))
            self.assertEqual(meta["dtype"], case["dtype"])
            self.assertEqual(meta["block_symbols"], case["block_symbols"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
