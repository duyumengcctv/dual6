"""Optional arithmetic for exact-dual symbol sequences.

This layer only applies to the **exact-dual** codec (``dual6.exact_dual``):
both views of an operand must decode to the same integer ``N``.

Two things are provided:

* value-level ``add`` / ``sub`` / ``mul`` / ``divmod``: decode the operands to
  ``N``, compute in Python integers, re-encode.  Correct and simple.
* ``add_digits``: a demonstration that addition can also be done digit-by-digit
  with independent carry rules in each base (binary carry for ``d // 3``,
  balanced-ternary carry for ``d % 3 - 1``).  It is checked against the
  value-level result.

The core container still does not define arithmetic on the symbol ``d``; this
is an optional layer built on top of ``d`` sequences.
"""

from __future__ import annotations

import builtins
from typing import List, Sequence, Tuple

from ._ref.errors import Dual6Error, ErrorCode
from .exact_dual import encode_number, read_binary, read_ternary


def _value(symbols: Sequence[int], name: str = "operand") -> int:
    binary = read_binary(symbols)
    ternary = read_ternary(symbols)
    if binary != ternary:
        raise Dual6Error(
            ErrorCode.INVALID_LAYOUT,
            f"{name} is not an exact-dual sequence: binary view {binary} != ternary view {ternary}",
        )
    return binary


def _pair(bits: Sequence[int], trits: Sequence[int]) -> List[int]:
    length = max(len(bits), len(trits))
    bits = list(bits) + [0] * (length - len(bits))
    trits = list(trits) + [0] * (length - len(trits))
    return [3 * b + (t + 1) for b, t in zip(bits, trits)]


def add(a: Sequence[int], b: Sequence[int]) -> List[int]:
    """Return the exact-dual encoding of ``value(a) + value(b)``."""
    return encode_number(_value(a, "a") + _value(b, "b"))


def sub(a: Sequence[int], b: Sequence[int]) -> List[int]:
    """Return ``value(a) - value(b)``; negative results are rejected in v1."""
    result = _value(a, "a") - _value(b, "b")
    if result < 0:
        raise Dual6Error(ErrorCode.INVALID_PACKING, "negative result is not supported")
    return encode_number(result)


def mul(a: Sequence[int], b: Sequence[int]) -> List[int]:
    """Return the exact-dual encoding of ``value(a) * value(b)``.

    Length: the result needs at most ``len(a) + len(b)`` symbols (binary
    multiplication of an m-bit and an n-bit value fits in m+n bits), but the
    returned sequence is only as long as the value requires, so callers that
    pre-allocate should use that bound.
    """
    return encode_number(_value(a, "a") * _value(b, "b"))


def divmod(a: Sequence[int], b: Sequence[int]) -> Tuple[List[int], List[int]]:
    """Return ``(quotient, remainder)`` as exact-dual sequences.

    Semantics are **floor** division (Python's ``divmod``): the remainder takes
    the sign of the divisor.  Truncating division (round toward zero) differs
    for negative operands, and since ``sub`` rejects negatives in v1 both
    agree today -- this is pinned down so a future signed version cannot
    silently change meaning.  ``b`` must be non-zero.
    """
    x = _value(a, "a")
    y = _value(b, "b")
    if y == 0:
        raise Dual6Error(ErrorCode.INVALID_PACKING, "division by zero")
    quotient, remainder = builtins.divmod(x, y)
    return encode_number(quotient), encode_number(remainder)


# --------------------------------------------------------------------------
# digit-level addition (demonstration of independent carry rules)
# --------------------------------------------------------------------------
def _add_binary_digits(a: Sequence[int], b: Sequence[int]) -> List[int]:
    length = max(len(a), len(b))
    out: List[int] = []
    carry = 0
    for i in range(length):
        total = (a[i] if i < len(a) else 0) + (b[i] if i < len(b) else 0) + carry
        out.append(total & 1)
        carry = total >> 1
    if carry:
        out.append(carry)
    return out


def _add_balanced_digits(a: Sequence[int], b: Sequence[int]) -> List[int]:
    length = max(len(a), len(b))
    out: List[int] = []
    carry = 0
    for i in range(length):
        total = (a[i] if i < len(a) else 0) + (b[i] if i < len(b) else 0) + carry
        if total > 1:
            out.append(total - 3)
            carry = 1
        elif total < -1:
            out.append(total + 3)
            carry = -1
        else:
            out.append(total)
            carry = 0
    if carry:
        out.append(carry)
    return out


def add_digits(a: Sequence[int], b: Sequence[int]) -> List[int]:
    """Add two exact-dual sequences with per-base carry propagation.

    The binary channel uses binary carry; the ternary channel uses balanced
    ternary carry.  Both must reconstruct the same sum, which is checked.
    """
    a_bits = [d // 3 for d in a]
    b_bits = [d // 3 for d in b]
    a_trits = [d % 3 - 1 for d in a]
    b_trits = [d % 3 - 1 for d in b]

    result = _pair(_add_binary_digits(a_bits, b_bits), _add_balanced_digits(a_trits, b_trits))
    if read_binary(result) != read_ternary(result):
        raise Dual6Error(
            ErrorCode.INVALID_LAYOUT,
            "digit-level addition produced inconsistent views",
        )
    return result


# --------------------------------------------------------------------------
# channel-local (carry-free) operations
#
# These act on ONE channel and leave the other alone.  They are what a real
# mixed binary/ternary datapath would expose, and they are O(n) with **no
# carry propagation** -- unlike add/sub/mul, which decode the shared integer
# and re-encode it (coupling both channels again).
#
# Consequence: the result is generally NOT an exact-dual sequence (the two
# views no longer describe the same integer).  That is the point -- but callers
# must not feed the result back into to_int/add/mul.
# --------------------------------------------------------------------------
def _pad(a: Sequence[int], b: Sequence[int]):
    length = max(len(a), len(b))
    zero = 1  # d = 1 -> (bit 0, trit 0)
    return (
        list(a) + [zero] * (length - len(a)),
        list(b) + [zero] * (length - len(b)),
        length,
    )


def xor_bits(a: Sequence[int], b: Sequence[int]) -> List[int]:
    """Carry-free XOR of the bit channels; the trit channel is taken from ``a``.

    Length is preserved (shorter operand is zero-padded).  Not exact-dual.
    """
    left, right, _ = _pad(a, b)
    return [3 * ((x // 3) ^ (y // 3)) + (x % 3) for x, y in zip(left, right)]


def add_trits_mod3(a: Sequence[int], b: Sequence[int]) -> List[int]:
    """Carry-free addition of the trit channels modulo 3; bits come from ``a``.

    Length is preserved (shorter operand is zero-padded).  Not exact-dual.
    """
    left, right, _ = _pad(a, b)
    return [
        3 * (x // 3) + (((x % 3) + (y % 3)) % 3)
        for x, y in zip(left, right)
    ]


def neg_trits(a: Sequence[int]) -> List[int]:
    """Carry-free negation of the trit channel; bits are unchanged.  Not exact-dual."""
    return [3 * (d // 3) + ((-(d % 3)) % 3) for d in a]


__all__ = [
    "add",
    "sub",
    "mul",
    "divmod",
    "add_digits",
    "xor_bits",
    "add_trits_mod3",
    "neg_trits",
]
