"""Single 6-state Dual6 symbol mux/demux.

A symbol is not a base-6 numeric digit.  It is a bijective packing of one bit
and one balanced trit:

    d = 3*b + (t + 1)
    b = d // 3
    t = d % 3 - 1
"""

from __future__ import annotations

from typing import Tuple

from .errors import Dual6Error, ErrorCode

DIGIT_BASE = 6
DIGIT_COUNT = 6

BIT_VALUES = (0, 1)
TRIT_VALUES = (-1, 0, 1)


# ``bool`` is an ``int`` subclass; both backends accept ``True``/``False`` as
# 1/0.  Everything else (floats such as ``1.0``, strings, ...) is rejected with
# the same error code on the reference and native backends.

def _check_bit(bit: int) -> None:
    if not isinstance(bit, int) or bit not in BIT_VALUES:
        raise Dual6Error(ErrorCode.INVALID_BIT, f"bit must be 0 or 1, got {bit!r}")


def _check_trit(trit: int) -> None:
    if not isinstance(trit, int) or trit not in TRIT_VALUES:
        raise Dual6Error(ErrorCode.INVALID_TRIT, f"trit must be -1, 0 or 1, got {trit!r}")


def _check_digit(digit: int) -> None:
    if not isinstance(digit, int) or not (0 <= digit < DIGIT_COUNT):
        raise Dual6Error(ErrorCode.INVALID_DIGIT, f"digit must be 0..5, got {digit!r}")


def encode_digit(bit: int, trit: int) -> int:
    """Mux one bit and one balanced trit into a 6-state symbol."""
    _check_bit(bit)
    _check_trit(trit)
    return 3 * bit + (trit + 1)


def decode_digit(digit: int) -> Tuple[int, int]:
    """Demux one 6-state symbol into ``(bit, trit)``."""
    _check_digit(digit)
    return digit // 3, digit % 3 - 1
