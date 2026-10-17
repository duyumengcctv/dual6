"""Tests for file and mmap frame helpers."""

from __future__ import annotations

import os
import tempfile
import unittest

from dual6 import (
    Dual6Error,
    ErrorCode,
    MappedFrame,
    main_check,
    pack_dual_plane_v1,
    pack_dual_plane_v2,
    read_frame,
    write_frame,
)


class TestFrameFileIO(unittest.TestCase):
    def _path(self, directory: str, name: str = "frame.p6") -> str:
        return os.path.join(directory, name)

    def test_write_read_roundtrip(self) -> None:
        bits = [1, 0, 1, 0, 1]
        trits = [1, -1, 0, 0, 1]
        frame = pack_dual_plane_v1(bits, trits)
        with tempfile.TemporaryDirectory() as tmp:
            path = self._path(tmp)
            written = write_frame(path, frame)
            self.assertEqual(written, len(frame))
            self.assertEqual(read_frame(path), frame)

    def test_mapped_v1(self) -> None:
        bits = [1, 0, 1]
        trits = [1, -1, 0]
        frame = pack_dual_plane_v1(bits, trits)
        with tempfile.TemporaryDirectory() as tmp:
            path = self._path(tmp)
            write_frame(path, frame)
            with MappedFrame(path) as mapped:
                version, got_bits, got_trits, meta = mapped.unpack()
            self.assertEqual(version, 1)
            self.assertEqual((got_bits, got_trits), (bits, trits))
            self.assertEqual(meta, {})

    def test_mapped_v2(self) -> None:
        bits = [1, 0] * 24
        trits = [1, -1] * 24
        frame = pack_dual_plane_v2(bits, trits, dtype=2, block_symbols=24)
        with tempfile.TemporaryDirectory() as tmp:
            path = self._path(tmp)
            write_frame(path, frame)
            with MappedFrame(path) as mapped:
                version, got_bits, got_trits, meta = mapped.unpack()
            self.assertEqual(version, 2)
            self.assertEqual((got_bits, got_trits), (bits, trits))
            self.assertEqual(meta["block_symbols"], 24)

    def test_main_check(self) -> None:
        frame = pack_dual_plane_v1([1, 0], [1, -1])
        with tempfile.TemporaryDirectory() as tmp:
            path = self._path(tmp)
            write_frame(path, frame)
            info = main_check(path)
        self.assertEqual(info["version"], 1)
        self.assertEqual(info["width"], 2)

    def test_unknown_magic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._path(tmp)
            write_frame(path, b"XXXX" + b"\x00" * 20)
            with self.assertRaises(Dual6Error) as ctx:
                with MappedFrame(path) as mapped:
                    mapped.unpack()
            self.assertEqual(ctx.exception.code, ErrorCode.INVALID_LAYOUT)


if __name__ == "__main__":
    unittest.main(verbosity=2)
