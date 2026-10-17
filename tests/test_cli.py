"""Tests for the Dual6 CLI."""

from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout

from dual6.cli import main


def run_cli(argv):
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class TestCli(unittest.TestCase):
    def test_encode_decode(self) -> None:
        code, out, _ = run_cli(["encode", "--bits", "101", "--trits", "P0T"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["symbols"], "513")

        code, out, _ = run_cli(["decode", "--symbols", "513"])
        self.assertEqual(code, 0)
        result = json.loads(out)
        self.assertEqual(result["bits"], "101")
        self.assertEqual(result["trits"], "P0T")

    def test_trit_variants(self) -> None:
        code, out, _ = run_cli(["encode", "--bits", "10", "--trits", "+1-1"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["symbols"], "50")

    def test_pack_unpack_block64(self) -> None:
        symbols = "123450" * 4
        code, out, _ = run_cli(["pack-block64", "--symbols", symbols])
        self.assertEqual(code, 0)
        packed = json.loads(out)
        self.assertEqual(packed["bytes"], 8)

        code, out, _ = run_cli(["unpack-block64", "--hex", packed["hex"]])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["symbols"], symbols)

    def test_pack_unpack_frame(self) -> None:
        code, out, _ = run_cli(["pack-frame", "--bits", "101", "--trits", "P0T"])
        self.assertEqual(code, 0)
        frame = json.loads(out)

        code, out, _ = run_cli(["unpack-frame", "--hex", frame["hex"]])
        self.assertEqual(code, 0)
        result = json.loads(out)
        self.assertEqual(result["bits"], "101")
        self.assertEqual(result["trits"], "P0T")

    def test_inspect_frame_good(self) -> None:
        code, out, _ = run_cli(["pack-frame", "--bits", "101", "--trits", "P0T"])
        frame = json.loads(out)
        code, out, _ = run_cli(["inspect-frame", "--hex", frame["hex"]])
        self.assertEqual(code, 0)
        info = json.loads(out)
        self.assertTrue(info["crc_ok"])
        self.assertEqual(info["width"], 3)
        self.assertEqual(info["decoded"]["bits"], "101")

    def test_inspect_frame_bad_crc(self) -> None:
        code, out, _ = run_cli(["pack-frame", "--bits", "101", "--trits", "P0T"])
        frame = bytearray.fromhex(json.loads(out)["hex"])
        frame[-1] ^= 0x01
        code, out, _ = run_cli(["inspect-frame", "--hex", frame.hex()])
        self.assertEqual(code, 0)
        info = json.loads(out)
        self.assertFalse(info["crc_ok"])
        self.assertIsNone(info["decoded"])

    def test_invalid_input(self) -> None:
        code, _, err = run_cli(["decode", "--symbols", "9"])
        self.assertEqual(code, 2)
        self.assertIn("VALUE_ERROR", err)

    def test_width_mismatch(self) -> None:
        code, _, err = run_cli(["encode", "--bits", "10", "--trits", "P"])
        self.assertEqual(code, 2)
        self.assertIn("VALUE_ERROR", err)

    def test_pack_unpack_block64_dp(self) -> None:
        bits = "10" * 12
        trits = "P0" * 12
        code, out, _ = run_cli(["pack-block64-dp", "--bits", bits, "--trits", trits])
        self.assertEqual(code, 0)
        packed = json.loads(out)
        self.assertEqual(packed["bytes"], 8)

        code, out, _ = run_cli(["unpack-block64-dp", "--hex", packed["hex"]])
        self.assertEqual(code, 0)
        result = json.loads(out)
        self.assertEqual(result["bits"], bits)
        self.assertEqual(result["trits"], trits)

    def test_pack_unpack_frame_v2_auto_detect(self) -> None:
        code, out, _ = run_cli(
            [
                "pack-frame",
                "--bits",
                "10" * 12,
                "--trits",
                "P0" * 12,
                "--version",
                "2",
                "--dtype",
                "2",
                "--block-symbols",
                "24",
            ]
        )
        self.assertEqual(code, 0)
        frame = json.loads(out)
        self.assertEqual(frame["version"], 2)

        code, out, _ = run_cli(["unpack-frame", "--hex", frame["hex"]])
        self.assertEqual(code, 0)
        result = json.loads(out)
        self.assertEqual(result["version"], 2)
        self.assertEqual(result["bits"], "10" * 12)
        self.assertEqual(result["meta"]["block_symbols"], 24)

        code, out, _ = run_cli(["inspect-frame", "--hex", frame["hex"]])
        self.assertEqual(code, 0)
        info = json.loads(out)
        self.assertTrue(info["crc_ok"])
        self.assertEqual(info["block_count"], 1)


    def test_block128_and_40_roundtrip(self) -> None:
        symbols128 = "123450" * 8
        code, out, _ = run_cli(["pack-block128", "--symbols", symbols128])
        self.assertEqual(code, 0)
        packed = json.loads(out)
        code, out, _ = run_cli(["unpack-block128", "--hex", packed["hex"]])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["symbols"], symbols128)

        symbols40 = "123450" * 6 + "1234"
        code, out, _ = run_cli(["pack-block40", "--symbols", symbols40])
        self.assertEqual(code, 0)
        packed = json.loads(out)
        code, out, _ = run_cli(["unpack-block40", "--hex", packed["hex"]])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["symbols"], symbols40)

    def test_dp_block128_and_40_roundtrip(self) -> None:
        bits128 = "10" * 24
        trits128 = "P0" * 24
        code, out, _ = run_cli(["pack-block128-dp", "--bits", bits128, "--trits", trits128])
        self.assertEqual(code, 0)
        packed = json.loads(out)
        code, out, _ = run_cli(["unpack-block128-dp", "--hex", packed["hex"]])
        self.assertEqual(code, 0)
        result = json.loads(out)
        self.assertEqual(result["bits"], bits128)
        self.assertEqual(result["trits"], trits128)

        bits40 = "10" * 20
        trits40 = "P0" * 20
        code, out, _ = run_cli(["pack-block40-dp", "--bits", bits40, "--trits", trits40])
        self.assertEqual(code, 0)
        packed = json.loads(out)
        code, out, _ = run_cli(["unpack-block40-dp", "--hex", packed["hex"]])
        self.assertEqual(code, 0)
        result = json.loads(out)
        self.assertEqual(result["bits"], bits40)
        self.assertEqual(result["trits"], trits40)


    def test_info(self) -> None:
        code, out, _ = run_cli(["info"])
        self.assertEqual(code, 0)
        info = json.loads(out)
        self.assertEqual(info["name"], "dual6")
        self.assertIn(info["backend"], ("native", "ref"))
        self.assertIn("version", info)

    def test_version_flag(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out), self.assertRaises(SystemExit) as ctx:
            main(["--version"])
        self.assertEqual(ctx.exception.code, 0)
        self.assertIn("dual6", out.getvalue())


    def test_number_command(self) -> None:
        code, out, _ = run_cli(["number", "--value", "42"])
        self.assertEqual(code, 0)
        result = json.loads(out)
        self.assertEqual(result["symbols"], "130324")
        self.assertEqual(result["length"], 6)
        self.assertEqual(result["binary"], "101010")
        self.assertEqual(result["balanced_ternary"], "PTTT0")
        self.assertEqual(result["balanced_ternary_padded"], "0PTTT0")
        self.assertEqual(result["container_value"], 34363)
        self.assertEqual(result["slot3_value"], 140825)
        self.assertEqual(result["binary_view"], 42)
        self.assertEqual(result["ternary_view"], 42)

    def test_number_rejects_negative(self) -> None:
        code, _, err = run_cli(["number", "--value", "-1"])
        self.assertEqual(code, 2)
        self.assertIn("VALUE_ERROR", err)

    def test_demo_command(self) -> None:
        code, out, _ = run_cli(["demo", "--value", "42", "--check", "1000"])
        self.assertEqual(code, 0)
        self.assertIn("二进制视图读回 = 42", out)
        self.assertIn("三进制视图读回 = 42", out)
        self.assertIn("全量对拍通过", out)

    def test_expected_commands_present(self) -> None:
        from dual6.cli import build_parser

        help_text = build_parser().format_help()
        for command in (
            "encode",
            "decode",
            "pack-block64",
            "unpack-block64",
            "pack-block64-dp",
            "unpack-block64-dp",
            "pack-block128",
            "unpack-block128",
            "pack-block40",
            "unpack-block40",
            "pack-frame",
            "unpack-frame",
            "inspect-frame",
            "info",
            "number",
            "demo",
        ):
            self.assertIn(command, help_text)



if __name__ == "__main__":
    unittest.main(verbosity=2)
