"""Exact dual-expansion codec on top of the 6-state symbol.

One integer ``N`` is encoded into one symbol sequence that carries **both**:

    b_i = i-th base-2 digit of N          (read with ``d_i // 3``)
    t_i = i-th balanced-base-3 digit of N (read with ``d_i % 3 - 1``)
    d_i = 3*b_i + (t_i + 1)               (6-state symbol, 0..5)

Both views reconstruct ``N`` exactly; there is no read-time base conversion.
The price is paid once, on write: both expansions must be computed and paired.

This is an **optional codec**, not the core container.  It is lossless but
redundant: both channels encode the same ``N``, so the bit channel cannot also
carry independent routing/mask data.

Padding rule: pad with ``d = 1`` (the Dual6 zero, ``b=0, t=0``), never ``d = 0``
(which is ``b=0, t=-1``).  Truncating the symbol sequence changes the value.
"""

from __future__ import annotations

import struct
from typing import List, Sequence

from ._ref.errors import Dual6Error, ErrorCode

DIGIT_BASE = 6
BIT_VALUES = (0, 1)
TRIT_VALUES = (-1, 0, 1)
F64_BYTES = 8


# --------------------------------------------------------------------------
# digit expansions
# --------------------------------------------------------------------------
def _check_non_negative_int(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise Dual6Error(
            ErrorCode.INVALID_PACKING,
            f"{name} must be a non-negative int, got {value!r}",
        )
    return value


def _check_symbol(d: object) -> int:
    if not isinstance(d, int) or isinstance(d, bool) or not 0 <= d < DIGIT_BASE:
        raise Dual6Error(ErrorCode.INVALID_DIGIT, f"digit must be 0..5, got {d!r}")
    return d


def to_binary_digits(n: int) -> List[int]:
    """Base-2 digits of ``n``, least-significant first."""
    n = _check_non_negative_int(n, "n")
    if n == 0:
        return [0]
    out: List[int] = []
    while n:
        out.append(n & 1)
        n >>= 1
    return out


def to_balanced_ternary(n: int) -> List[int]:
    """Balanced base-3 digits of ``n`` (LSB first), each in ``{-1, 0, +1}``."""
    n = _check_non_negative_int(n, "n")
    if n == 0:
        return [0]
    out: List[int] = []
    while n:
        r = n % 3
        if r == 2:
            out.append(-1)
            n = (n + 1) // 3
        else:
            out.append(r)
            n //= 3
    return out


def to_balanced_ternary_signed(n: int) -> List[int]:
    """Balanced base-3 digits of any integer, including negatives (LSB first)."""
    if not isinstance(n, int) or isinstance(n, bool):
        raise Dual6Error(ErrorCode.INVALID_PACKING, f"n must be an int, got {n!r}")
    sign = -1 if n < 0 else 1
    out = to_balanced_ternary(abs(n))
    return out if sign > 0 else [-t for t in out]


def from_balanced_ternary(trits: Sequence[int]) -> int:
    """Evaluate balanced-ternary digits (LSB first) back to an integer."""
    value = 0
    for t in reversed(trits):
        if t not in TRIT_VALUES:
            raise Dual6Error(ErrorCode.INVALID_TRIT, f"trit must be -1, 0 or 1, got {t!r}")
        value = value * 3 + t
    return value


# --------------------------------------------------------------------------
# the codec
# --------------------------------------------------------------------------
def encode_number(n: int, width: int = 0) -> List[int]:
    """Encode a non-negative integer into 6-state symbols.

    ``width`` pads the symbol sequence to at least that many symbols with the
    Dual6 zero (``d = 1`` -> ``(b=0, t=0)``), which preserves leading zeros.
    Without it the sequence is only as long as the longer of the two
    expansions, so ``from_bits([1, 0, 0, 0])`` would decode back as ``[1]``.
    """
    if not isinstance(width, int) or isinstance(width, bool) or width < 0:
        raise Dual6Error(
            ErrorCode.INVALID_PACKING, f"width must be a non-negative int, got {width!r}"
        )
    bits = to_binary_digits(n)
    trits = to_balanced_ternary(n)
    length = max(len(bits), len(trits), width)
    bits.extend([0] * (length - len(bits)))
    trits.extend([0] * (length - len(trits)))
    return [3 * b + (t + 1) for b, t in zip(bits, trits)]


def read_binary(symbols: Sequence[int]) -> int:
    """Binary view: ``b_i = d_i // 3`` then ``sum(b_i * 2**i)``."""
    value = 0
    for i, d in enumerate(symbols):
        value |= (_check_symbol(d) // 3) << i
    return value


def read_ternary(symbols: Sequence[int]) -> int:
    """Ternary view: ``t_i = d_i % 3 - 1`` then ``sum(t_i * 3**i)``."""
    value = 0
    for d in reversed(symbols):
        value = value * 3 + (_check_symbol(d) % 3 - 1)
    return value


# --------------------------------------------------------------------------
# friendly one-sided API: give one representation, get one representation
# --------------------------------------------------------------------------
def from_bits(bits: Sequence[int]) -> List[int]:
    """Encode from a native binary bit sequence (LSB first).

    The symbol count is at least ``len(bits)``, so leading zeros survive a
    round-trip through :func:`to_bits`.
    """
    if len(bits) == 0:
        return []
    value = 0
    for i, bit in enumerate(bits):
        if bit not in BIT_VALUES:
            raise Dual6Error(ErrorCode.INVALID_BIT, f"bit must be 0 or 1, got {bit!r}")
        value |= bit << i
    return encode_number(value, width=len(bits))


def from_trits(trits: Sequence[int]) -> List[int]:
    """Encode from a native balanced-ternary trit sequence (LSB first).

    The symbol count is at least ``len(trits)`` (see :func:`from_bits`).
    """
    if len(trits) == 0:
        return []
    return encode_number(from_balanced_ternary(trits), width=len(trits))


def to_int(symbols: Sequence[int]) -> int:
    """Decode to an integer; requires both views to agree (exact-dual)."""
    binary = read_binary(symbols)
    ternary = read_ternary(symbols)
    if binary != ternary:
        raise Dual6Error(
            ErrorCode.INVALID_LAYOUT,
            f"not an exact-dual sequence: binary view {binary} != ternary view {ternary}",
        )
    return binary


def encode_signed(n: int, width: int) -> List[int]:
    """Encode a **signed** integer as an exact-dual sequence of ``width`` symbols.

    The trit channel carries the balanced-ternary expansion directly (it is
    signed by nature); the bit channel carries the two's-complement expansion
    of the same value in ``width`` bits.  Both views therefore reconstruct the
    same negative number, which the unsigned codec cannot do.

    ``width`` must be large enough to hold the value in two's complement.
    """
    if not isinstance(width, int) or isinstance(width, bool) or width < 1:
        raise Dual6Error(
            ErrorCode.INVALID_PACKING, f"width must be a positive int, got {width!r}"
        )
    if not isinstance(n, int) or isinstance(n, bool):
        raise Dual6Error(ErrorCode.INVALID_PACKING, f"n must be an int, got {n!r}")
    lo, hi = -(1 << (width - 1)), (1 << (width - 1)) - 1
    if not lo <= n <= hi:
        raise Dual6Error(
            ErrorCode.INVALID_PACKING,
            f"{n} does not fit in {width}-bit two's complement [{lo}, {hi}]",
        )
    trits = to_balanced_ternary_signed(n)
    if len(trits) > width:
        raise Dual6Error(
            ErrorCode.INVALID_PACKING,
            f"balanced-ternary expansion of {n} needs {len(trits)} symbols > width {width}",
        )
    trits = trits + [0] * (width - len(trits))
    mask = (1 << width) - 1
    bits = [(n & mask) >> i & 1 for i in range(width)]
    return [3 * b + (t + 1) for b, t in zip(bits, trits)]


def read_signed(symbols: Sequence[int], width: int) -> int:
    """Decode an :func:`encode_signed` sequence; both views must agree."""
    if len(symbols) != width:
        raise Dual6Error(
            ErrorCode.WIDTH_MISMATCH, f"expected {width} symbols, got {len(symbols)}"
        )
    bits = [d // 3 for d in symbols]
    value = 0
    for i, b in enumerate(bits):
        value |= b << i
    if width and value >= (1 << (width - 1)):
        value -= 1 << width
    ternary = read_ternary(symbols)
    if value != ternary:
        raise Dual6Error(
            ErrorCode.INVALID_LAYOUT,
            f"not an exact-dual sequence: two's complement {value} != ternary {ternary}",
        )
    return value


def to_bits(symbols: Sequence[int]) -> List[int]:
    """Decode to a native binary bit sequence (LSB first)."""
    return [_check_symbol(d) // 3 for d in symbols]


def to_trits(symbols: Sequence[int]) -> List[int]:
    """Decode to a native balanced-ternary trit sequence (LSB first)."""
    return [_check_symbol(d) % 3 - 1 for d in symbols]


# --------------------------------------------------------------------------
# float / bytes helpers (encode the bit pattern, not the numeric value)
# --------------------------------------------------------------------------
def encode_f64(value: float) -> List[int]:
    """Encode an IEEE-754 binary64 bit pattern; both views recover the float."""
    raw = struct.pack("<d", float(value))
    return encode_number(int.from_bytes(raw, "little"))


def decode_f64(symbols: Sequence[int]) -> float:
    n = read_binary(symbols)
    try:
        raw = n.to_bytes(F64_BYTES, "little")
    except OverflowError as exc:
        raise Dual6Error(
            ErrorCode.INVALID_PACKING,
            f"decoded value does not fit in {F64_BYTES} bytes",
        ) from exc
    return struct.unpack("<d", raw)[0]


def encode_bytes(data: bytes) -> List[int]:
    """Encode a small byte string (little-endian integer) into symbols."""
    return encode_number(int.from_bytes(bytes(data), "little"))


def decode_bytes(symbols: Sequence[int], nbytes: int) -> bytes:
    if not isinstance(nbytes, int) or isinstance(nbytes, bool) or nbytes < 0:
        raise Dual6Error(ErrorCode.INVALID_LAYOUT, f"nbytes must be >= 0, got {nbytes!r}")
    n = read_binary(symbols)
    try:
        return n.to_bytes(nbytes, "little")
    except OverflowError as exc:
        raise Dual6Error(
            ErrorCode.INVALID_LAYOUT,
            f"decoded value does not fit in {nbytes} bytes",
        ) from exc


__all__ = [
    "encode_number",
    "read_binary",
    "read_ternary",
    "from_bits",
    "from_trits",
    "to_int",
    "to_bits",
    "to_trits",
    "to_binary_digits",
    "to_balanced_ternary",
    "from_balanced_ternary",
    "encode_f64",
    "decode_f64",
    "encode_bytes",
    "decode_bytes",
]
