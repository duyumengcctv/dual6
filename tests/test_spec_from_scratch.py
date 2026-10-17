"""Design-first tests, written from the docs alone.

Every expectation here is derived from ``docs/00``..``docs/05`` (and the
header tables inside them), *not* from reading the implementation.  The
point is to make doc/code drift fail loudly:

* the symbol table in ``docs/01`` is parsed and re-checked against the code;
* the error-code table in ``docs/05`` is parsed and compared set-wise;
* the block tables in ``docs/03`` are parsed and compared numerically;
* frame bytes are parsed with an **independent** ``struct`` layout built
  from the offset tables in ``docs/04``, and the CRC is recomputed from the
  doc's written rule ("zero the field, CRC over header + payload").

If a future edit changes the code without changing the doc (or the other
way round), one of these should fail.
"""

from __future__ import annotations

import math
import os
import random
import re
import struct
import unittest
import zlib

import dual6
from dual6 import Dual6Error, ErrorCode

DOCS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")


def doc(name: str) -> str:
    with open(os.path.join(DOCS, name), encoding="utf-8") as fh:
        return fh.read()


def all_tables(text: str):
    """Return every pipe table in *text* as ``(header_cells, rows)``."""
    tables = []
    header = None
    rows = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            if header is not None:
                tables.append((header, rows))
                header, rows = None, []
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if header is None:
            header = cells
            continue
        if all(set(c) <= set("-: ") for c in cells):
            continue
        rows.append(cells)
    if header is not None:
        tables.append((header, rows))
    return tables


def find_table(text: str, first_cell: str, columns: int):
    for header, rows in all_tables(text):
        if header[0].lower() == first_cell.lower() and len(header) == columns and rows:
            return header, rows
    raise AssertionError(f"table starting with {first_cell!r} not found")


def parse_int(cell: str) -> int:
    return int(re.sub(r"[^0-9\-]", "", cell))


# --------------------------------------------------------------------------
# docs/01 — the 6-state symbol
# --------------------------------------------------------------------------


class SymbolFromDoc(unittest.TestCase):
    def test_docs01_table_matches_code(self):
        _, rows = find_table(doc("01-symbol.md"), "d", 3)
        self.assertEqual(len(rows), 6, "docs/01 should list exactly 6 symbols")
        seen = set()
        for raw_d, raw_b, raw_t in rows:
            d, b, t = int(raw_d), int(raw_b), int(raw_t)
            with self.subTest(d=d):
                # the formula printed in docs/01
                self.assertEqual(d, 3 * b + (t + 1))
                self.assertIn(b, (0, 1))
                self.assertIn(t, (-1, 0, 1))
                self.assertEqual(dual6.encode_digit(b, t), d)
                self.assertEqual(tuple(dual6.decode_digit(d)), (b, t))
            seen.add(d)
        self.assertEqual(seen, set(range(6)), "docs/01 must cover every digit 0..5")

    def test_domain_is_exactly_six_and_bijective(self):
        pairs = [(b, t) for b in (0, 1) for t in (-1, 0, 1)]
        digits = [dual6.encode_digit(b, t) for b, t in pairs]
        self.assertEqual(sorted(digits), [0, 1, 2, 3, 4, 5])
        self.assertEqual(len(set(digits)), 6, "encoding must be injective")
        for d in range(6):
            b, t = dual6.decode_digit(d)
            self.assertEqual(dual6.encode_digit(b, t), d, "decode/encode must invert")

    def test_docs01_zero_symbol_is_one(self):
        # "Dual6 的零是 (0,0)，每个码元为 d=1"
        self.assertEqual(dual6.encode_digit(0, 0), 1)

    def test_rejects_out_of_domain(self):
        for bad in ((2, 0), (0, 2), (0, -2), (-1, 0)):
            with self.subTest(bad=bad):
                with self.assertRaises(Dual6Error) as ctx:
                    dual6.encode_digit(*bad)
                self.assertIn(
                    ctx.exception.code,
                    (ErrorCode.INVALID_BIT, ErrorCode.INVALID_TRIT),
                )
        for bad_digit in (-1, 6, 7, 100):
            with self.subTest(digit=bad_digit):
                with self.assertRaises(Dual6Error) as ctx:
                    dual6.decode_digit(bad_digit)
                self.assertEqual(ctx.exception.code, ErrorCode.INVALID_DIGIT)


# --------------------------------------------------------------------------
# docs/05 — the error-code table
# --------------------------------------------------------------------------


class ErrorTableFromDoc(unittest.TestCase):
    def test_error_codes_are_exactly_the_documented_set(self):
        _, rows = find_table(doc("05-errors.md"), "错误码", 2)
        documented = {r[0].strip("`").strip() for r in rows}
        implemented = {code.name for code in ErrorCode}
        self.assertEqual(documented - implemented, set(), "documented but missing")
        self.assertEqual(implemented - documented, set(), "implemented but undocumented")

    def test_dual6_error_carries_code(self):
        try:
            dual6.decode_digit(99)
        except Dual6Error as exc:
            self.assertIsInstance(exc.code, ErrorCode)
        else:
            self.fail("decode_digit(99) should raise Dual6Error")


# --------------------------------------------------------------------------
# docs/03 — layouts, blocks, planes
# --------------------------------------------------------------------------


def bits_needed(symbols: int) -> int:
    """Smallest number of bits that can hold 6**symbols distinct values."""
    return math.ceil(symbols * math.log2(6))


class LayoutFromDoc(unittest.TestCase):
    def test_interleaved_density_claim(self):
        # docs/03: "5 个码元 -> 13 bit"
        self.assertEqual(bits_needed(5), 13)
        self.assertLess(6 ** 5, 2 ** 13, "13 bits must be enough for 5 symbols")
        self.assertGreaterEqual(6 ** 5, 2 ** 12, "...and 12 bits must not be")

    def test_fixed_block_table(self):
        _, rows = find_table(doc("03-layout.md"), "布局", 4)
        self.assertEqual(len(rows), 3)
        for raw_name, raw_sym, raw_bytes, raw_used in rows:
            name = raw_name.strip("`")
            symbols, nbytes = int(raw_sym), int(raw_bytes)
            used = int(re.sub(r"[^0-9]", "", raw_used))
            with self.subTest(layout=name):
                layout = dual6.LAYOUTS[name]
                self.assertEqual(layout.symbols, symbols)
                self.assertEqual(layout.byte_length, nbytes)
                # "实际使用 N bit" must be the exact information content
                self.assertEqual(used, bits_needed(symbols))
                self.assertEqual(nbytes, math.ceil(used / 8))
                self.assertLess(6 ** symbols, 2 ** used)
                self.assertGreaterEqual(6 ** symbols, 2 ** (used - 1))

    def test_dual_plane_block_table(self):
        _, rows = find_table(doc("03-layout.md"), "布局", 5)
        self.assertEqual(len(rows), 3)
        for raw_name, raw_sym, raw_bit, raw_trit, raw_total in rows:
            name = raw_name.strip("`")
            symbols = int(raw_sym)
            bit_bytes = int(re.sub(r"[^0-9]", "", raw_bit))
            trit_bytes = int(re.sub(r"[^0-9]", "", raw_trit))
            total = int(re.sub(r"[^0-9]", "", raw_total))
            with self.subTest(layout=name):
                layout = dual6.LAYOUTS_DP[name]
                self.assertEqual(layout.symbols, symbols)
                self.assertEqual(layout.bit_bytes, bit_bytes)
                self.assertEqual(layout.trit_bytes, trit_bytes)
                self.assertEqual(layout.byte_length, total)
                # docs/03: the three blocks divide exactly
                self.assertEqual(bit_bytes, math.ceil(symbols / 8))
                self.assertEqual(trit_bytes, math.ceil(symbols / 5))
                self.assertEqual(total, bit_bytes + trit_bytes)
                # the split must not cost a single byte
                self.assertEqual(
                    total,
                    dual6.bits_bytes_len(symbols) + dual6.trits_bytes_len(symbols),
                )

    def test_plane_lengths_follow_the_formula(self):
        # docs/04 constraints: ceil(n/8) and ceil(n/5)
        for n in range(0, 400):
            with self.subTest(n=n):
                self.assertEqual(dual6.bits_bytes_len(n), math.ceil(n / 8))
                self.assertEqual(dual6.trits_bytes_len(n), math.ceil(n / 5))

    def test_interleaved_bound(self):
        # docs/03: "D >= 6^n 返回 INVALID_PACKING"
        for n in (1, 2, 3, 5, 24):
            with self.subTest(n=n):
                self.assertEqual(dual6.max_interleaved(n), 6 ** n - 1)
                self.assertEqual(
                    dual6.unpack_digits(6 ** n - 1, n), [5] * n
                )
                with self.assertRaises(Dual6Error) as ctx:
                    dual6.unpack_digits(6 ** n, n)
                self.assertEqual(ctx.exception.code, ErrorCode.INVALID_PACKING)

    def test_pack_digits_roundtrip_and_lsb_first(self):
        rng = random.Random(20240501)
        for n in (1, 2, 5, 24, 33):
            digits = [rng.randrange(6) for _ in range(n)]
            with self.subTest(n=n):
                value = dual6.pack_digits(digits)
                self.assertEqual(dual6.unpack_digits(value, n), digits)
                # LSB first: digit 0 is the least significant
                if n:
                    self.assertEqual(value % 6, digits[0])

    def test_unused_bits_are_zero(self):
        # nothing in the spec says padding may be dirty
        rng = random.Random(7)
        for n in range(0, 41):
            bits = [rng.randrange(2) for _ in range(n)]
            trits = [rng.randrange(-1, 2) for _ in range(n)]
            with self.subTest(n=n):
                if n % 8:
                    last = dual6.pack_bits_bytes(bits)[-1]
                    self.assertLess(last, 2 ** (n % 8), "bit padding not zeroed")
                if n % 5:
                    last = dual6.pack_trits_bytes(trits)[-1]
                    self.assertLess(last, 3 ** (n % 5), "trit padding not zeroed")

    def test_dual_plane_blocks_agree_with_interleaved(self):
        rng = random.Random(99)
        for name in ("D6-64", "D6-128", "D6-40"):
            layout = dual6.LAYOUTS[name]
            dp = dual6.LAYOUTS_DP[name + "-DP"]
            bits = [rng.randrange(2) for _ in range(layout.symbols)]
            trits = [rng.randrange(-1, 2) for _ in range(layout.symbols)]
            symbols = dual6.mux(bits, trits)
            with self.subTest(layout=name):
                inter = dual6.pack_block(symbols, layout)
                self.assertEqual(len(inter), layout.byte_length)
                self.assertEqual(dual6.unpack_block(inter, layout), symbols)

                dp_bytes = dual6.pack_block_dp(bits, trits, dp)
                self.assertEqual(len(dp_bytes), dp.byte_length)
                self.assertEqual(dual6.unpack_block_dp(dp_bytes, dp), (bits, trits))

                # docs/03: "二进制引擎只读前段 bit 平面；三进制引擎只读后段 trit 平面"
                self.assertEqual(
                    dp_bytes[: dp.bit_bytes], bytes(dual6.pack_bits_bytes(bits))
                )
                self.assertEqual(
                    dp_bytes[dp.bit_bytes :],
                    bytes(dual6.pack_trits_bytes(trits)),
                )


# --------------------------------------------------------------------------
# docs/02 — the sequence layer
# --------------------------------------------------------------------------


class SequenceFromDoc(unittest.TestCase):
    def test_mux_is_the_documented_formula(self):
        rng = random.Random(1234)
        for n in (0, 1, 5, 64):
            bits = [rng.randrange(2) for _ in range(n)]
            trits = [rng.randrange(-1, 2) for _ in range(n)]
            with self.subTest(n=n):
                symbols = dual6.mux(bits, trits)
                self.assertEqual(len(symbols), n)
                for b, t, d in zip(bits, trits, symbols):
                    self.assertEqual(d, 3 * b + (t + 1))
                self.assertEqual(dual6.demux(symbols), (bits, trits))

    def test_demux_is_lsb_first_and_index_preserving(self):
        bits = [1, 0, 1, 0]
        trits = [-1, 0, 1, 1]
        symbols = dual6.mux(bits, trits)
        got_bits, got_trits = dual6.demux(symbols)
        self.assertEqual(got_bits, bits)
        self.assertEqual(got_trits, trits)
        self.assertEqual(symbols[0], 3 * 1 + (-1 + 1))

    def test_width_mismatch_is_reported(self):
        with self.assertRaises(Dual6Error) as ctx:
            dual6.mux([1, 0, 1], [0, 0])
        self.assertEqual(ctx.exception.code, ErrorCode.WIDTH_MISMATCH)

    def test_bad_inputs_are_reported(self):
        with self.assertRaises(Dual6Error) as ctx:
            dual6.mux([2], [0])
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_BIT)
        with self.assertRaises(Dual6Error) as ctx:
            dual6.mux([1], [2])
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_TRIT)
        with self.assertRaises(Dual6Error) as ctx:
            dual6.demux([6])
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_DIGIT)


# --------------------------------------------------------------------------
# docs/04 — frames, parsed with an independent struct layout
# --------------------------------------------------------------------------

# Built only from the offset tables printed in docs/04.
# magic | version | layout | [reserved|dtype] | flags | width | ... | crc32
HDR_V1 = struct.Struct("<4s" + "B" * 2 + "H" + "I" * 3)
HDR_V2 = struct.Struct("<4s" + "B" * 3 + "H" + "I" * 6)

V1_HEADER_LEN = 20
V2_HEADER_LEN = 33
V1_CRC_OFFSET = 16
V2_CRC_OFFSET = 29


def recompute_crc(frame: bytes, header_len: int, crc_offset: int) -> int:
    """docs/04: zero the CRC field, then CRC32 over header + payload."""
    zeroed = bytearray(frame[:header_len])
    zeroed[crc_offset : crc_offset + 4] = b"\x00\x00\x00\x00"
    return zlib.crc32(bytes(zeroed) + frame[header_len:]) & 0xFFFFFFFF


class FrameHeaderFromDoc(unittest.TestCase):
    def test_struct_sizes_match_doc_offsets(self):
        self.assertEqual(HDR_V1.size, V1_HEADER_LEN)
        self.assertEqual(HDR_V2.size, V2_HEADER_LEN)
        # offset 20 / 33 is where the payload starts, per docs/04
        self.assertEqual(V1_CRC_OFFSET + 4, V1_HEADER_LEN)
        self.assertEqual(V2_CRC_OFFSET + 4, V2_HEADER_LEN)

    def _parse_v1(self, frame: bytes):
        magic, ver, layout, reserved, width, plen, crc = HDR_V1.unpack_from(frame, 0)
        return dict(
            magic=magic, version=ver, layout=layout, reserved=reserved,
            width=width, payload_len=plen, crc32=crc,
            payload=frame[V1_HEADER_LEN:],
        )

    def test_v1_frame_matches_doc(self):
        bits = [1, 0, 1, 1, 0, 0, 1]
        trits = [1, -1, 0, 1, 0, -1, 1]
        frame = dual6.pack_dual_plane_v1(bits, trits)
        info = self._parse_v1(frame)

        self.assertEqual(info["magic"], b"D6P1")
        self.assertEqual(info["version"], 1)
        self.assertEqual(info["layout"], 0)
        self.assertEqual(info["reserved"], 0)
        self.assertEqual(info["width"], len(bits))
        self.assertEqual(len(info["payload"]), info["payload_len"])
        # docs/04 constraint: payload_len == ceil(n/8) + ceil(n/5)
        self.assertEqual(
            info["payload_len"],
            math.ceil(len(bits) / 8) + math.ceil(len(trits) / 5),
        )
        # docs/04 CRC rule, recomputed independently with zlib
        self.assertEqual(info["crc32"], recompute_crc(frame, V1_HEADER_LEN, V1_CRC_OFFSET))
        # and the payload really is bit plane then trit plane
        self.assertEqual(
            info["payload"], bytes(dual6.pack_bits_bytes(bits)) + bytes(dual6.pack_trits_bytes(trits))
        )
        # the reader agrees with our independent parse
        self.assertEqual(dual6.unpack_frame_auto(frame)[1:3], (bits, trits))

    def test_v2_frame_matches_doc(self):
        bits = [1, 0] * 24
        trits = [1, -1] * 24
        frame = dual6.pack_dual_plane_v2(bits, trits, dtype=dual6.DTYPE_MIXED)
        magic, ver, layout, dtype, flags, width, bsym, bbytes, bcnt, plen, crc = HDR_V2.unpack_from(frame, 0)

        self.assertEqual(magic, b"D6P2")
        self.assertEqual(ver, 1)
        self.assertEqual(layout, 0)
        self.assertEqual(dtype, dual6.DTYPE_MIXED)
        self.assertEqual(flags, 0)
        self.assertEqual(width, 48)
        self.assertEqual(len(frame) - V2_HEADER_LEN, plen)
        self.assertEqual(crc, recompute_crc(frame, V2_HEADER_LEN, V2_CRC_OFFSET))

        # docs/04: block_symbols = 0 -> one whole dual-plane stream
        self.assertEqual((bsym, bbytes, bcnt), (0, 0, 0))
        self.assertEqual(plen, math.ceil(48 / 8) + math.ceil(48 / 5))

    def test_v2_block_metadata_obeys_doc_rules(self):
        bits = [1, 0, 1] * 16
        trits = [1, -1, 0] * 16
        block = 24
        frame = dual6.pack_dual_plane_v2(bits, trits, block_symbols=block)
        _, _, _, _, _, width, bsym, bbytes, bcnt, plen, crc = HDR_V2.unpack_from(frame, 0)

        self.assertEqual(bsym, block)
        self.assertEqual(width, 48)
        # docs/04: block_count * block_symbols == width
        self.assertEqual(bcnt * bsym, width)
        # docs/04: block_bytes == ceil(bsym/8) + ceil(bsym/5)
        self.assertEqual(bbytes, math.ceil(bsym / 8) + math.ceil(bsym / 5))
        self.assertEqual(plen, bcnt * bbytes)
        self.assertEqual(len(frame) - V2_HEADER_LEN, plen)
        self.assertEqual(crc, recompute_crc(frame, V2_HEADER_LEN, V2_CRC_OFFSET))
        self.assertEqual(dual6.unpack_frame_auto(frame)[1:3], (bits, trits))

    def test_roundtrip_over_many_widths(self):
        rng = random.Random(31337)
        for n in (0, 1, 2, 3, 4, 5, 7, 8, 9, 13, 24, 40, 48, 77, 128):
            bits = [rng.randrange(2) for _ in range(n)]
            trits = [rng.randrange(-1, 2) for _ in range(n)]
            with self.subTest(n=n):
                v1 = dual6.pack_dual_plane_v1(bits, trits)
                self.assertEqual(len(v1), V1_HEADER_LEN + math.ceil(n / 8) + math.ceil(n / 5))
                self.assertEqual(dual6.unpack_dual_plane_v1(v1), (bits, trits))
                v2 = dual6.pack_dual_plane_v2(bits, trits)
                self.assertEqual(dual6.unpack_dual_plane_v2(v2)[:2], (bits, trits))
                self.assertEqual(dual6.frame_version(v1), 1)
                self.assertEqual(dual6.frame_version(v2), 2)


# --------------------------------------------------------------------------
# docs/04 — a frame that is wrong must never be silently accepted
# --------------------------------------------------------------------------


class FrameFaultsFromDoc(unittest.TestCase):
    def setUp(self):
        rng = random.Random(4242)
        self.bits = [rng.randrange(2) for _ in range(29)]
        self.trits = [rng.randrange(-1, 2) for _ in range(29)]
        self.v1 = dual6.pack_dual_plane_v1(self.bits, self.trits)
        self.v2 = dual6.pack_dual_plane_v2(self.bits, self.trits)

    def test_every_payload_bit_flip_is_caught(self):
        # docs/04: CRC mismatch must be reported, never ignored
        for frame, reader, header_len in (
            (self.v1, dual6.unpack_dual_plane_v1, V1_HEADER_LEN),
            (self.v2, dual6.unpack_dual_plane_v2, V2_HEADER_LEN),
        ):
            for offset in range(header_len, len(frame)):
                for bit in (0, 7):
                    broken = bytearray(frame)
                    broken[offset] ^= 1 << bit
                    with self.subTest(offset=offset, bit=bit):
                        with self.assertRaises(Dual6Error) as ctx:
                            reader(bytes(broken))
                        self.assertEqual(ctx.exception.code, ErrorCode.CRC_MISMATCH)

    def test_header_edits_are_caught(self):
        # the CRC covers the header too, so a doctored width cannot slip through
        broken = bytearray(self.v1)
        HDR_V1.pack_into(broken, 0, b"D6P1", 1, 0, 0, 999, len(self.v1) - V1_HEADER_LEN, 0)
        with self.assertRaises(Dual6Error) as ctx:
            dual6.unpack_dual_plane_v1(bytes(broken))
        self.assertIn(
            ctx.exception.code, (ErrorCode.CRC_MISMATCH, ErrorCode.INVALID_LAYOUT)
        )

    def test_truncation_is_never_silently_accepted(self):
        # an 80% truncated file must be rejected, not loaded
        for frame, reader in (
            (self.v1, dual6.unpack_dual_plane_v1),
            (self.v2, dual6.unpack_dual_plane_v2),
        ):
            cut = frame[: int(len(frame) * 0.8)]
            with self.assertRaises(Dual6Error):
                reader(cut)

    def test_bad_magic_is_invalid_layout(self):
        broken = b"XXXX" + self.v1[4:]
        with self.assertRaises(Dual6Error) as ctx:
            dual6.unpack_dual_plane_v1(broken)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_LAYOUT)

    def test_unknown_version_is_reported(self):
        broken = bytearray(self.v1)
        broken[4] = 9
        with self.assertRaises(Dual6Error) as ctx:
            dual6.unpack_dual_plane_v1(bytes(broken))
        self.assertEqual(ctx.exception.code, ErrorCode.UNSUPPORTED_VERSION)

    def test_inconsistent_block_metadata_is_rejected(self):
        fields = list(HDR_V2.unpack_from(self.v2, 0))
        fields[6] = 24          # block_symbols
        fields[8] = 3           # block_count -> 3 * 24 != 29
        fields[9] = 3 * 8       # payload_len
        broken = bytearray(HDR_V2.pack(*fields))
        broken += self.v2[V2_HEADER_LEN:]
        with self.assertRaises(Dual6Error):
            dual6.unpack_dual_plane_v2(bytes(broken))

    def test_write_read_roundtrip_on_disk(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "frame.p6")
            written = dual6.write_frame(path, self.v2)
            self.assertEqual(written, len(self.v2))
            self.assertEqual(dual6.read_frame(path), self.v2)
            self.assertEqual(
                dual6.unpack_frame_auto(dual6.read_frame(path))[1:3],
                (self.bits, self.trits),
            )


# --------------------------------------------------------------------------
# Differential test: the two implementations must be indistinguishable
# --------------------------------------------------------------------------

_DIFF_SCRIPT = r"""
import hashlib, random, struct, sys
import dual6

h = hashlib.sha256()
rng = random.Random(2025)


def feed(obj):
    if isinstance(obj, (bytes, bytearray)):
        h.update(bytes(obj))
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            feed(item)
    else:
        h.update(repr(obj).encode())


for n in (0, 1, 5, 7, 8, 13, 24, 40, 48, 96):
    bits = [rng.randrange(2) for _ in range(n)]
    trits = [rng.randrange(-1, 2) for _ in range(n)]
    feed(dual6.mux(bits, trits))
    feed(dual6.demux(dual6.mux(bits, trits)))
    feed(dual6.pack_bits_bytes(bits))
    feed(dual6.pack_trits_bytes(trits))
    feed(dual6.pack_dual_plane(bits, trits))
    feed(dual6.unpack_dual_plane(dual6.pack_dual_plane(bits, trits)))
    feed(dual6.pack_dual_plane_v1(bits, trits))
    feed(dual6.pack_dual_plane_v2(bits, trits, dtype=1, flags=0b110))
    feed(dual6.bits_bytes_len(n), )
    feed(dual6.trits_bytes_len(n))

for name in ("D6-64", "D6-128", "D6-40"):
    layout = dual6.LAYOUTS[name]
    dp = dual6.LAYOUTS_DP[name + "-DP"]
    bits = [rng.randrange(2) for _ in range(layout.symbols)]
    trits = [rng.randrange(-1, 2) for _ in range(layout.symbols)]
    feed(dual6.pack_block(dual6.mux(bits, trits), layout))
    feed(dual6.pack_block_dp(bits, trits, dp))

for digits in ([0], [1, 2, 3], [5] * 24, [rng.randrange(6) for _ in range(21)]):
    feed(dual6.pack_digits(digits))
    feed(dual6.unpack_digits(dual6.pack_digits(digits), len(digits)))

print(dual6.__backend__)
print(h.hexdigest())
"""


class BackendDifferential(unittest.TestCase):
    def _run(self, backend: str):
        import subprocess
        import sys

        env = dict(os.environ)
        env["DUAL6_BACKEND"] = backend
        env["PYTHONPATH"] = os.path.join(os.path.dirname(DOCS), "python")
        out = subprocess.run(
            [sys.executable, "-c", _DIFF_SCRIPT],
            capture_output=True,
            text=True,
            env=env,
        )
        if out.returncode != 0 and "not importable" in (out.stderr or ""):
            # a source-only checkout has no compiled extension; that is fine
            self.skipTest("native extension not built in this checkout")
        self.assertEqual(out.returncode, 0, out.stderr)
        lines = out.stdout.strip().splitlines()
        return lines[0], lines[1]

    def test_ref_and_native_produce_identical_bytes(self):
        used_ref, ref_digest = self._run("ref")
        used_native, native_digest = self._run("native")
        self.assertEqual(used_ref, "ref")
        if used_native != "native":
            self.skipTest("native extension not importable here")
        self.assertEqual(ref_digest, native_digest, "backends disagree byte-for-byte")
