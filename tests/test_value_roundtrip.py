"""Store a non-trivial value in Dual6 and read it back.

Covers the "complex value" demo in ``examples/roundtrip_value.py``:
complex numbers, big integers, a mixed record, the real two-channel case,
CRC corruption detection, and the file / mmap path.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from dual6 import (
    Dual6Error,
    MappedFrame,
    pack_dual_plane_v1,
    unpack_dual_plane_v1,
    write_frame,
)

ROOT = Path(__file__).resolve().parents[1]


def _load_example():
    path = ROOT / "examples" / "roundtrip_value.py"
    spec = importlib.util.spec_from_file_location("dual6_roundtrip_example", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


codec = _load_example()


class TestValueRoundtrip(unittest.TestCase):
    def test_arbitrary_bytes_roundtrip(self) -> None:
        for payload in (b"", b"\x00", b"\xff\x00\x7f", bytes(range(256))):
            frame = codec.store_bytes(payload)
            self.assertEqual(codec.load_bytes(frame, len(payload)), payload)

    def test_complex_number_roundtrip(self) -> None:
        for value in (0j, complex(3.5, -2.25), complex(-1e-9, 1e9)):
            payload = codec.encode_complex(value)
            frame = codec.store_bytes(payload)
            got = codec.decode_complex(codec.load_bytes(frame, len(payload)))
            self.assertEqual(got, value)

    def test_big_integer_roundtrip(self) -> None:
        for value in (0, 1, -1, 6 ** 24, 2 ** 200 + 12345, -(10 ** 40 + 7)):
            payload = codec.encode_bigint(value)
            frame = codec.store_bytes(payload)
            got = codec.decode_bigint(codec.load_bytes(frame, len(payload)))
            self.assertEqual(got, value)

    def test_mixed_record_roundtrip(self) -> None:
        record = (
            complex(1.0, -0.5),
            -(10 ** 40 + 7),
            2.718281828,
            "边缘设备",
            [2, 3],
            [1.0, -2.5, 3.25, 0.0, 4.5, -6.75],
        )
        payload = codec.encode_record(*record)
        frame = codec.store_bytes(payload)
        self.assertEqual(codec.decode_record(codec.load_bytes(frame, len(payload))), record)

    def test_true_dual_channel_roundtrip(self) -> None:
        # This is what Dual6 is actually for: both channels carry real data.
        flags = [1, 0, 1, 1, 0, 0, 1, 0] * 3
        trits = [1, -1, 0] * 8
        frame = pack_dual_plane_v1(flags, trits)
        self.assertEqual(unpack_dual_plane_v1(frame), (flags, trits))

    def test_crc_detects_corruption(self) -> None:
        frame = bytearray(codec.store_bytes(codec.encode_complex(complex(1, 2))))
        frame[-1] ^= 0xFF
        with self.assertRaises(Dual6Error) as ctx:
            unpack_dual_plane_v1(bytes(frame))
        self.assertEqual(ctx.exception.code.value, "CRC_MISMATCH")

    def test_file_and_mmap_roundtrip(self) -> None:
        value = complex(-8.25, 15.5)
        payload = codec.encode_complex(value)
        frame = codec.store_bytes(payload)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "value.p6")
            write_frame(path, frame)
            with MappedFrame(path) as mapped:
                version, bits, _trits, _meta = mapped.unpack()
        self.assertEqual(version, 1)
        got = codec.decode_complex(codec.bits_to_bytes(bits)[: len(payload)])
        self.assertEqual(got, value)

    def test_example_script_runs(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "examples" / "roundtrip_value.py")],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("全部通过", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
