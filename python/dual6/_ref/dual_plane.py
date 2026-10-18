"""Dual-plane byte packing: bit plane and balanced-trit plane.

The two planes are independent contiguous streams.  A binary engine can read
the bit plane without touching trits; a ternary engine can read the trit plane
without touching bits.

The hot paths use precomputed lookup tables (8 bits per byte, 5 trits per
byte).  Validation is inlined so the pure-Python fallback stays reasonably
fast on platforms without the native extension.
"""

from __future__ import annotations

import itertools
from array import array
from typing import List, Sequence

from .errors import Dual6Error, ErrorCode
from .symbol import TRIT_VALUES

TRIT_PER_BYTE = 5

_TRIT_POW5 = (1, 3, 9, 27, 81)
_TRIT_LIMIT = tuple(3 ** n for n in range(TRIT_PER_BYTE + 1))

# byte (0..242) -> its 5 balanced trits, least-significant first
_TRIT_DECODE = tuple(
    tuple(((b // _TRIT_POW5[j]) % 3) - 1 for j in range(TRIT_PER_BYTE))
    for b in range(_TRIT_LIMIT[TRIT_PER_BYTE])
)

# byte -> its 8 bits, least-significant first
_BIT_DECODE = tuple(tuple((b >> j) & 1 for j in range(8)) for b in range(256))

# 8 bits -> byte, and 5 trits -> byte.  Dict lookups beat per-element shifts
# on the pure-Python path; invalid input falls back to explicit validation.
_BIT_GROUP = {
    group: sum(bit << j for j, bit in enumerate(group))
    for group in itertools.product((0, 1), repeat=8)
}
_TRIT_GROUP = {
    group: sum((trit + 1) * _TRIT_POW5[j] for j, trit in enumerate(group))
    for group in itertools.product((-1, 0, 1), repeat=TRIT_PER_BYTE)
}


def _require_ints(values: Sequence[int], code: ErrorCode, label: str) -> None:
    """Reject non-integer elements before the table lookups.

    The lookup tables are keyed by ``(0, 1, ...)`` tuples, and Python considers
    ``0.0 == 0`` with the same hash, so a float would silently match a valid
    key.  ``array('b', ...)`` validates the element types at C speed (and
    rejects values outside a signed byte); range checking for 2..127 is still
    done by the table lookup / slow path below.
    """
    try:
        array("b", values)
    except TypeError as exc:
        raise Dual6Error(
            code, f"{label} values must be integers, got {exc}"
        ) from exc
    except (OverflowError, ValueError) as exc:
        raise Dual6Error(
            code, f"{label} value out of range, got {exc}"
        ) from exc


def pack_bits_bytes(bits: Sequence[int]) -> bytes:
    """Pack bits LSB-first into bytes; unused high bits are zero."""
    _require_ints(bits, ErrorCode.INVALID_BIT, "bit")
    n = len(bits)
    out = bytearray((n + 7) // 8)
    for base in range(0, n - 7, 8):
        try:
            out[base >> 3] = _BIT_GROUP[
                (
                    bits[base],
                    bits[base + 1],
                    bits[base + 2],
                    bits[base + 3],
                    bits[base + 4],
                    bits[base + 5],
                    bits[base + 6],
                    bits[base + 7],
                )
            ]
        except (KeyError, TypeError):
            # slow path only for invalid input, to raise a precise error
            for j in range(base, base + 8):
                bit = bits[j]
                if bit != 0 and bit != 1:
                    raise Dual6Error(ErrorCode.INVALID_BIT, f"bit must be 0 or 1, got {bit!r}")
            raise  # pragma: no cover - valid groups are always in the table
    remainder = n % 8
    if remainder:
        value = 0
        start = n - remainder
        for j in range(remainder):
            bit = bits[start + j]
            if bit != 0 and bit != 1:
                raise Dual6Error(ErrorCode.INVALID_BIT, f"bit must be 0 or 1, got {bit!r}")
            if bit:
                value |= 1 << j
        out[n >> 3] = value
    return bytes(out)


def unpack_bits_bytes(data: bytes, width: int) -> List[int]:
    """Unpack ``width`` bits from an LSB-first byte string."""
    if width < 0:
        raise Dual6Error(ErrorCode.INVALID_LAYOUT, f"width must be >= 0, got {width}")
    expected = (width + 7) // 8
    if len(data) != expected:
        raise Dual6Error(
            ErrorCode.INVALID_LAYOUT,
            f"bit plane length {len(data)} != expected {expected}",
        )
    if width % 8:
        mask = (0xFF << (width % 8)) & 0xFF
        if data[-1] & mask:
            raise Dual6Error(ErrorCode.INVALID_LAYOUT, "non-zero padding bits in bit plane")
    bits: List[int] = []
    extend = bits.extend
    for byte in data:
        extend(_BIT_DECODE[byte])
    return bits[:width]


def pack_trits_bytes(trits: Sequence[int]) -> bytes:
    """Pack balanced trits, 5 trits per byte, LSB-first within each group."""
    _require_ints(trits, ErrorCode.INVALID_TRIT, "trit")
    n = len(trits)
    out = bytearray()
    full = n - n % TRIT_PER_BYTE
    for base in range(0, full, TRIT_PER_BYTE):
        try:
            out.append(
                _TRIT_GROUP[
                    (
                        trits[base],
                        trits[base + 1],
                        trits[base + 2],
                        trits[base + 3],
                        trits[base + 4],
                    )
                ]
            )
        except (KeyError, TypeError):
            for j in range(base, base + TRIT_PER_BYTE):
                trit = trits[j]
                if trit not in TRIT_VALUES:
                    raise Dual6Error(ErrorCode.INVALID_TRIT, f"trit must be -1, 0 or 1, got {trit!r}")
            raise  # pragma: no cover
    remainder = n - full
    if remainder:
        value = 0
        for j in range(remainder):
            trit = trits[full + j]
            if trit not in TRIT_VALUES:
                raise Dual6Error(ErrorCode.INVALID_TRIT, f"trit must be -1, 0 or 1, got {trit!r}")
            value += (trit + 1) * _TRIT_POW5[j]
        out.append(value)
    return bytes(out)


def unpack_trits_bytes(data: bytes, width: int) -> List[int]:
    """Unpack ``width`` balanced trits from 5-trits-per-byte data."""
    if width < 0:
        raise Dual6Error(ErrorCode.INVALID_LAYOUT, f"width must be >= 0, got {width}")
    expected = (width + TRIT_PER_BYTE - 1) // TRIT_PER_BYTE
    if len(data) != expected:
        raise Dual6Error(
            ErrorCode.INVALID_LAYOUT,
            f"trit plane length {len(data)} != expected {expected}",
        )
    full_bytes, remainder = divmod(width, TRIT_PER_BYTE)
    trits: List[int] = []
    extend = trits.extend
    for i, byte in enumerate(data):
        used = TRIT_PER_BYTE if i < full_bytes else remainder
        if byte >= _TRIT_LIMIT[used]:
            raise Dual6Error(
                ErrorCode.INVALID_LAYOUT,
                f"invalid trit byte {byte} for {used} used trits (limit {_TRIT_LIMIT[used]})",
            )
        extend(_TRIT_DECODE[byte][:used])
    return trits
