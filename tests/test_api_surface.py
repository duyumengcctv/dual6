"""API surface checks for the public `dual6` package."""

from __future__ import annotations

import unittest

import dual6


class TestApiSurface(unittest.TestCase):
    def test_all_declared_names_exist(self) -> None:
        missing = [name for name in dual6.__all__ if not hasattr(dual6, name)]
        self.assertEqual(missing, [])

    def test_expected_core_api_is_present(self) -> None:
        import pathlib

        path = pathlib.Path(__file__).parent / "expected_core_api.txt"
        expected = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        missing = [name for name in expected if not hasattr(dual6, name)]
        self.assertEqual(missing, [])

    def test_core_api_is_present(self) -> None:
        for name in (
            "encode_digit",
            "decode_digit",
            "mux",
            "demux",
            "pack_digits",
            "unpack_digits",
            "pack_block64",
            "unpack_block64",
            "pack_block64_dp",
            "unpack_block64_dp",
            "pack_dual_plane",
            "unpack_dual_plane",
            "pack_dual_plane_v1",
            "unpack_dual_plane_v1",
            "pack_dual_plane_v2",
            "unpack_dual_plane_v2",
            "frame_version",
            "unpack_frame_auto",
            "pack_bits_into",
            "unpack_bits_from",
            "pack_dual_plane_into",
            "unpack_dual_plane_from",
        ):
            self.assertTrue(callable(getattr(dual6, name)), name)

    def test_adapters_are_present(self) -> None:
        from dual6.adapters import (
            bits_to_symbols,
            symbols_to_bits,
            symbols_to_trits,
            trits_to_symbols,
        )

        self.assertTrue(callable(bits_to_symbols))
        self.assertTrue(callable(symbols_to_bits))
        self.assertTrue(callable(symbols_to_trits))
        self.assertTrue(callable(trits_to_symbols))

    def test_no_model_format_connectors(self) -> None:
        """v0.3 is a storage tool; external/model format connectors are out of scope."""
        import dual6.adapters as adapters

        banned = ("gguf", "tq1", "tq2", "quant")
        leaked = [name for name in adapters.__all__ if any(token in name.lower() for token in banned)]
        self.assertEqual(leaked, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
