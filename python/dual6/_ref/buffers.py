"""Buffer-oriented bit/trit plane helpers.

These functions write into a caller-provided writable buffer (``bytearray`` or
writable ``memoryview``) and read from any bytes-like buffer.  They are the
low-level bridge that a future Rust/mmap layer can replace without changing
the Python-facing API shape.
"""

from __future__ import annotations

from typing import List, Sequence, Tuple, Union

from .dual_plane import (
    TRIT_PER_BYTE,
    _BIT_DECODE,
    _TRIT_DECODE,
    _TRIT_LIMIT,
    pack_bits_bytes,
    pack_trits_bytes,
)
from .errors import Dual6Error, ErrorCode

Buffer = Union[bytes, bytearray, memoryview]


def _view(buffer: Buffer) -> memoryview:
    try:
        return memoryview(buffer).cast("B")
    except (TypeError, ValueError) as exc:
        raise Dual6Error(ErrorCode.INVALID_LAYOUT, f"not a byte buffer: {buffer!r}") from exc


def _writable(view: memoryview) -> memoryview:
    if view.readonly:
        raise Dual6Error(ErrorCode.INVALID_LAYOUT, "buffer is read-only")
    return view


def _check_region(view: memoryview, offset: int, length: int) -> None:
    if offset < 0 or length < 0 or offset + length > len(view):
        raise Dual6Error(
            ErrorCode.INVALID_LAYOUT,
            f"buffer region [{offset}, {offset + length}) exceeds buffer length {len(view)}",
        )


def bits_bytes_len(width: int) -> int:
    return (width + 7) // 8


def trits_bytes_len(width: int) -> int:
    return (width + TRIT_PER_BYTE - 1) // TRIT_PER_BYTE


def pack_bits_into(bits: Sequence[int], buffer: Buffer, offset: int = 0) -> int:
    """Write ``bits`` LSB-first into ``buffer``; return bytes written."""
    view = _writable(_view(buffer))
    data = pack_bits_bytes(bits)  # validates bits and uses the fast table path
    _check_region(view, offset, len(data))
    view[offset : offset + len(data)] = data
    return len(data)


def unpack_bits_from(buffer: Buffer, width: int, offset: int = 0) -> List[int]:
    """Read ``width`` LSB-first bits from ``buffer``."""
    view = _view(buffer)
    length = bits_bytes_len(width)
    _check_region(view, offset, length)
    if width % 8:
        mask = (0xFF << (width % 8)) & 0xFF
        if view[offset + length - 1] & mask:
            raise Dual6Error(ErrorCode.INVALID_LAYOUT, "non-zero padding bits in bit plane")
    bits: List[int] = []
    extend = bits.extend
    for i in range(length):
        extend(_BIT_DECODE[view[offset + i]])
    return bits[:width]


def pack_trits_into(trits: Sequence[int], buffer: Buffer, offset: int = 0) -> int:
    """Write balanced trits, 5 per byte, into ``buffer``."""
    view = _writable(_view(buffer))
    data = pack_trits_bytes(trits)  # validates trits and uses the fast table path
    _check_region(view, offset, len(data))
    view[offset : offset + len(data)] = data
    return len(data)


def unpack_trits_from(buffer: Buffer, width: int, offset: int = 0) -> List[int]:
    """Read ``width`` balanced trits from 5-trits-per-byte data."""
    view = _view(buffer)
    length = trits_bytes_len(width)
    _check_region(view, offset, length)
    full_bytes, remainder = divmod(width, TRIT_PER_BYTE)
    trits: List[int] = []
    extend = trits.extend
    for i in range(length):
        used = TRIT_PER_BYTE if i < full_bytes else remainder
        limit = _TRIT_LIMIT[used]
        byte = view[offset + i]
        if byte >= limit:
            raise Dual6Error(
                ErrorCode.INVALID_LAYOUT,
                f"invalid trit byte {byte} for {used} used trits (limit {limit})",
            )
        extend(_TRIT_DECODE[byte][:used])
    return trits


def pack_dual_plane_into(
    bits: Sequence[int],
    trits: Sequence[int],
    buffer: Buffer,
    offset: int = 0,
) -> int:
    """Write `bit plane || trit plane` into ``buffer``; return bytes written."""
    if len(bits) != len(trits):
        raise Dual6Error(
            ErrorCode.WIDTH_MISMATCH,
            f"bits length {len(bits)} != trits length {len(trits)}",
        )
    bit_len = pack_bits_into(bits, buffer, offset)
    trit_len = pack_trits_into(trits, buffer, offset + bit_len)
    return bit_len + trit_len


def unpack_dual_plane_from(
    buffer: Buffer,
    width: int,
    offset: int = 0,
) -> Tuple[List[int], List[int]]:
    """Read `bit plane || trit plane` from ``buffer``."""
    bit_len = bits_bytes_len(width)
    bits = unpack_bits_from(buffer, width, offset)
    trits = unpack_trits_from(buffer, width, offset + bit_len)
    return bits, trits
