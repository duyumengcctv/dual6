"""Interleaved base-6 packing for 6-state Dual6 symbols.

This module only packs and unpacks symbols.  The resulting integer is a
container value, not an ordinary base-6 number, and no arithmetic is defined
on it.
"""

from __future__ import annotations

import math
from typing import List, Sequence

from .errors import Dual6Error, ErrorCode
from .symbol import DIGIT_BASE, _check_digit

# Above this width the exact ``6 ** width`` comparison would materialise very
# large integers, so ``fits_unsigned_word`` switches to a log2 comparison.
_EXACT_WIDTH_LIMIT = 4096
_LOG2_DIGIT_BASE = math.log2(DIGIT_BASE)


def pack_digits(digits: Sequence[int]) -> int:
    """Pack a symbol sequence into a base-6 container integer, LSB first."""
    value = 0
    for d in reversed(digits):
        _check_digit(d)
        value = value * DIGIT_BASE + d
    return value


def unpack_digits(value: int, width: int) -> List[int]:
    """Unpack a base-6 container integer into exactly ``width`` symbols."""
    if width < 0:
        raise Dual6Error(ErrorCode.INVALID_PACKING, f"width must be >= 0, got {width}")
    limit = DIGIT_BASE ** width
    if not isinstance(value, int) or isinstance(value, bool) or not (0 <= value < limit):
        raise Dual6Error(
            ErrorCode.INVALID_PACKING,
            f"value {value!r} out of range [0, {limit}) for width {width}",
        )
    digits: List[int] = []
    for _ in range(width):
        value, d = divmod(value, DIGIT_BASE)
        digits.append(d)
    return digits


def max_interleaved(width: int) -> int:
    """Largest value of an interleaved container of the given width."""
    if width < 0:
        raise Dual6Error(ErrorCode.INVALID_PACKING, f"width must be >= 0, got {width}")
    return DIGIT_BASE ** width - 1


def fits_unsigned_word(width: int, word_bits: int) -> bool:
    """Return True if a ``width``-symbol interleaved container fits in ``word_bits``.

    The check is done without materialising ``6 ** width`` so that pathological
    widths (user input, corrupted headers) cannot exhaust memory.
    """
    if width < 0 or word_bits < 0:
        raise Dual6Error(
            ErrorCode.INVALID_PACKING,
            f"width and word_bits must be non-negative, got {width!r}, {word_bits!r}",
        )
    if width == 0:
        return True
    # 6 ** width > 2 ** width, so anything wider than the word cannot fit.
    if width > word_bits:
        return False
    if width <= _EXACT_WIDTH_LIMIT:
        return DIGIT_BASE ** width <= (1 << word_bits)
    # Both values are large but width <= word_bits: compare exponents instead.
    return width * _LOG2_DIGIT_BASE <= word_bits
