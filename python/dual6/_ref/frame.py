"""Versioned Dual6 frames.

D6P0 is the simple legacy frame:

    magic "D6P0" | version u8 | width u32 | bit_len u32 | trit_len u32
    bit plane bytes
    trit plane bytes

D6P1 adds a CRC32 and a small layout header:

    magic "D6P1" | version u8 | layout u8 | reserved u16 |
    width u32 | payload_len u32 | crc32 u32 |
    payload

The frame is a storage format only.  It does not define arithmetic.
"""

from __future__ import annotations

import zlib
from struct import Struct
from typing import List, Sequence, Tuple

from .dual_plane import (
    TRIT_PER_BYTE,
    pack_bits_bytes,
    pack_trits_bytes,
    unpack_bits_bytes,
    unpack_trits_bytes,
)
from .errors import Dual6Error, ErrorCode

# ---------------------------------------------------------------------------
# D6P0
# ---------------------------------------------------------------------------

MAGIC = b"D6P0"
VERSION = 1

_HEADER = Struct("<4sBIII")
_HEADER_SIZE = _HEADER.size


def pack_dual_plane(bits: Sequence[int], trits: Sequence[int]) -> bytes:
    """Serialize bits and trits into a D6P0 dual-plane frame."""
    if len(bits) != len(trits):
        raise Dual6Error(
            ErrorCode.WIDTH_MISMATCH,
            f"bits length {len(bits)} != trits length {len(trits)}",
        )
    width = len(bits)
    bit_data = pack_bits_bytes(bits)
    trit_data = pack_trits_bytes(trits)
    header = _HEADER.pack(MAGIC, VERSION, width, len(bit_data), len(trit_data))
    return header + bit_data + trit_data


def unpack_dual_plane(data: bytes) -> Tuple[List[int], List[int]]:
    """Deserialize a D6P0 dual-plane frame into ``(bits, trits)``."""
    if len(data) < _HEADER_SIZE:
        raise Dual6Error(ErrorCode.INVALID_LAYOUT, "frame shorter than header")
    magic, version, width, bit_len, trit_len = _HEADER.unpack_from(data)
    if magic != MAGIC:
        raise Dual6Error(ErrorCode.INVALID_LAYOUT, f"bad magic {magic!r}")
    if version != VERSION:
        raise Dual6Error(ErrorCode.UNSUPPORTED_VERSION, f"unsupported version {version}")
    expected_bit_len = (width + 7) // 8
    expected_trit_len = (width + TRIT_PER_BYTE - 1) // TRIT_PER_BYTE
    if bit_len != expected_bit_len or trit_len != expected_trit_len:
        raise Dual6Error(
            ErrorCode.INVALID_LAYOUT,
            f"length fields bit={bit_len}/{expected_bit_len}, trit={trit_len}/{expected_trit_len}",
        )
    if len(data) != _HEADER_SIZE + bit_len + trit_len:
        raise Dual6Error(
            ErrorCode.INVALID_LAYOUT,
            f"frame length {len(data)} != header + payload {_HEADER_SIZE + bit_len + trit_len}",
        )
    bit_start = _HEADER_SIZE
    trit_start = bit_start + bit_len
    bits = unpack_bits_bytes(data[bit_start:trit_start], width)
    trits = unpack_trits_bytes(data[trit_start : trit_start + trit_len], width)
    return bits, trits


# ---------------------------------------------------------------------------
# D6P1
# ---------------------------------------------------------------------------

MAGIC_V1 = b"D6P1"
VERSION_V1 = 1
LAYOUT_DUAL_PLANE = 0

_HEADER_V1 = Struct("<4sBBHIII")
_HEADER_V1_SIZE = _HEADER_V1.size
_CRC_STRUCT = Struct("<I")
_CRC_OFFSET = 16


def _crc32(header_with_zero_crc: bytes, payload: bytes) -> int:
    return zlib.crc32(header_with_zero_crc + payload) & 0xFFFFFFFF


def pack_dual_plane_v1(bits: Sequence[int], trits: Sequence[int]) -> bytes:
    """Serialize bits and trits into a D6P1 dual-plane frame with CRC32."""
    if len(bits) != len(trits):
        raise Dual6Error(
            ErrorCode.WIDTH_MISMATCH,
            f"bits length {len(bits)} != trits length {len(trits)}",
        )
    width = len(bits)
    payload = pack_bits_bytes(bits) + pack_trits_bytes(trits)
    header = bytearray(
        _HEADER_V1.pack(
            MAGIC_V1,
            VERSION_V1,
            LAYOUT_DUAL_PLANE,
            0,
            width,
            len(payload),
            0,
        )
    )
    crc = _crc32(bytes(header), payload)
    _CRC_STRUCT.pack_into(header, _CRC_OFFSET, crc)
    return bytes(header) + payload


def unpack_dual_plane_v1(data: bytes) -> Tuple[List[int], List[int]]:
    """Deserialize a D6P1 dual-plane frame into ``(bits, trits)``."""
    if len(data) < _HEADER_V1_SIZE:
        raise Dual6Error(ErrorCode.INVALID_LAYOUT, "frame shorter than D6P1 header")
    magic, version, layout, reserved, width, payload_len, crc = _HEADER_V1.unpack_from(data)
    if magic != MAGIC_V1:
        raise Dual6Error(ErrorCode.INVALID_LAYOUT, f"bad magic {magic!r}")
    if version != VERSION_V1:
        raise Dual6Error(ErrorCode.UNSUPPORTED_VERSION, f"unsupported version {version}")
    if layout != LAYOUT_DUAL_PLANE:
        raise Dual6Error(ErrorCode.INVALID_LAYOUT, f"unsupported layout {layout}")
    if reserved != 0:
        raise Dual6Error(ErrorCode.INVALID_LAYOUT, f"reserved field must be 0, got {reserved}")

    expected_payload_len = (width + 7) // 8 + (width + TRIT_PER_BYTE - 1) // TRIT_PER_BYTE
    if payload_len != expected_payload_len:
        raise Dual6Error(
            ErrorCode.INVALID_LAYOUT,
            f"payload length {payload_len} != expected {expected_payload_len}",
        )
    if len(data) != _HEADER_V1_SIZE + payload_len:
        raise Dual6Error(
            ErrorCode.INVALID_LAYOUT,
            f"frame length {len(data)} != header + payload {_HEADER_V1_SIZE + payload_len}",
        )

    header = bytearray(data[:_HEADER_V1_SIZE])
    _CRC_STRUCT.pack_into(header, _CRC_OFFSET, 0)
    calculated = _crc32(bytes(header), data[_HEADER_V1_SIZE:])
    if calculated != crc:
        raise Dual6Error(
            ErrorCode.CRC_MISMATCH,
            f"CRC32 mismatch: stored {crc:#010x}, calculated {calculated:#010x}",
        )

    payload = data[_HEADER_V1_SIZE:]
    bit_len = (width + 7) // 8
    bits = unpack_bits_bytes(payload[:bit_len], width)
    trits = unpack_trits_bytes(payload[bit_len:], width)
    return bits, trits


# ---------------------------------------------------------------------------
# D6P2: dual-plane payload, dtype, optional fixed-size block metadata
# ---------------------------------------------------------------------------

MAGIC_V2 = b"D6P2"
VERSION_V2 = 1
LAYOUT_DUAL_PLANE_V2 = 0

DTYPE_RAW = 0
DTYPE_BINARY = 1
DTYPE_TERNARY = 2
DTYPE_MIXED = 3

_HEADER_V2 = Struct("<4sBBBHIIIIII")
_HEADER_V2_SIZE = _HEADER_V2.size
_CRC_OFFSET_V2 = 29


LAYOUT_DUAL_PLANE_SPARSE = 1
"""Layout id 1: block-compacted bit plane ("sparse bit plane").

Payload layout (block mode only)::

    block flags   ceil(block_count / 8) bytes   bit i = block i has a bitmap
    bitmaps       ceil(bs/8) bytes for every block whose flag is set
    trit plane    ceil(bs/5) bytes per block, always present, contiguous

Blocks whose flag is clear are all-zero in the bit channel.  A mask that is a
few percent dense therefore stores only the blocks that actually contain a set
bit, while the trit plane stays contiguous (so a ternary engine reads exactly
the same bytes as in layout 0).
"""

FLAG_OMIT_BIT_PLANE = 0x0001
"""D6P2 flags bit 0: the bit plane is absent; the payload is trit-only.

When set, every bit must be 0 (otherwise data would be lost), the payload holds
only the trit plane, and readers return ``bits = [0] * width``.  This makes a
pure-ternary payload cost ``ceil(n/5)`` bytes instead of
``ceil(n/8) + ceil(n/5)`` -- 1.6 bpw instead of 2.6 bpw.
"""


def _dp_block_bytes(symbols: int, omit_bit_plane: bool = False) -> int:
    trits = (symbols + 4) // 5
    return trits if omit_bit_plane else (symbols + 7) // 8 + trits


def _check_dtype(dtype: int) -> None:
    if dtype not in (DTYPE_RAW, DTYPE_BINARY, DTYPE_TERNARY, DTYPE_MIXED):
        raise Dual6Error(ErrorCode.INVALID_LAYOUT, f"unsupported dtype {dtype}")


def pack_dual_plane_v2(
    bits: Sequence[int],
    trits: Sequence[int],
    dtype: int = DTYPE_RAW,
    block_symbols: int = 0,
    flags: int = 0,
    layout: int = LAYOUT_DUAL_PLANE_V2,
) -> bytes:
    """Serialize a D6P2 frame.

    ``layout=0`` is the plain dual-plane frame.  ``layout=1`` is the
    block-compacted "sparse bit plane" variant (see
    :data:`LAYOUT_DUAL_PLANE_SPARSE`); it requires ``block_symbols > 0``.

    If ``block_symbols`` is 0, the payload is one dual-plane stream.
    Otherwise, the bit/trit streams are split into fixed-size blocks and the
    header carries the block metadata.  ``block_count * block_symbols`` must
    equal the total width.
    """
    if layout not in (LAYOUT_DUAL_PLANE_V2, LAYOUT_DUAL_PLANE_SPARSE):
        raise Dual6Error(ErrorCode.INVALID_LAYOUT, f"unsupported layout {layout}")
    if len(bits) != len(trits):
        raise Dual6Error(
            ErrorCode.WIDTH_MISMATCH,
            f"bits length {len(bits)} != trits length {len(trits)}",
        )
    _check_dtype(dtype)
    omit_bit_plane = bool(flags & FLAG_OMIT_BIT_PLANE)
    if omit_bit_plane and any(bits):
        raise Dual6Error(
            ErrorCode.INVALID_BIT,
            "FLAG_OMIT_BIT_PLANE requires every bit to be 0",
        )
    width = len(bits)

    if layout == LAYOUT_DUAL_PLANE_SPARSE and block_symbols <= 0:
        raise Dual6Error(
            ErrorCode.INVALID_LAYOUT, "sparse layout requires block_symbols > 0"
        )

    if block_symbols == 0:
        block_bytes = 0
        block_count = 0
        if omit_bit_plane:
            payload = pack_trits_bytes(trits)
        else:
            payload = pack_bits_bytes(bits) + pack_trits_bytes(trits)
    else:
        if block_symbols < 0:
            raise Dual6Error(ErrorCode.INVALID_LAYOUT, "block_symbols must be >= 0")
        if width % block_symbols != 0:
            raise Dual6Error(
                ErrorCode.WIDTH_MISMATCH,
                f"width {width} is not a multiple of block_symbols {block_symbols}",
            )
        block_count = width // block_symbols
        if layout == LAYOUT_DUAL_PLANE_SPARSE:
            block_bytes = (block_symbols + 4) // 5
            flag_bytes = (block_count + 7) // 8
            block_flags = bytearray(flag_bytes)
            bitmaps: List[bytes] = []
            trit_chunks: List[bytes] = []
            for i in range(block_count):
                start = i * block_symbols
                stop = start + block_symbols
                block_bits = bits[start:stop]
                trit_chunks.append(pack_trits_bytes(trits[start:stop]))
                if any(block_bits):
                    block_flags[i >> 3] |= 1 << (i & 7)
                    bitmaps.append(pack_bits_bytes(block_bits))
            payload = bytes(block_flags) + b"".join(bitmaps) + b"".join(trit_chunks)
        else:
            block_bytes = _dp_block_bytes(block_symbols, omit_bit_plane)
            chunks: List[bytes] = []
            for i in range(block_count):
                start = i * block_symbols
                stop = start + block_symbols
                if omit_bit_plane:
                    chunks.append(pack_trits_bytes(trits[start:stop]))
                else:
                    chunks.append(
                        pack_bits_bytes(bits[start:stop])
                        + pack_trits_bytes(trits[start:stop])
                    )
            payload = b"".join(chunks)

    header = bytearray(
        _HEADER_V2.pack(
            MAGIC_V2,
            VERSION_V2,
            layout,
            dtype,
            flags,
            width,
            block_symbols,
            block_bytes,
            block_count,
            len(payload),
            0,
        )
    )
    crc = _crc32(bytes(header), payload)
    _CRC_STRUCT.pack_into(header, _CRC_OFFSET_V2, crc)
    return bytes(header) + payload


def unpack_dual_plane_v2(data: bytes) -> Tuple[List[int], List[int], dict]:
    """Deserialize a D6P2 frame.

    Returns ``(bits, trits, metadata)``.
    """
    if len(data) < _HEADER_V2_SIZE:
        raise Dual6Error(ErrorCode.INVALID_LAYOUT, "frame shorter than D6P2 header")
    (
        magic,
        version,
        layout,
        dtype,
        flags,
        width,
        block_symbols,
        block_bytes,
        block_count,
        payload_len,
        crc,
    ) = _HEADER_V2.unpack_from(data)
    if magic != MAGIC_V2:
        raise Dual6Error(ErrorCode.INVALID_LAYOUT, f"bad magic {magic!r}")
    if version != VERSION_V2:
        raise Dual6Error(ErrorCode.UNSUPPORTED_VERSION, f"unsupported version {version}")
    if layout not in (LAYOUT_DUAL_PLANE_V2, LAYOUT_DUAL_PLANE_SPARSE):
        raise Dual6Error(ErrorCode.INVALID_LAYOUT, f"unsupported layout {layout}")
    sparse = layout == LAYOUT_DUAL_PLANE_SPARSE
    if sparse and block_symbols <= 0:
        raise Dual6Error(
            ErrorCode.INVALID_LAYOUT, "sparse layout requires block_symbols > 0"
        )
    _check_dtype(dtype)

    omit_bit_plane = bool(flags & FLAG_OMIT_BIT_PLANE)
    if block_symbols == 0:
        if block_bytes != 0 or block_count != 0:
            raise Dual6Error(ErrorCode.INVALID_LAYOUT, "block metadata must be zero when block_symbols=0")
        expected_payload_len = _dp_block_bytes(width, omit_bit_plane)
    elif sparse:
        expected_block_bytes = (block_symbols + 4) // 5
        if block_bytes != expected_block_bytes:
            raise Dual6Error(
                ErrorCode.INVALID_LAYOUT,
                f"block_bytes {block_bytes} != expected trit bytes {expected_block_bytes}",
            )
        if block_count * block_symbols != width:
            raise Dual6Error(
                ErrorCode.INVALID_LAYOUT,
                f"block_count {block_count} * block_symbols {block_symbols} != width {width}",
            )
        expected_payload_len = -1  # validated after the flags are known
    else:
        expected_block_bytes = _dp_block_bytes(block_symbols, omit_bit_plane)
        if block_bytes != expected_block_bytes:
            raise Dual6Error(
                ErrorCode.INVALID_LAYOUT,
                f"block_bytes {block_bytes} != expected {expected_block_bytes}",
            )
        if block_count * block_symbols != width:
            raise Dual6Error(
                ErrorCode.INVALID_LAYOUT,
                f"block_count {block_count} * block_symbols {block_symbols} != width {width}",
            )
        expected_payload_len = block_count * block_bytes

    if expected_payload_len >= 0 and payload_len != expected_payload_len:
        raise Dual6Error(
            ErrorCode.INVALID_LAYOUT,
            f"payload length {payload_len} != expected {expected_payload_len}",
        )
    if len(data) != _HEADER_V2_SIZE + payload_len:
        raise Dual6Error(
            ErrorCode.INVALID_LAYOUT,
            f"frame length {len(data)} != header + payload {_HEADER_V2_SIZE + payload_len}",
        )

    header = bytearray(data[:_HEADER_V2_SIZE])
    _CRC_STRUCT.pack_into(header, _CRC_OFFSET_V2, 0)
    calculated = _crc32(bytes(header), data[_HEADER_V2_SIZE:])
    if calculated != crc:
        raise Dual6Error(
            ErrorCode.CRC_MISMATCH,
            f"CRC32 mismatch: stored {crc:#010x}, calculated {calculated:#010x}",
        )

    payload = data[_HEADER_V2_SIZE:]
    bits: List[int] = []
    trits: List[int] = []
    if sparse:
        flag_bytes = (block_count + 7) // 8
        if payload_len < flag_bytes:
            raise Dual6Error(ErrorCode.INVALID_LAYOUT, "payload shorter than block flags")
        block_flags = payload[:flag_bytes]
        bitmap_bytes = (block_symbols + 7) // 8
        present = sum(1 for i in range(block_count) if (block_flags[i >> 3] >> (i & 7)) & 1)
        expected = flag_bytes + present * bitmap_bytes + block_count * block_bytes
        if payload_len != expected:
            raise Dual6Error(
                ErrorCode.INVALID_LAYOUT,
                f"sparse payload length {payload_len} != expected {expected}",
            )
        cursor = flag_bytes
        trit_base = flag_bytes + present * bitmap_bytes
        for i in range(block_count):
            has_bitmap = (block_flags[i >> 3] >> (i & 7)) & 1
            if has_bitmap:
                block_bits = unpack_bits_bytes(
                    payload[cursor : cursor + bitmap_bytes], block_symbols
                )
                cursor += bitmap_bytes
            else:
                block_bits = [0] * block_symbols
            start = trit_base + i * block_bytes
            block_trits = unpack_trits_bytes(payload[start : start + block_bytes], block_symbols)
            bits.extend(block_bits)
            trits.extend(block_trits)
    elif block_symbols == 0:
        if omit_bit_plane:
            bits = [0] * width
            trits = unpack_trits_bytes(payload, width)
        else:
            bit_bytes = (width + 7) // 8
            bits = unpack_bits_bytes(payload[:bit_bytes], width)
            trits = unpack_trits_bytes(payload[bit_bytes:], width)
    else:
        bit_bytes = 0 if omit_bit_plane else (block_symbols + 7) // 8
        for i in range(block_count):
            block = payload[i * block_bytes : (i + 1) * block_bytes]
            if omit_bit_plane:
                bits.extend([0] * block_symbols)
            else:
                bits.extend(unpack_bits_bytes(block[:bit_bytes], block_symbols))
            trits.extend(unpack_trits_bytes(block[bit_bytes:], block_symbols))

    meta = {
        "layout": layout,
        "dtype": dtype,
        "flags": flags,
        "width": width,
        "block_symbols": block_symbols,
        "block_bytes": block_bytes,
        "block_count": block_count,
        "payload_len": payload_len,
        "crc32": crc,
    }
    return bits, trits, meta


# ---------------------------------------------------------------------------
# Auto-detection helpers
# ---------------------------------------------------------------------------


def frame_version(data: bytes) -> int:
    """Return 0/1/2 for D6P0/D6P1/D6P2, or raise INVALID_LAYOUT."""
    if len(data) < 4:
        raise Dual6Error(ErrorCode.INVALID_LAYOUT, "frame shorter than magic")
    magic = bytes(data[:4])
    if magic == MAGIC:
        return 0
    if magic == MAGIC_V1:
        return 1
    if magic == MAGIC_V2:
        return 2
    raise Dual6Error(ErrorCode.INVALID_LAYOUT, f"unknown frame magic {magic!r}")


def unpack_frame_auto(data: bytes) -> Tuple[int, List[int], List[int], dict]:
    """Auto-detect a frame and return ``(version, bits, trits, metadata)``."""
    version = frame_version(data)
    if version == 0:
        bits, trits = unpack_dual_plane(data)
        return 0, bits, trits, {}
    if version == 1:
        bits, trits = unpack_dual_plane_v1(data)
        return 1, bits, trits, {}
    bits, trits, meta = unpack_dual_plane_v2(data)
    return 2, bits, trits, meta

def unpack_frame_auto_buffer(buffer: object) -> Tuple[int, List[int], List[int], dict]:
    """Decode a frame from any buffer-like object.

    Accepts ``bytes`` / ``bytearray`` / ``memoryview`` / ``mmap``.  The pure
    Python path only borrows the buffer while decoding and releases it before
    returning, so callers such as :class:`MappedFrame` can still close their
    ``mmap``.  The native extension overrides this with a zero-copy PyBuffer
    reader.
    """
    try:
        view = memoryview(buffer)
    except TypeError as exc:
        raise Dual6Error(
            ErrorCode.INVALID_LAYOUT,
            f"object of type {type(buffer).__name__} does not support the buffer protocol",
        ) from exc
    try:
        return unpack_frame_auto(view)
    finally:
        view.release()
